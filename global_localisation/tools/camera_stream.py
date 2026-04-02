"""
Live dual-camera stream viewable in browser.
Run on Jetson: python tools/camera_stream.py
Then open: http://jetson-dang.local:8080
"""
import sys
import os
import cv2
import cv2.aruco as aruco
from flask import Flask, Response

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import CAMERA_INDEX_1, CAMERA_INDEX_2

app = Flask(__name__)

aruco_dict = aruco.getPredefinedDictionary(aruco.DICT_4X4_50)
aruco_params = aruco.DetectorParameters()
aruco_params.adaptiveThreshWinSizeMin = 3
aruco_params.adaptiveThreshWinSizeMax = 23
aruco_params.adaptiveThreshWinSizeStep = 10
detector = aruco.ArucoDetector(aruco_dict, aruco_params)

cap1 = cv2.VideoCapture(CAMERA_INDEX_1, cv2.CAP_V4L2)
cap2 = cv2.VideoCapture(CAMERA_INDEX_2, cv2.CAP_V4L2)


def detect_and_draw(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    corners, ids, _ = detector.detectMarkers(gray)
    if ids is not None:
        aruco.drawDetectedMarkers(frame, corners, ids)
    return frame


def generate_frames():
    while True:
        ret1, frame1 = cap1.read()
        ret2, frame2 = cap2.read()

        if ret1:
            frame1 = detect_and_draw(frame1)
        if ret2:
            frame2 = detect_and_draw(frame2)

        if ret1 and ret2:
            combined = cv2.hconcat([frame1, frame2])
        elif ret1:
            combined = frame1
        elif ret2:
            combined = frame2
        else:
            continue

        _, buffer = cv2.imencode(".jpg", combined)
        yield (b"--frame\r\n"
               b"Content-Type: image/jpeg\r\n\r\n" + buffer.tobytes() + b"\r\n")


@app.route("/")
def index():
    return '<html><body style="background:#000;margin:0"><img src="/video" style="width:100%"></body></html>'


@app.route("/video")
def video():
    return Response(generate_frames(), mimetype="multipart/x-mixed-replace; boundary=frame")


if __name__ == "__main__":
    if not cap1.isOpened():
        print(f"Error: Could not open camera {CAMERA_INDEX_1}")
    if not cap2.isOpened():
        print(f"Error: Could not open camera {CAMERA_INDEX_2}")
    if not cap1.isOpened() and not cap2.isOpened():
        raise SystemExit(1)

    print(f"Streaming cameras {CAMERA_INDEX_1} + {CAMERA_INDEX_2} → http://0.0.0.0:8080")
    app.run(host="0.0.0.0", port=8080)
