"""
Live camera stream viewable in browser.
Run on Jetson: python tools/camera_stream.py
Then open: http://jetson-dang.local:8080
"""
import threading
import cv2
import cv2.aruco as aruco
import numpy as np
from flask import Flask, Response
from config import CAMERA_INDEX_1, CAMERA_INDEX_2

app = Flask(__name__)

aruco_dict = aruco.getPredefinedDictionary(aruco.DICT_4X4_50)
aruco_params = aruco.DetectorParameters()
aruco_params.adaptiveThreshWinSizeMin = 3
aruco_params.adaptiveThreshWinSizeMax = 23
aruco_params.adaptiveThreshWinSizeStep = 10
detector = aruco.ArucoDetector(aruco_dict, aruco_params)

PANEL_WIDTH = 960
PANEL_HEIGHT = 540
TOTAL_WIDTH = PANEL_WIDTH * 2
TOTAL_HEIGHT = PANEL_HEIGHT
LABEL_STYLE = cv2.FONT_HERSHEY_SIMPLEX

cap1 = cv2.VideoCapture(CAMERA_INDEX_1, cv2.CAP_V4L2)
cap2 = cv2.VideoCapture(CAMERA_INDEX_2, cv2.CAP_V4L2)

latest_frame = None
frame_lock = threading.Lock()


def detect_and_draw(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    corners, ids, _ = detector.detectMarkers(gray)
    if ids is not None:
        aruco.drawDetectedMarkers(frame, corners, ids)
    return frame


def compose_frame(frame1, frame2):
    canvas = np.zeros((TOTAL_HEIGHT, TOTAL_WIDTH, 3), dtype=np.uint8)

    if frame1 is not None:
        left = cv2.resize(frame1, (PANEL_WIDTH, PANEL_HEIGHT))
        canvas[0:PANEL_HEIGHT, 0:PANEL_WIDTH] = left
        cv2.rectangle(canvas, (12, 12), (320, 58), (0, 0, 0), -1)
        cv2.putText(canvas, "LEFT", (20, 45), LABEL_STYLE, 1.0, (255, 255, 255), 2, cv2.LINE_AA)

    if frame2 is not None:
        right = cv2.resize(frame2, (PANEL_WIDTH, PANEL_HEIGHT))
        canvas[0:PANEL_HEIGHT, PANEL_WIDTH:TOTAL_WIDTH] = right
        cv2.rectangle(canvas, (PANEL_WIDTH + 12, 12), (PANEL_WIDTH + 320, 58), (0, 0, 0), -1)
        cv2.putText(canvas, "RIGHT", (PANEL_WIDTH + 20, 45), LABEL_STYLE, 1.0, (255, 255, 255), 2, cv2.LINE_AA)

    return canvas


def capture_loop():
    global latest_frame
    while True:
        ret1, frame1 = cap1.read()
        ret2, frame2 = cap2.read()

        if ret1:
            frame1 = detect_and_draw(frame1)
        else:
            frame1 = None

        if ret2:
            frame2 = detect_and_draw(frame2)
        else:
            frame2 = None

        combined = compose_frame(frame1, frame2)
        if combined is None:
            continue

        with frame_lock:
            latest_frame = combined


def generate_frames():
    while True:
        with frame_lock:
            frame = latest_frame
        if frame is None:
            continue
        _, buffer = cv2.imencode(".jpg", frame)
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

    t = threading.Thread(target=capture_loop, daemon=True)
    t.start()

    print(f"Streaming camera {CAMERA_INDEX_1} with camera {CAMERA_INDEX_2} overlay → http://0.0.0.0:8080")
    app.run(host="0.0.0.0", port=8080)
