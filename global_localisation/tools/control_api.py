"""
Control API for the frontend team.
Allows starting/stopping the localisation system remotely via HTTP.

Run as a service on the Jetson — always on.
Endpoints:
  POST /start   → stop FTP service, start main.py
  POST /stop    → stop main.py, restart FTP service
  GET  /status  → returns current state
"""

import subprocess
import os
import signal
from flask import Flask, jsonify

app = Flask(__name__)

main_process = None


def is_running():
    return main_process is not None and main_process.poll() is None


@app.route("/start", methods=["POST"])
def start():
    global main_process

    if is_running():
        return jsonify({"status": "already_running"}), 200

    subprocess.run(["sudo", "systemctl", "stop", "camera-ftp"], check=False)

    env = os.environ.copy()
    env["PYTHONPATH"] = "/opt/ros/humble/lib/python3.10/site-packages"

    main_process = subprocess.Popen(
        ["/home/jetson/RoboticsProject_1/global_localisation/.venv/bin/python", "main.py"],
        cwd="/home/jetson/RoboticsProject_1/global_localisation",
        env=env,
    )

    return jsonify({"status": "started"}), 200


@app.route("/stop", methods=["POST"])
def stop():
    global main_process

    if not is_running():
        subprocess.run(["sudo", "systemctl", "start", "camera-ftp"], check=False)
        return jsonify({"status": "not_running"}), 200

    main_process.send_signal(signal.SIGINT)
    main_process.wait(timeout=10)
    main_process = None

    subprocess.run(["sudo", "systemctl", "start", "camera-ftp"], check=False)

    return jsonify({"status": "stopped"}), 200


@app.route("/status", methods=["GET"])
def status():
    return jsonify({
        "localisation": "running" if is_running() else "stopped",
        "ftp": "stopped" if is_running() else "running",
    }), 200


if __name__ == "__main__":
    print("Control API → http://0.0.0.0:8081")
    app.run(host="0.0.0.0", port=8081)
