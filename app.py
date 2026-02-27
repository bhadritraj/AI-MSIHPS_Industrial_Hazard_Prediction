from flask import Flask, request, jsonify, send_from_directory
from flask_socketio import SocketIO

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

latest_data = {}

@app.route('/data', methods=['POST'])
def receive_data():
    global latest_data
    data = request.get_json()

    if data:
        latest_data = data
        socketio.emit('sensor_update', data)
        return jsonify({"status": "ok"}), 200

    return jsonify({"status": "error"}), 400


# 🔥 ADD THIS
@app.route('/latest', methods=['GET'])
def get_latest():
    return jsonify(latest_data)


@app.route('/')
def index():
    return send_from_directory('.', 'index.html')




if __name__ == '__main__':
    socketio.run(app, allow_unsafe_werkzeug= True, host='0.0.0.0', port=5000)