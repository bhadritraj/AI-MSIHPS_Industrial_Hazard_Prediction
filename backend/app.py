"""
AI-MSIHPS Backend - Flask Application
Main entry point with REST API + WebSocket support
"""

from flask import Flask, jsonify, request, render_template
from flask_socketio import SocketIO, emit
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
import paho.mqtt.client as mqtt
import json, threading, os, datetime
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'msihps-secret-2026')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
    'DATABASE_URL', 'postgresql://postgres:password@localhost:5432/msihps'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
CORS(app, origins="*")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# ─── Models ───────────────────────────────────────────────────────────────────

class SensorReading(db.Model):
    __tablename__ = 'sensor_readings'
    id            = db.Column(db.Integer, primary_key=True)
    zone_id       = db.Column(db.String(50), nullable=False)
    timestamp     = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    mq2           = db.Column(db.Float)   # Methane/LPG/Smoke ppm
    mq135         = db.Column(db.Float)   # Toxic gas ppm
    temperature   = db.Column(db.Float)   # °C
    humidity      = db.Column(db.Float)   # %
    vibration     = db.Column(db.Float)   # Hz
    tilt          = db.Column(db.Float)   # degrees
    liquid_level  = db.Column(db.Float)   # cm
    flame_detected = db.Column(db.Boolean, default=False)
    sound_level   = db.Column(db.Float)   # dB
    risk_score    = db.Column(db.Float)
    prediction_minutes = db.Column(db.Float)  # minutes until unsafe
    status        = db.Column(db.String(20))  # SAFE / WARNING / CRITICAL

class Worker(db.Model):
    __tablename__ = 'workers'
    id          = db.Column(db.Integer, primary_key=True)
    rfid_uid    = db.Column(db.String(50), unique=True, nullable=False)
    name        = db.Column(db.String(100))
    role        = db.Column(db.String(50))
    department  = db.Column(db.String(50))
    is_inside   = db.Column(db.Boolean, default=False)
    last_entry  = db.Column(db.DateTime)
    last_exit   = db.Column(db.DateTime)
    photo_url   = db.Column(db.String(200))

class Alert(db.Model):
    __tablename__ = 'alerts'
    id          = db.Column(db.Integer, primary_key=True)
    zone_id     = db.Column(db.String(50))
    timestamp   = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    alert_type  = db.Column(db.String(50))   # GAS / FIRE / STRUCTURAL / EVACUATION
    severity    = db.Column(db.String(20))   # LOW / MEDIUM / HIGH / CRITICAL
    message     = db.Column(db.Text)
    resolved    = db.Column(db.Boolean, default=False)
    resolved_at = db.Column(db.DateTime)

class Zone(db.Model):
    __tablename__ = 'zones'
    id          = db.Column(db.Integer, primary_key=True)
    zone_id     = db.Column(db.String(50), unique=True)
    name        = db.Column(db.String(100))
    zone_type   = db.Column(db.String(50))   # FACTORY / SEWAGE / CHEMICAL / CONFINED
    location    = db.Column(db.String(200))
    capacity    = db.Column(db.Integer)
    is_active   = db.Column(db.Boolean, default=True)

# ─── AI Risk Engine ───────────────────────────────────────────────────────────

from risk_engine import RiskEngine
risk_engine = RiskEngine()

# ─── MQTT Setup ───────────────────────────────────────────────────────────────

MQTT_BROKER = os.getenv('MQTT_BROKER', 'localhost')
MQTT_PORT   = int(os.getenv('MQTT_PORT', 1883))
MQTT_TOPIC  = 'msihps/sensors/#'

def on_mqtt_message(client, userdata, msg):
    """Handle incoming sensor data from ESP32 via MQTT"""
    try:
        topic = msg.topic  # e.g., msihps/sensors/zone_01
        zone_id = topic.split('/')[-1]
        data = json.loads(msg.payload.decode())

        with app.app_context():
            # Calculate AI risk score
            risk_result = risk_engine.calculate_risk(data)

            reading = SensorReading(
                zone_id=zone_id,
                mq2=data.get('mq2', 0),
                mq135=data.get('mq135', 0),
                temperature=data.get('temperature', 25),
                humidity=data.get('humidity', 50),
                vibration=data.get('vibration', 0),
                tilt=data.get('tilt', 0),
                liquid_level=data.get('liquid_level', 0),
                flame_detected=data.get('flame', False),
                sound_level=data.get('sound', 0),
                risk_score=risk_result['score'],
                prediction_minutes=risk_result['prediction_minutes'],
                status=risk_result['status']
            )
            db.session.add(reading)

            # Create alert if needed
            if risk_result['score'] >= 70:
                alert = Alert(
                    zone_id=zone_id,
                    alert_type=risk_result['alert_type'],
                    severity='CRITICAL' if risk_result['score'] >= 85 else 'HIGH',
                    message=risk_result['message']
                )
                db.session.add(alert)

            db.session.commit()

            # Broadcast to all dashboard clients via WebSocket
            payload = {
                'zone_id': zone_id,
                'sensors': data,
                'risk': risk_result,
                'timestamp': datetime.datetime.utcnow().isoformat()
            }
            socketio.emit('sensor_update', payload, namespace='/')

            # If critical — send evacuation command back to ESP32
            if risk_result['score'] >= 70:
                mqtt_client.publish(
                    f'msihps/commands/{zone_id}',
                    json.dumps({'command': 'EVACUATE', 'buzzer': True, 'led': 'RED'})
                )

    except Exception as e:
        print(f"[MQTT ERROR] {e}")

mqtt_client = mqtt.Client()
mqtt_client.on_message = on_mqtt_message

def start_mqtt():
    try:
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
        mqtt_client.subscribe(MQTT_TOPIC)
        mqtt_client.loop_forever()
    except Exception as e:
        print(f"[MQTT CONNECTION FAILED] {e} — running without MQTT")

# ─── REST API Routes ──────────────────────────────────────────────────────────

@app.route('/api/health')
def health():
    return jsonify({'status': 'ok', 'version': '1.0.0'})

@app.route('/api/zones', methods=['GET'])
def get_zones():
    zones = Zone.query.all()
    return jsonify([{
        'zone_id': z.zone_id, 'name': z.name,
        'type': z.zone_type, 'location': z.location,
        'capacity': z.capacity, 'active': z.is_active
    } for z in zones])

@app.route('/api/zones/<zone_id>/latest', methods=['GET'])
def get_latest_reading(zone_id):
    reading = SensorReading.query.filter_by(zone_id=zone_id)\
        .order_by(SensorReading.timestamp.desc()).first()
    if not reading:
        return jsonify({'error': 'No data'}), 404
    return jsonify(serialize_reading(reading))

@app.route('/api/zones/<zone_id>/history', methods=['GET'])
def get_history(zone_id):
    hours = int(request.args.get('hours', 1))
    since = datetime.datetime.utcnow() - datetime.timedelta(hours=hours)
    readings = SensorReading.query.filter(
        SensorReading.zone_id == zone_id,
        SensorReading.timestamp >= since
    ).order_by(SensorReading.timestamp.asc()).all()
    return jsonify([serialize_reading(r) for r in readings])

@app.route('/api/dashboard/summary', methods=['GET'])
def dashboard_summary():
    """Summary for all zones — used by dashboard home"""
    zones = Zone.query.filter_by(is_active=True).all()
    summary = []
    for z in zones:
        latest = SensorReading.query.filter_by(zone_id=z.zone_id)\
            .order_by(SensorReading.timestamp.desc()).first()
        workers_inside = Worker.query.filter_by(is_inside=True).count()
        active_alerts = Alert.query.filter_by(zone_id=z.zone_id, resolved=False).count()
        summary.append({
            'zone_id': z.zone_id,
            'name': z.name,
            'type': z.zone_type,
            'risk_score': latest.risk_score if latest else 0,
            'status': latest.status if latest else 'SAFE',
            'workers_inside': workers_inside,
            'active_alerts': active_alerts,
            'last_update': latest.timestamp.isoformat() if latest else None
        })
    return jsonify(summary)

@app.route('/api/rfid/scan', methods=['POST'])
def rfid_scan():
    """Called by ESP32 when worker scans RFID"""
    data = request.json
    rfid_uid = data.get('rfid_uid')
    zone_id  = data.get('zone_id')
    action   = data.get('action', 'entry')  # entry or exit

    worker = Worker.query.filter_by(rfid_uid=rfid_uid).first()
    if not worker:
        return jsonify({'access': False, 'reason': 'Unknown worker'}), 403

    # Check current risk score
    latest = SensorReading.query.filter_by(zone_id=zone_id)\
        .order_by(SensorReading.timestamp.desc()).first()
    
    if latest and latest.risk_score >= 70 and action == 'entry':
        return jsonify({
            'access': False,
            'reason': f'Zone unsafe. Risk: {latest.risk_score:.0f}/100. Predicted unsafe in {latest.prediction_minutes:.0f} min.',
            'risk_score': latest.risk_score,
            'command': {'buzzer': True, 'led': 'RED'}
        }), 403

    # Grant access
    if action == 'entry':
        worker.is_inside = True
        worker.last_entry = datetime.datetime.utcnow()
    else:
        worker.is_inside = False
        worker.last_exit = datetime.datetime.utcnow()
    
    db.session.commit()

    # Notify dashboard
    socketio.emit('worker_update', {
        'worker_id': worker.id,
        'name': worker.name,
        'zone_id': zone_id,
        'action': action,
        'timestamp': datetime.datetime.utcnow().isoformat()
    })

    return jsonify({
        'access': True,
        'worker': {'name': worker.name, 'role': worker.role},
        'command': {'buzzer': False, 'led': 'GREEN'}
    })

@app.route('/api/alerts', methods=['GET'])
def get_alerts():
    resolved = request.args.get('resolved', 'false') == 'true'
    alerts = Alert.query.filter_by(resolved=resolved)\
        .order_by(Alert.timestamp.desc()).limit(50).all()
    return jsonify([{
        'id': a.id, 'zone_id': a.zone_id,
        'type': a.alert_type, 'severity': a.severity,
        'message': a.message, 'timestamp': a.timestamp.isoformat(),
        'resolved': a.resolved
    } for a in alerts])

@app.route('/api/alerts/<int:alert_id>/resolve', methods=['POST'])
def resolve_alert(alert_id):
    alert = Alert.query.get_or_404(alert_id)
    alert.resolved = True
    alert.resolved_at = datetime.datetime.utcnow()
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/simulate', methods=['POST'])
def simulate_sensor():
    """Inject simulated sensor data for demo purposes"""
    data = request.json
    zone_id = data.get('zone_id', 'zone_01')
    risk_result = risk_engine.calculate_risk(data)
    
    with app.app_context():
        reading = SensorReading(
            zone_id=zone_id,
            mq2=data.get('mq2', 0),
            mq135=data.get('mq135', 0),
            temperature=data.get('temperature', 25),
            humidity=data.get('humidity', 50),
            vibration=data.get('vibration', 0),
            tilt=data.get('tilt', 0),
            liquid_level=data.get('liquid_level', 0),
            flame_detected=data.get('flame', False),
            sound_level=data.get('sound', 0),
            risk_score=risk_result['score'],
            prediction_minutes=risk_result['prediction_minutes'],
            status=risk_result['status']
        )
        db.session.add(reading)
        db.session.commit()

    socketio.emit('sensor_update', {
        'zone_id': zone_id,
        'sensors': data,
        'risk': risk_result,
        'timestamp': datetime.datetime.utcnow().isoformat()
    })
    return jsonify({'success': True, 'risk': risk_result})

@app.route('/api/workers', methods=['GET'])
def get_workers():
    workers = Worker.query.all()
    return jsonify([{
        'id': w.id, 'name': w.name, 'role': w.role,
        'department': w.department, 'rfid_uid': w.rfid_uid,
        'is_inside': w.is_inside,
        'last_entry': w.last_entry.isoformat() if w.last_entry else None
    } for w in workers])

# ─── WebSocket Events ─────────────────────────────────────────────────────────

@socketio.on('connect')
def on_connect():
    print(f"[WS] Client connected")
    emit('connected', {'message': 'AI-MSIHPS Dashboard Connected'})

@socketio.on('subscribe_zone')
def subscribe_zone(data):
    zone_id = data.get('zone_id')
    print(f"[WS] Client subscribed to zone: {zone_id}")

# ─── Helpers ──────────────────────────────────────────────────────────────────

def serialize_reading(r):
    return {
        'id': r.id, 'zone_id': r.zone_id,
        'timestamp': r.timestamp.isoformat(),
        'mq2': r.mq2, 'mq135': r.mq135,
        'temperature': r.temperature, 'humidity': r.humidity,
        'vibration': r.vibration, 'tilt': r.tilt,
        'liquid_level': r.liquid_level,
        'flame': r.flame_detected, 'sound': r.sound_level,
        'risk_score': r.risk_score,
        'prediction_minutes': r.prediction_minutes,
        'status': r.status
    }

def seed_db():
    """Add sample zones and workers for demo"""
    if not Zone.query.first():
        zones = [
            Zone(zone_id='zone_01', name='Chemical Storage A', zone_type='CHEMICAL', location='Block A, Floor 1', capacity=5),
            Zone(zone_id='zone_02', name='Sewage Pit B', zone_type='SEWAGE', location='Underground Level 2', capacity=3),
            Zone(zone_id='zone_03', name='Boiler Room C', zone_type='FACTORY', location='Block C, Floor 0', capacity=4),
            Zone(zone_id='zone_04', name='Confined Tank D', zone_type='CONFINED', location='Storage Yard', capacity=2),
        ]
        workers = [
            Worker(rfid_uid='A1B2C3D4', name='Rajan Kumar', role='Safety Officer', department='Operations'),
            Worker(rfid_uid='E5F6G7H8', name='Priya Sharma', role='Technician', department='Maintenance'),
            Worker(rfid_uid='I9J0K1L2', name='Suresh Patel', role='Supervisor', department='Chemical'),
        ]
        db.session.add_all(zones + workers)
        db.session.commit()
        print("[DB] Seeded with sample data")

# ─── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        seed_db()

    # Start MQTT in background thread
    mqtt_thread = threading.Thread(target=start_mqtt, daemon=True)
    mqtt_thread.start()

    print("[SERVER] AI-MSIHPS Backend starting on port 5000...")
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)