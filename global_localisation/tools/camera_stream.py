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

PANEL_WIDTH = 640   # 2 panels = 1280 total width
PANEL_HEIGHT = 720
TOTAL_WIDTH = PANEL_WIDTH * 2
TOTAL_HEIGHT = PANEL_HEIGHT

ROTATE_LEFT_DEGREES = 90.0
ROTATE_RIGHT_DEGREES = -90.0
CROP_PADDING = 0.05  # 5% padding around calibration markers

# Cached crop regions per camera (x0, x1, y0, y1) in pixel coords
crop_box1 = None
crop_box2 = None

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
    calib_corners = []
    if ids is not None:
        for i, corner in enumerate(corners):
            marker_id = int(ids[i][0])
            color = (0, 0, 255) if marker_id in CALIBRATION_IDS else (0, 255, 0)
            pts = corner[0].astype(int)
            cv2.polylines(frame, [pts], isClosed=True, color=color, thickness=3)
            cv2.putText(frame, str(marker_id), tuple(pts[0]), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
            if marker_id in CALIBRATION_IDS:
                calib_corners.append(corner[0])
    return frame, calib_corners


def compute_crop_box(calib_corners, frame_shape):
    if not calib_corners:
        return None
    h, w = frame_shape[:2]
    all_pts = np.concatenate(calib_corners, axis=0)
    x0 = max(0, int(all_pts[:, 0].min() - w * CROP_PADDING))
    x1 = min(w, int(all_pts[:, 0].max() + w * CROP_PADDING))
    y0 = max(0, int(all_pts[:, 1].min() - h * CROP_PADDING))
    y1 = min(h, int(all_pts[:, 1].max() + h * CROP_PADDING))
    return (x0, x1, y0, y1)


def crop_frame(frame, box):
    if box is None:
        return frame
    x0, x1, y0, y1 = box
    return frame[y0:y1, x0:x1]


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
        left = crop_frame(frame1, crop_box1)
        left = rotate_frame(left, ROTATE_LEFT_DEGREES)
        left = cv2.resize(left, (PANEL_WIDTH, PANEL_HEIGHT))
        canvas[0:PANEL_HEIGHT, 0:PANEL_WIDTH] = left

    if frame2 is not None:
        right = crop_frame(frame2, crop_box2)
        right = rotate_frame(right, ROTATE_RIGHT_DEGREES)
        right = cv2.resize(right, (PANEL_WIDTH, PANEL_HEIGHT))
        canvas[0:PANEL_HEIGHT, PANEL_WIDTH:TOTAL_WIDTH] = right

    return canvas


def capture_loop():
    global latest_frame, crop_box1, crop_box2
    while True:
        ret1, frame1 = cap1.read()
        ret2, frame2 = cap2.read()

        if ret1:
            frame1, calib1 = detect_and_draw(frame1)
            if calib1:
                crop_box1 = compute_crop_box(calib1, frame1.shape)
        else:
            frame1 = None

        if ret2:
            frame2, calib2 = detect_and_draw(frame2)
            if calib2:
                crop_box2 = compute_crop_box(calib2, frame2.shape)
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
