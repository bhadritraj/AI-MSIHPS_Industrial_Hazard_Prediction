from flask import Flask, request, jsonify, send_from_directory
from flask_socketio import SocketIO
import pickle
import numpy as np

# ---------------- APP INIT ----------------
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

latest_data = {}

# ---------------- LOAD AI MODEL ----------------
try:
    rf_model = pickle.load(open("rf_classifier.pkl", "rb"))
    scaler = pickle.load(open("scaler.pkl", "rb"))
    print("AI Model Loaded Successfully")
except Exception as e:
    print("Model loading failed:", e)
    rf_model = None
    scaler = None


# ---------------- AI PREDICTION FUNCTION ----------------
def predict_risk(sensor_data):

    if rf_model is None or scaler is None:
        return 0, "SAFE"

    try:
        features = np.array([[
            sensor_data.get("mq2", 0),
            sensor_data.get("mq7", 0),
            sensor_data.get("mq135", 0),
            sensor_data.get("sound", 0),
            1 if sensor_data.get("flame", 0) else 0,
            sensor_data.get("temperature", 25),
            sensor_data.get("humidity", 50),
            sensor_data.get("liquid", 0),
            sensor_data.get("vibration", 0),
            sensor_data.get("tilt", 0)
        ]])

        # Scale input
        scaled = scaler.transform(features)

        # Predict class
        prediction = rf_model.predict(scaled)[0]

        labels = ["SAFE", "WARNING", "CRITICAL"]

        # Convert class → risk score
        risk_map = {
            0: 25,
            1: 55,
            2: 85
        }

        return risk_map[int(prediction)], labels[int(prediction)]

    except Exception as e:
        print("Prediction error:", e)
        return 0, "SAFE"


# ---------------- RECEIVE SENSOR DATA ----------------
@app.route('/data', methods=['POST'])
def receive_data():
    global latest_data

    data = request.get_json()

    if data:

        # AI MODEL PREDICTION
        risk_score, hazard_level = predict_risk(data)

        latest_data = {
            "risk_score": risk_score,
            "hazard_level": hazard_level,
            "sensors": data
        }

        print("AI Output:", latest_data)

        socketio.emit('sensor_update', latest_data)

        return jsonify({"status": "ok"}), 200

    return jsonify({"status": "error"}), 400


# ---------------- SEND LATEST AI RESULT ----------------
@app.route('/latest', methods=['GET'])
def get_latest():
    return jsonify(latest_data)


# ---------------- FRONTEND ----------------
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')


# ---------------- RUN SERVER ----------------
if __name__ == '__main__':
    socketio.run(
        app,
        allow_unsafe_werkzeug=True,
        host='0.0.0.0',
        port=5000
    )