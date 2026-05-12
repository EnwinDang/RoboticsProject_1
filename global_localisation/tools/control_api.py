"""
Control API for the frontend team.
Allows starting/stopping the localisation system via:
  - HTTP API on port 8081
  - MQTT topic city/control on HiveMQ cloud

Endpoints:
  POST /start   → start main.py
  POST /stop    → stop main.py
  GET  /status  → returns current state

MQTT:
  Subscribe: city/control
  Payload: {"action": "start"} or {"action": "stop"}
"""

import json
import os
import signal
import subprocess
import threading

import paho.mqtt.client as mqtt
from flask import Flask, jsonify, request

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import MQTT_BROKER, MQTT_PORT, MQTT_TLS, MQTT_USERNAME, MQTT_PASSWORD

VENV_PYTHON = "/home/jetson/RoboticsProject_1/global_localisation/.venv/bin/python"
WORK_DIR = "/home/jetson/RoboticsProject_1/global_localisation"
CONTROL_TOPIC = "city/control"
API_KEY = os.getenv("API_KEY", "")

app = Flask(__name__)
main_process = None


def is_running():
    return main_process is not None and main_process.poll() is None


def authorized():
    if not API_KEY:
        return True  # no key set → open access
    return request.headers.get("X-API-Key") == API_KEY


def do_start():
    global main_process
    if is_running():
        return "already_running"
    main_process = subprocess.Popen(
        ["bash", "-c", f"source /opt/ros/humble/setup.bash && {VENV_PYTHON} main.py"],
        cwd=WORK_DIR,
    )
    return "started"


def do_stop():
    global main_process
    if not is_running():
        return "not_running"
    main_process.send_signal(signal.SIGINT)
    main_process.wait(timeout=10)
    main_process = None
    return "stopped"


# --- HTTP API ---

@app.route("/start", methods=["POST"])
def start():
    if not authorized():
        return jsonify({"error": "unauthorized"}), 401
    return jsonify({"status": do_start()}), 200


@app.route("/stop", methods=["POST"])
def stop():
    if not authorized():
        return jsonify({"error": "unauthorized"}), 401
    return jsonify({"status": do_stop()}), 200


@app.route("/status", methods=["GET"])
def status():
    return jsonify({
        "localisation": "running" if is_running() else "stopped",
        "ftp": "stopped" if is_running() else "running",
    }), 200


# --- MQTT control ---

def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        action = payload.get("action")
        if action == "start":
            result = do_start()
            print(f"[MQTT] start → {result}")
        elif action == "stop":
            result = do_stop()
            print(f"[MQTT] stop → {result}")
        else:
            print(f"[MQTT] unknown action: {action}")
    except Exception as e:
        print(f"[MQTT] error: {e}")


def start_mqtt_listener():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    if MQTT_TLS:
        client.tls_set()
    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    client.on_message = on_message
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
        client.subscribe(CONTROL_TOPIC)
        print(f"[MQTT] Listening on {CONTROL_TOPIC}")
        client.loop_forever()
    except Exception as e:
        print(f"[MQTT] Connection failed: {e}")


if __name__ == "__main__":
    t = threading.Thread(target=start_mqtt_listener, daemon=True)
    t.start()

    print("Control API → http://0.0.0.0:8081")
    print(f"MQTT control → {MQTT_BROKER} topic: {CONTROL_TOPIC}")
    app.run(host="0.0.0.0", port=8081)
