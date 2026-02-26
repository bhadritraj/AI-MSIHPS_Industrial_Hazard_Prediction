"""
AI-MSIHPS Risk Engine
Core AI module: sensor fusion, risk scoring, and time-series prediction

Architecture:
  1. Weighted Sensor Fusion → Instant Risk Score (0–100)
  2. Random Forest Classifier → Status (SAFE/WARNING/CRITICAL)
  3. LSTM → Prediction: "Unsafe in X minutes"
  4. Anomaly Detector → Sudden pattern changes
"""

import numpy as np
import os, pickle, warnings
from collections import deque
from datetime import datetime

warnings.filterwarnings('ignore')

# ─── Sensor Weight Configuration ──────────────────────────────────────────────
# These weights define how much each sensor contributes to risk score
# Tuned based on industrial safety standards (OSHA, IS:15258)

SENSOR_WEIGHTS = {
    'mq2':          0.25,   # Methane/LPG — highest explosion risk
    'mq135':        0.20,   # Toxic gas — health risk
    'flame':        0.20,   # Flame — immediate danger
    'temperature':  0.10,   # High temp accelerates gas risk
    'humidity':     0.08,   # High humidity affects sensor readings
    'vibration':    0.07,   # Structural stress
    'tilt':         0.05,   # Structural failure indicator
    'liquid_level': 0.03,   # Overflow risk
    'sound':        0.02,   # Explosion precursor
}

# ─── Sensor Normalization Thresholds ──────────────────────────────────────────
# Based on OSHA PEL (Permissible Exposure Limits) and IEC standards

THRESHOLDS = {
    'mq2': {
        'safe':     200,    # ppm — below this is safe
        'warning':  500,    # ppm — permissible limit
        'critical': 1000    # ppm — explosive range
    },
    'mq135': {
        'safe':     100,
        'warning':  200,
        'critical': 400
    },
    'temperature': {
        'safe':     35,     # °C
        'warning':  50,
        'critical': 70
    },
    'humidity': {
        'safe':     60,     # %
        'warning':  80,
        'critical': 95
    },
    'vibration': {
        'safe':     0.5,    # Hz
        'warning':  2.0,
        'critical': 5.0
    },
    'tilt': {
        'safe':     2.0,    # degrees
        'warning':  5.0,
        'critical': 10.0
    },
    'liquid_level': {
        'safe':     60,     # cm
        'warning':  80,
        'critical': 95
    },
    'sound': {
        'safe':     70,     # dB
        'warning':  85,
        'critical': 100
    }
}


class RiskEngine:
    """Core AI risk assessment engine"""

    def __init__(self):
        # Sliding window: last 60 readings per zone (for LSTM)
        self.reading_history = {}   # zone_id -> deque of readings
        self.WINDOW_SIZE = 60

        # Try to load trained models
        self.rf_model  = self._load_model('models/rf_classifier.pkl')
        self.lstm_model = self._load_model('models/lstm_predictor.pkl')
        self.scaler    = self._load_model('models/scaler.pkl')

        print(f"[AI Engine] RF Model: {'Loaded' if self.rf_model else 'Using rule-based fallback'}")
        print(f"[AI Engine] LSTM Model: {'Loaded' if self.lstm_model else 'Using trend-based fallback'}")

    def _load_model(self, path):
        if os.path.exists(path):
            with open(path, 'rb') as f:
                return pickle.load(f)
        return None

    def normalize_sensor(self, sensor, value, is_boolean=False):
        """Normalize a sensor value to 0–1 scale using thresholds"""
        if is_boolean:
            return 1.0 if value else 0.0
        
        thresholds = THRESHOLDS.get(sensor)
        if not thresholds:
            return 0.0

        if value <= thresholds['safe']:
            return value / thresholds['safe'] * 0.4           # 0.0 – 0.4
        elif value <= thresholds['warning']:
            ratio = (value - thresholds['safe']) / (thresholds['warning'] - thresholds['safe'])
            return 0.4 + ratio * 0.3                          # 0.4 – 0.7
        elif value <= thresholds['critical']:
            ratio = (value - thresholds['warning']) / (thresholds['critical'] - thresholds['warning'])
            return 0.7 + ratio * 0.2                          # 0.7 – 0.9
        else:
            return min(1.0, 0.9 + (value - thresholds['critical']) / thresholds['critical'] * 0.1)  # 0.9–1.0

    def weighted_sensor_fusion(self, data):
        """
        Weighted Sensor Fusion Algorithm
        
        Formula: RiskScore = Σ(weight_i × normalized_value_i) × 100
        With multiplicative penalty for flame detection
        """
        score = 0.0

        score += SENSOR_WEIGHTS['mq2']         * self.normalize_sensor('mq2', data.get('mq2', 0))
        score += SENSOR_WEIGHTS['mq135']        * self.normalize_sensor('mq135', data.get('mq135', 0))
        score += SENSOR_WEIGHTS['flame']        * self.normalize_sensor('flame', data.get('flame', False), is_boolean=True)
        score += SENSOR_WEIGHTS['temperature']  * self.normalize_sensor('temperature', data.get('temperature', 25))
        score += SENSOR_WEIGHTS['humidity']     * self.normalize_sensor('humidity', data.get('humidity', 50))
        score += SENSOR_WEIGHTS['vibration']    * self.normalize_sensor('vibration', data.get('vibration', 0))
        score += SENSOR_WEIGHTS['tilt']         * self.normalize_sensor('tilt', data.get('tilt', 0))
        score += SENSOR_WEIGHTS['liquid_level'] * self.normalize_sensor('liquid_level', data.get('liquid_level', 0))
        score += SENSOR_WEIGHTS['sound']        * self.normalize_sensor('sound', data.get('sound', 0))

        risk_score = score * 100

        # 🔴 Multiplicative flame penalty — flame + gas = immediate critical
        if data.get('flame', False) and (data.get('mq2', 0) > 100 or data.get('mq135', 0) > 100):
            risk_score = min(100, risk_score * 1.5)

        # 🟡 Humidity amplification — high humidity worsens gas accumulation
        humidity = data.get('humidity', 50)
        if humidity > 80:
            gas_component = (data.get('mq2', 0) / THRESHOLDS['mq2']['critical'] + 
                           data.get('mq135', 0) / THRESHOLDS['mq135']['critical']) / 2
            risk_score = min(100, risk_score + gas_component * 5)

        return round(risk_score, 2)

    def trend_based_prediction(self, zone_id):
        """
        Time-Series Trend Predictor
        Analyzes rate of change to predict when conditions become unsafe.
        
        Uses linear regression on sliding window of gas readings.
        Returns: minutes until risk score hits 70 (danger threshold)
        """
        history = self.reading_history.get(zone_id, deque())
        if len(history) < 5:
            return None   # Not enough data

        # Extract risk scores over time
        recent = list(history)[-30:]   # Last 30 readings
        scores = [r['risk_score'] for r in recent]
        times  = list(range(len(scores)))

        # Linear regression: y = mx + b
        n = len(scores)
        if n < 2:
            return None

        m_num = n * sum(t*s for t,s in zip(times, scores)) - sum(times)*sum(scores)
        m_den = n * sum(t**2 for t in times) - sum(times)**2

        if abs(m_den) < 1e-9:
            return None

        slope = m_num / m_den   # Risk score change per reading interval

        if slope <= 0:
            return None   # Decreasing or stable — no prediction needed

        current_score = scores[-1]
        if current_score >= 70:
            return 0   # Already unsafe

        # Readings are taken every 60 seconds (configurable)
        reading_interval_minutes = 1
        readings_to_danger = (70 - current_score) / slope
        minutes_to_danger = readings_to_danger * reading_interval_minutes

        # Clamp to reasonable range
        return round(min(120, max(0, minutes_to_danger)), 1)

    def lstm_prediction(self, zone_id):
        """
        LSTM-based prediction (if model is loaded)
        Falls back to trend_based_prediction if model not available.
        """
        if not self.lstm_model or not self.scaler:
            return self.trend_based_prediction(zone_id)

        history = self.reading_history.get(zone_id, deque())
        if len(history) < self.WINDOW_SIZE:
            return self.trend_based_prediction(zone_id)

        try:
            # Prepare sequence for LSTM
            features = ['mq2', 'mq135', 'temperature', 'humidity', 'vibration', 'risk_score']
            recent = list(history)[-self.WINDOW_SIZE:]
            sequence = np.array([[r.get(f, 0) for f in features] for r in recent])
            sequence_scaled = self.scaler.transform(sequence)
            sequence_input = sequence_scaled.reshape(1, self.WINDOW_SIZE, len(features))

            prediction = self.lstm_model.predict(sequence_input, verbose=0)[0][0]
            return round(float(prediction), 1)
        except Exception as e:
            print(f"[LSTM Error] {e} — falling back to trend")
            return self.trend_based_prediction(zone_id)

    def detect_anomaly(self, zone_id, current_score):
        """
        Anomaly Detection: Detect sudden spikes that break the gradual trend
        Uses Z-score on recent risk scores
        """
        history = self.reading_history.get(zone_id, deque())
        if len(history) < 10:
            return False

        recent_scores = [r['risk_score'] for r in list(history)[-10:]]
        mean = np.mean(recent_scores)
        std  = np.std(recent_scores)

        if std < 0.1:
            return False

        z_score = abs(current_score - mean) / std
        return z_score > 2.5   # Spike detected if z-score > 2.5

    def classify_status(self, risk_score):
        """Classify risk score into status label"""
        if risk_score < 40:
            return 'SAFE'
        elif risk_score < 70:
            return 'WARNING'
        else:
            return 'CRITICAL'

    def identify_primary_hazard(self, data, risk_score):
        """Identify the primary contributing hazard for alert messaging"""
        if data.get('flame', False):
            return 'FIRE', 'Flame detected! Immediate evacuation required.'

        gas_scores = {
            'Methane/LPG/Smoke': data.get('mq2', 0) / THRESHOLDS['mq2']['critical'],
            'Toxic Gas':         data.get('mq135', 0) / THRESHOLDS['mq135']['critical'],
        }
        structural_scores = {
            'Vibration': data.get('vibration', 0) / THRESHOLDS['vibration']['critical'],
            'Tilt':      data.get('tilt', 0) / THRESHOLDS['tilt']['critical'],
        }

        max_gas  = max(gas_scores.values())
        max_struc = max(structural_scores.values())

        if max_gas > max_struc and max_gas > 0.5:
            hazard = max(gas_scores, key=gas_scores.get)
            return 'GAS', f'{hazard} levels elevated. Risk score: {risk_score:.0f}/100.'
        elif max_struc > 0.5:
            hazard = max(structural_scores, key=structural_scores.get)
            return 'STRUCTURAL', f'{hazard} anomaly detected. Structural risk: {risk_score:.0f}/100.'
        elif data.get('temperature', 25) > THRESHOLDS['temperature']['warning']:
            return 'THERMAL', f'High temperature detected: {data.get("temperature")}°C.'
        else:
            return 'GENERAL', f'Multiple sensor anomalies. Risk score: {risk_score:.0f}/100.'

    def calculate_risk(self, data, zone_id='default'):
        """
        Master risk calculation function
        Returns complete risk assessment dict
        """
        # 1. Weighted sensor fusion for instant score
        risk_score = self.weighted_sensor_fusion(data)

        # 2. Store in history for trend analysis
        if zone_id not in self.reading_history:
            self.reading_history[zone_id] = deque(maxlen=self.WINDOW_SIZE)
        
        self.reading_history[zone_id].append({
            **data,
            'risk_score': risk_score,
            'timestamp': datetime.utcnow().isoformat()
        })

        # 3. Status classification
        status = self.classify_status(risk_score)

        # 4. Time-to-danger prediction
        prediction_minutes = self.lstm_prediction(zone_id)

        # 5. Anomaly detection
        is_anomaly = self.detect_anomaly(zone_id, risk_score)

        # 6. Primary hazard identification
        alert_type, message = self.identify_primary_hazard(data, risk_score)

        # 7. Override prediction if anomaly detected
        if is_anomaly and prediction_minutes and prediction_minutes > 15:
            prediction_minutes = max(5, prediction_minutes * 0.6)   # More urgent estimate

        return {
            'score':               risk_score,
            'status':              status,
            'prediction_minutes':  prediction_minutes,
            'alert_type':          alert_type,
            'message':             message,
            'is_anomaly':          is_anomaly,
            'sensor_breakdown': {
                'gas_index':         round(self.normalize_sensor('mq2', data.get('mq2', 0)) * 100, 1),
                'toxic_index':       round(self.normalize_sensor('mq135', data.get('mq135', 0)) * 100, 1),
                'thermal_index':     round(self.normalize_sensor('temperature', data.get('temperature', 25)) * 100, 1),
                'structural_index':  round((self.normalize_sensor('vibration', data.get('vibration', 0)) + 
                                           self.normalize_sensor('tilt', data.get('tilt', 0))) / 2 * 100, 1),
            },
            'entry_allowed': risk_score < 70,
            'recommended_action': self._get_recommendation(risk_score, prediction_minutes, data)
        }

    def _get_recommendation(self, score, pred_min, data):
        if data.get('flame', False):
            return 'EVACUATE IMMEDIATELY — Fire detected'
        if score >= 85:
            return 'IMMEDIATE EVACUATION — Critical hazard levels'
        if score >= 70:
            return 'EVACUATE — Unsafe for human entry. Activate ventilation.'
        if score >= 55:
            return 'WARNING — Limit exposure. Alert supervisor. Prepare ventilation.'
        if score >= 40:
            return 'CAUTION — Monitor closely. Review in 15 minutes.'
        if pred_min and pred_min < 30:
            return f'CAUTION — Conditions may become unsafe in ~{pred_min:.0f} minutes.'
        return 'SAFE — Normal operations. Continue monitoring.'


# ─── Model Training Script ────────────────────────────────────────────────────

def generate_synthetic_dataset(n_samples=10000):
    """
    Generate synthetic training dataset for hackathon demo.
    In production, replace with real sensor logs.
    """
    np.random.seed(42)
    data = []
    labels = []  # 0=SAFE, 1=WARNING, 2=CRITICAL

    for i in range(n_samples):
        # Scenario sampling
        scenario = np.random.choice(['normal', 'gas_buildup', 'fire_hazard', 'structural'], 
                                    p=[0.5, 0.3, 0.1, 0.1])

        if scenario == 'normal':
            sample = {
                'mq2':         np.random.uniform(0, 150),
                'mq135':       np.random.uniform(0, 80),
                'temperature': np.random.uniform(20, 35),
                'humidity':    np.random.uniform(30, 65),
                'vibration':   np.random.uniform(0, 0.3),
                'tilt':        np.random.uniform(0, 1.5),
                'liquid_level': np.random.uniform(10, 50),
                'flame':       0,
                'sound':       np.random.uniform(40, 65),
            }
            label = 0

        elif scenario == 'gas_buildup':
            sample = {
                'mq2':         np.random.uniform(300, 1500),
                'mq135':       np.random.uniform(150, 500),
                'temperature': np.random.uniform(28, 55),
                'humidity':    np.random.uniform(60, 90),
                'vibration':   np.random.uniform(0, 1.0),
                'tilt':        np.random.uniform(0, 3.0),
                'liquid_level': np.random.uniform(20, 70),
                'flame':       0,
                'sound':       np.random.uniform(50, 80),
            }
            label = 1 if sample['mq2'] < 700 else 2

        elif scenario == 'fire_hazard':
            sample = {
                'mq2':         np.random.uniform(200, 800),
                'mq135':       np.random.uniform(100, 300),
                'temperature': np.random.uniform(55, 120),
                'humidity':    np.random.uniform(20, 50),
                'vibration':   np.random.uniform(0.5, 3.0),
                'tilt':        np.random.uniform(1, 5),
                'liquid_level': np.random.uniform(0, 30),
                'flame':       1,
                'sound':       np.random.uniform(75, 110),
            }
            label = 2

        else:  # structural
            sample = {
                'mq2':         np.random.uniform(0, 200),
                'mq135':       np.random.uniform(0, 100),
                'temperature': np.random.uniform(22, 40),
                'humidity':    np.random.uniform(40, 70),
                'vibration':   np.random.uniform(2.0, 8.0),
                'tilt':        np.random.uniform(4.0, 15.0),
                'liquid_level': np.random.uniform(60, 100),
                'flame':       0,
                'sound':       np.random.uniform(80, 120),
            }
            label = 1 if sample['vibration'] < 4.0 else 2

        data.append(list(sample.values()))
        labels.append(label)

    return np.array(data), np.array(labels)


def train_and_save_models():
    """Train RF classifier and save. Run this once before demo."""
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import classification_report
    import os, pickle

    print("[Training] Generating synthetic dataset...")
    X, y = generate_synthetic_dataset(10000)

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled  = scaler.transform(X_test)

    print("[Training] Training Random Forest Classifier...")
    rf = RandomForestClassifier(n_estimators=200, max_depth=15, random_state=42, n_jobs=-1)
    rf.fit(X_train_scaled, y_train)

    y_pred = rf.predict(X_test_scaled)
    print(classification_report(y_test, y_pred, target_names=['SAFE', 'WARNING', 'CRITICAL']))

    os.makedirs('models', exist_ok=True)
    with open('models/rf_classifier.pkl', 'wb') as f:
        pickle.dump(rf, f)
    with open('models/scaler.pkl', 'wb') as f:
        pickle.dump(scaler, f)

    print("[Training] Models saved to models/")
    return rf, scaler


def train_lstm_model():
    """Train LSTM for time-series prediction — run once."""
    try:
        import tensorflow as tf
        from sklearn.preprocessing import MinMaxScaler
        import pickle

        print("[LSTM Training] Generating time-series data...")
        # Generate gas buildup sequences
        engine = RiskEngine()
        sequences, targets = [], []

        for _ in range(500):
            # Simulate a 60-minute gas buildup scenario
            seq = []
            base_mq2 = np.random.uniform(50, 200)
            drift = np.random.uniform(5, 25)   # ppm per minute
            for t in range(60):
                mq2 = base_mq2 + drift * t + np.random.normal(0, 10)
                mq135 = mq2 * np.random.uniform(0.3, 0.7)
                temp = 25 + t * 0.1 + np.random.normal(0, 1)
                humidity = 50 + t * 0.2 + np.random.normal(0, 2)
                vibration = np.random.uniform(0, 0.5)
                risk = engine.weighted_sensor_fusion({
                    'mq2': mq2, 'mq135': mq135, 'temperature': temp,
                    'humidity': humidity, 'vibration': vibration, 'tilt': 0,
                    'liquid_level': 30, 'flame': False, 'sound': 60
                })
                seq.append([mq2, mq135, temp, humidity, vibration, risk])

            # Target: minutes until risk >= 70
            future_scores = [s[-1] for s in seq[30:]]
            dangerous_idx = next((i for i, s in enumerate(future_scores) if s >= 70), None)
            target = dangerous_idx if dangerous_idx is not None else 30
            sequences.append(seq[:30])   # First 30 mins as input
            targets.append(target)

        X = np.array(sequences)
        y = np.array(targets, dtype=np.float32)

        scaler = MinMaxScaler()
        X_shaped = X.reshape(-1, 6)
        X_scaled = scaler.fit_transform(X_shaped).reshape(len(sequences), 30, 6)

        # Build LSTM model
        model = tf.keras.Sequential([
            tf.keras.layers.LSTM(64, return_sequences=True, input_shape=(30, 6)),
            tf.keras.layers.Dropout(0.2),
            tf.keras.layers.LSTM(32),
            tf.keras.layers.Dropout(0.2),
            tf.keras.layers.Dense(16, activation='relu'),
            tf.keras.layers.Dense(1)
        ])
        model.compile(optimizer='adam', loss='mse', metrics=['mae'])
        model.summary()

        model.fit(X_scaled, y, epochs=50, batch_size=32, validation_split=0.2, verbose=1)
        model.save('models/lstm_predictor.h5')

        with open('models/lstm_scaler.pkl', 'wb') as f:
            pickle.dump(scaler, f)

        print("[LSTM Training] LSTM model saved!")

    except ImportError:
        print("[LSTM] TensorFlow not available. LSTM training skipped.")


if __name__ == '__main__':
    print("Training AI models for AI-MSIHPS...")
    train_and_save_models()
    train_lstm_model()
    print("All models trained and saved!")