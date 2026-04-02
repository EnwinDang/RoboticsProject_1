"""
Live top-down map stream viewable in browser.
Both camera views are warped into world coordinates using ArUco calibration markers.
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
from config import CAMERA_INDEX_1, CAMERA_INDEX_2, CALIBRATION_IDS, WORLD_WIDTH, WORLD_HEIGHT

app = Flask(__name__)

# ArUco detector
aruco_dict = aruco.getPredefinedDictionary(aruco.DICT_4X4_50)
aruco_params = aruco.DetectorParameters()
aruco_params.adaptiveThreshWinSizeMin = 3
aruco_params.adaptiveThreshWinSizeMax = 23
aruco_params.adaptiveThreshWinSizeStep = 10
detector = aruco.ArucoDetector(aruco_dict, aruco_params)

# World coordinate map of calibration markers
WORLD_POINTS = {
    0: (0.0, 0.0),
    1: (0.0, WORLD_HEIGHT),
    2: (WORLD_WIDTH / 2, 0.0),
    3: (WORLD_WIDTH / 2, WORLD_HEIGHT),
    4: (WORLD_WIDTH, 0.0),
    5: (WORLD_WIDTH, WORLD_HEIGHT),
}

# Output canvas: scale world meters to pixels
MAP_SCALE = 150  # pixels per meter
MAP_W = int(WORLD_WIDTH * MAP_SCALE)
MAP_H = int(WORLD_HEIGHT * MAP_SCALE)

cap1 = cv2.VideoCapture(CAMERA_INDEX_1, cv2.CAP_V4L2)
cap2 = cv2.VideoCapture(CAMERA_INDEX_2, cv2.CAP_V4L2)

latest_frame = None
frame_lock = threading.Lock()

# Cached homographies (pixel → map canvas pixels)
H1 = None
H2 = None


def detect_markers(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    corners, ids, _ = detector.detectMarkers(gray)
    detections = {}
    if ids is not None:
        for i, corner in enumerate(corners):
            mid = int(ids[i][0])
            c = corner[0]
            detections[mid] = (float(c[:, 0].mean()), float(c[:, 1].mean()))
    return detections


def compute_homography(detections):
    pixel_pts = []
    map_pts = []
    for mid, (px, py) in detections.items():
        if mid in WORLD_POINTS:
            wx, wy = WORLD_POINTS[mid]
            pixel_pts.append([px, py])
            map_pts.append([wx * MAP_SCALE, wy * MAP_SCALE])
    if len(pixel_pts) >= 4:
        H, _ = cv2.findHomography(
            np.array(pixel_pts, dtype="float32"),
            np.array(map_pts, dtype="float32")
        )
        return H
    return None


def warp_to_map(frame, H):
    if H is None:
        return None
    return cv2.warpPerspective(frame, H, (MAP_W, MAP_H))


def draw_markers(canvas, detections, H):
    for mid, (px, py) in detections.items():
        pt = np.array([[[px, py]]], dtype="float32")
        mapped = cv2.perspectiveTransform(pt, H)
        mx, my = int(mapped[0][0][0]), int(mapped[0][0][1])
        color = (0, 0, 255) if mid in CALIBRATION_IDS else (0, 255, 0)
        cv2.circle(canvas, (mx, my), 8, color, -1)
        cv2.putText(canvas, str(mid), (mx + 10, my + 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)


def capture_loop():
    global latest_frame, H1, H2
    while True:
        ret1, frame1 = cap1.read()
        ret2, frame2 = cap2.read()

        canvas = np.zeros((MAP_H, MAP_W, 3), dtype=np.uint8)

        if ret1:
            det1 = detect_markers(frame1)
            h = compute_homography(det1)
            if h is not None:
                H1 = h
            if H1 is not None:
                warped = warp_to_map(frame1, H1)
                if warped is not None:
                    mask = np.any(warped > 0, axis=2)
                    canvas[mask] = warped[mask]
                det1_all = detect_markers(frame1)
                if det1_all and H1 is not None:
                    draw_markers(canvas, det1_all, H1)

        if ret2:
            det2 = detect_markers(frame2)
            h = compute_homography(det2)
            if h is not None:
                H2 = h
            if H2 is not None:
                warped = warp_to_map(frame2, H2)
                if warped is not None:
                    mask = np.any(warped > 0, axis=2)
                    # Blend overlap, fill empty areas
                    overlap = mask & np.any(canvas > 0, axis=2)
                    only_cam2 = mask & ~np.any(canvas > 0, axis=2)
                    canvas[only_cam2] = warped[only_cam2]
                    canvas[overlap] = (canvas[overlap].astype(np.float32) * 0.5 +
                                       warped[overlap].astype(np.float32) * 0.5).astype(np.uint8)
                det2_all = detect_markers(frame2)
                if det2_all and H2 is not None:
                    draw_markers(canvas, det2_all, H2)

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

    print(f"Streaming top-down map → http://0.0.0.0:8080")
    app.run(host="0.0.0.0", port=8080)
