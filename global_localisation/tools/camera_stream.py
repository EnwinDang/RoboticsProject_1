"""
Live dual-camera stream viewable in browser.
Run on Jetson: python tools/camera_stream.py
Then open: http://jetson-dang.local:8080
"""
import sys
import os
import threading
import cv2
import cv2.aruco as aruco
import numpy as np
from flask import Flask, Response

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import CAMERA_INDEX_1, CAMERA_INDEX_2, CALIBRATION_IDS, CAMERA_WIDTH, CAMERA_HEIGHT

app = Flask(__name__)

aruco_dict = aruco.getPredefinedDictionary(aruco.DICT_4X4_50)
aruco_params = aruco.DetectorParameters()
aruco_params.adaptiveThreshWinSizeMin = 3
aruco_params.adaptiveThreshWinSizeMax = 23
aruco_params.adaptiveThreshWinSizeStep = 10
detector = aruco.ArucoDetector(aruco_dict, aruco_params)

PANEL_WIDTH = 480
PANEL_HEIGHT = 640
TOTAL_WIDTH = PANEL_WIDTH * 2
TOTAL_HEIGHT = PANEL_HEIGHT

CROP_LEFT = (0.0, 1.0, 0.0, 1.0)
CROP_RIGHT = (0.0, 1.0, 0.0, 1.0)
ROTATE_LEFT_DEGREES = 90.0
ROTATE_RIGHT_DEGREES = -90.0

def open_camera(index):
    cap = cv2.VideoCapture(index, cv2.CAP_V4L2)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
    return cap

cap1 = open_camera(CAMERA_INDEX_1)
cap2 = open_camera(CAMERA_INDEX_2)

latest_frame = None
frame_lock = threading.Lock()


def detect_and_draw(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    corners, ids, _ = detector.detectMarkers(gray)
    if ids is not None:
        for i, corner in enumerate(corners):
            marker_id = int(ids[i][0])
            color = (0, 0, 255) if marker_id in CALIBRATION_IDS else (0, 255, 0)
            pts = corner[0].astype(int)
            cv2.polylines(frame, [pts], isClosed=True, color=color, thickness=3)
            cv2.putText(frame, str(marker_id), tuple(pts[0]), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
    return frame


def crop_frame(frame, crop_box):
    x0, x1, y0, y1 = crop_box
    height, width = frame.shape[:2]
    left = max(0, int(width * x0))
    right = min(width, int(width * x1))
    top = max(0, int(height * y0))
    bottom = min(height, int(height * y1))
    return frame[top:bottom, left:right]


def rotate_frame(frame, degrees):
    if frame is None:
        return None
    height, width = frame.shape[:2]
    center = (width / 2.0, height / 2.0)
    matrix = cv2.getRotationMatrix2D(center, degrees, 1.0)
    new_w, new_h = (height, width) if abs(degrees) == 90.0 else (width, height)
    matrix[0, 2] += (new_w - width) / 2
    matrix[1, 2] += (new_h - height) / 2
    return cv2.warpAffine(frame, matrix, (new_w, new_h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)


def compose_frame(frame1, frame2):
    canvas = np.zeros((TOTAL_HEIGHT, TOTAL_WIDTH, 3), dtype=np.uint8)

    if frame1 is not None:
        left = crop_frame(frame1, CROP_LEFT)
        left = rotate_frame(left, ROTATE_LEFT_DEGREES)
        left = cv2.resize(left, (PANEL_WIDTH, PANEL_HEIGHT))
        canvas[0:PANEL_HEIGHT, 0:PANEL_WIDTH] = left

    if frame2 is not None:
        right = crop_frame(frame2, CROP_RIGHT)
        right = rotate_frame(right, ROTATE_RIGHT_DEGREES)
        right = cv2.resize(right, (PANEL_WIDTH, PANEL_HEIGHT))
        canvas[0:PANEL_HEIGHT, PANEL_WIDTH:TOTAL_WIDTH] = right

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

    print(f"Streaming cameras {CAMERA_INDEX_1} + {CAMERA_INDEX_2} → http://0.0.0.0:8080")
    app.run(host="0.0.0.0", port=8080)
