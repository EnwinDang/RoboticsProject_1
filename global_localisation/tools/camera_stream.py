"""
Live dual-camera world-view stream viewable in browser.
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
from config import (
    CAMERA_INDEX_1, CAMERA_INDEX_2, CALIBRATION_IDS,
    CAMERA_WIDTH, CAMERA_HEIGHT, WORLD_WIDTH, WORLD_HEIGHT,
)
from mapping.homography import HomographyMapper

app = Flask(__name__)

aruco_dict = aruco.getPredefinedDictionary(aruco.DICT_4X4_50)
aruco_params = aruco.DetectorParameters()
aruco_params.adaptiveThreshWinSizeMin = 3
aruco_params.adaptiveThreshWinSizeMax = 23
aruco_params.adaptiveThreshWinSizeStep = 10
detector = aruco.ArucoDetector(aruco_dict, aruco_params)

# World canvas: 200 px per metre → 1200 × 600 + padding
WORLD_SCALE = 200
PADDING = 60  # pixels of empty border around the world area
CANVAS_WIDTH = int(WORLD_WIDTH * WORLD_SCALE) + 2 * PADDING
CANVAS_HEIGHT = int(WORLD_HEIGHT * WORLD_SCALE) + 2 * PADDING

mapper1 = HomographyMapper()
mapper2 = HomographyMapper()


def open_camera(index):
    cap = cv2.VideoCapture(index, cv2.CAP_V4L2)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
    cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)
    cap.set(cv2.CAP_PROP_FOCUS, 10)
    return cap


cap1 = open_camera(CAMERA_INDEX_1)
cap2 = open_camera(CAMERA_INDEX_2)

latest_frame = None
frame_lock = threading.Lock()


def detect_and_draw(frame):
    """Detect ArUco markers, annotate frame, return (frame, detections)."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    corners, ids, _ = detector.detectMarkers(gray)
    detections = []
    if ids is not None:
        for i, corner in enumerate(corners):
            marker_id = int(ids[i][0])
            color = (0, 0, 255) if marker_id in CALIBRATION_IDS else (0, 255, 0)
            pts = corner[0].astype(int)
            cx = int(corner[0][:, 0].mean())
            cy = int(corner[0][:, 1].mean())
            cv2.polylines(frame, [pts], isClosed=True, color=color, thickness=3)
            cv2.putText(frame, str(marker_id), tuple(pts[0]), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
            detections.append({"id": marker_id, "x_pixel": cx, "y_pixel": cy})
    return frame, detections


def render_to_world(frame, H):
    """Warp camera frame into world canvas using homography (pixel → world metres)."""
    if H is None or frame is None:
        return np.zeros((CANVAS_HEIGHT, CANVAS_WIDTH, 3), dtype=np.uint8)
    S = np.array([[WORLD_SCALE, 0, PADDING],
                  [0, WORLD_SCALE, PADDING],
                  [0, 0,           1]], dtype=np.float64)
    return cv2.warpPerspective(frame, S @ H, (CANVAS_WIDTH, CANVAS_HEIGHT))


def capture_loop():
    global latest_frame
    while True:
        ret1, frame1 = cap1.read()
        ret2, frame2 = cap2.read()

        if ret1:
            frame1, det1 = detect_and_draw(frame1)
            mapper1.compute_homography(det1)
        else:
            frame1, det1 = None, []

        if ret2:
            frame2, det2 = detect_and_draw(frame2)
            mapper2.compute_homography(det2)
        else:
            frame2, det2 = None, []

        world1 = render_to_world(frame1, mapper1.H)
        world2 = render_to_world(frame2, mapper2.H)

        # Each camera owns its half of the world — hard split at x = WORLD_WIDTH/2
        seam_x = PADDING + int(WORLD_WIDTH / 2 * WORLD_SCALE)
        canvas = np.zeros((CANVAS_HEIGHT, CANVAS_WIDTH, 3), dtype=np.uint8)
        canvas[:, :seam_x] = world2[:, :seam_x]
        canvas[:, seam_x:] = world1[:, seam_x:]

        with frame_lock:
            latest_frame = canvas


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

    print(f"World-view stream → http://0.0.0.0:8080  ({CANVAS_WIDTH}×{CANVAS_HEIGHT}px)")
    app.run(host="0.0.0.0", port=8080)
