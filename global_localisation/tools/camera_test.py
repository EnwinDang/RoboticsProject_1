"""
Live dual-camera test with ArUco detection overlay.
Run on Jetson: python tools/camera_test.py
Then open in browser: http://jetson-dang.local:8082  (or use the IP shown on startup)
Press Ctrl+C to quit.
"""
import argparse
import signal
import subprocess
import sys
import os
import threading
import time
from collections import Counter

import cv2
import numpy as np
from flask import Flask, Response

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import CAMERA_INDEX_1, CAMERA_INDEX_2, CALIBRATION_IDS
from tools.utils import open_camera

DISPLAY_WIDTH = 960
DISPLAY_HEIGHT = 540
# ID must appear in this many of the last N frames to be considered stable
STABLE_WINDOW = 5
STABLE_THRESHOLD = 3

aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
aruco_params = cv2.aruco.DetectorParameters()
aruco_params.adaptiveThreshWinSizeMin = 3
aruco_params.adaptiveThreshWinSizeMax = 53
aruco_params.adaptiveThreshWinSizeStep = 4
aruco_params.minMarkerPerimeterRate = 0.01
aruco_params.perspectiveRemovePixelPerCell = 8
aruco_params.minOtsuStdDev = 3.0
_detector = cv2.aruco.ArucoDetector(aruco_dict, aruco_params)


def detect_and_annotate(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    corners, ids, _ = _detector.detectMarkers(gray)
    detected_ids = []
    if ids is not None:
        for i, corner in enumerate(corners):
            marker_id = int(ids[i][0])
            detected_ids.append(marker_id)
            color = (0, 0, 255) if marker_id in CALIBRATION_IDS else (0, 255, 0)
            pts = corner[0].astype(int)
            cx = int(corner[0][:, 0].mean())
            cy = int(corner[0][:, 1].mean())
            cv2.polylines(frame, [pts], isClosed=True, color=color, thickness=3)
            cv2.putText(frame, f"ID:{marker_id}", (pts[0][0], pts[0][1] - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 2)
            cv2.circle(frame, (cx, cy), 5, color, -1)
    return frame, detected_ids


def draw_hud(frame, label, stable_ids, fps):
    cv2.rectangle(frame, (0, 0), (frame.shape[1], 36), (0, 0, 0), -1)
    cal = sorted(i for i in stable_ids if i in CALIBRATION_IDS)
    rob = sorted(i for i in stable_ids if i not in CALIBRATION_IDS)
    text = f"{label}  cal={cal}  rob={rob}  {fps:.1f}fps"
    cv2.putText(frame, text, (8, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 1)


latest_frame = None
frame_lock = threading.Lock()
stop_event = threading.Event()


def stable_ids(history):
    """Return IDs that appeared in at least STABLE_THRESHOLD of the last STABLE_WINDOW frames."""
    counts = Counter(mid for frame_ids in history for mid in frame_ids)
    return sorted(mid for mid, n in counts.items() if n >= STABLE_THRESHOLD)


def capture_loop():
    global latest_frame

    cap1 = open_camera(CAMERA_INDEX_1)
    cap2 = open_camera(CAMERA_INDEX_2)

    if not cap1.isOpened():
        print(f"ERROR: cannot open camera {CAMERA_INDEX_1}")
    if not cap2.isOpened():
        print(f"ERROR: cannot open camera {CAMERA_INDEX_2}")

    history1 = []
    history2 = []
    prev_stable1, prev_stable2 = [], []
    t_prev = time.time()

    while not stop_event.is_set():
        ret1, raw1 = cap1.read()
        ret2, raw2 = cap2.read()

        t_now = time.time()
        fps = 1.0 / max(t_now - t_prev, 1e-6)
        t_prev = t_now

        f1 = np.zeros((DISPLAY_HEIGHT, DISPLAY_WIDTH, 3), dtype=np.uint8)
        f2 = np.zeros((DISPLAY_HEIGHT, DISPLAY_WIDTH, 3), dtype=np.uint8)
        ids1, ids2 = [], []

        if ret1:
            annotated1, ids1 = detect_and_annotate(raw1)
            f1 = cv2.resize(annotated1, (DISPLAY_WIDTH, DISPLAY_HEIGHT))
        if ret2:
            annotated2, ids2 = detect_and_annotate(raw2)
            f2 = cv2.resize(annotated2, (DISPLAY_WIDTH, DISPLAY_HEIGHT))

        history1.append(ids1)
        history2.append(ids2)
        if len(history1) > STABLE_WINDOW:
            history1.pop(0)
        if len(history2) > STABLE_WINDOW:
            history2.pop(0)

        s1 = stable_ids(history1)
        s2 = stable_ids(history2)

        draw_hud(f1, f"CAM{CAMERA_INDEX_1} (left)", s1, fps)
        draw_hud(f2, f"CAM{CAMERA_INDEX_2} (right)", s2, fps)

        with frame_lock:
            latest_frame = np.hstack([f2, f1])

        if s1 != prev_stable1 or s2 != prev_stable2:
            print(f"  CAM{CAMERA_INDEX_1}: {s1}   CAM{CAMERA_INDEX_2}: {s2}")
            prev_stable1, prev_stable2 = s1, s2

    cap1.release()
    cap2.release()


def generate_frames():
    while True:
        with frame_lock:
            frame = latest_frame
        if frame is None:
            time.sleep(0.01)
            continue
        _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n")


app = Flask(__name__)


@app.route("/")
def index():
    return (
        '<html><body style="background:#000;margin:0">'
        '<img src="/video" style="width:100%">'
        '</body></html>'
    )


@app.route("/video")
def video():
    return Response(generate_frames(), mimetype="multipart/x-mixed-replace; boundary=frame")


def handle_sigint(sig, frame):
    stop_event.set()
    os._exit(0)


def set_zoom(index, zoom):
    dev = f"/dev/video{index}"
    subprocess.run(["v4l2-ctl", "-d", dev, "-c", f"zoom_absolute={zoom}"], check=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--zoom1", type=int, default=100, help="Zoom for cam4 (default 100 = no zoom, production=130)")
    parser.add_argument("--zoom2", type=int, default=100, help="Zoom for cam0 (default 100 = no zoom, production=113)")
    args = parser.parse_args()

    signal.signal(signal.SIGINT, handle_sigint)

    set_zoom(CAMERA_INDEX_1, args.zoom1)
    set_zoom(CAMERA_INDEX_2, args.zoom2)
    print(f"Zoom: cam{CAMERA_INDEX_1}={args.zoom1}  cam{CAMERA_INDEX_2}={args.zoom2}")

    t = threading.Thread(target=capture_loop, daemon=True)
    t.start()

    import socket
    try:
        ip = socket.gethostbyname(socket.gethostname())
    except Exception:
        ip = "127.0.0.1"

    print(f"Stream → http://jetson-dang.local:8082  or  http://{ip}:8082")
    print(f"Legend: RED = calibration (IDs {CALIBRATION_IDS}), GREEN = robot marker")
    print("Ctrl+C to quit.")
    app.run(host="0.0.0.0", port=8082)
