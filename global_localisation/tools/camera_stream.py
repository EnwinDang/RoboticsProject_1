"""
Live dual-camera world-view stream viewable in browser.
Run on Jetson: python tools/camera_stream.py
Then open: http://jetson-dang.local:8080
"""
import sys
import os
import threading

import cv2
from flask import Flask, Response

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import CAMERA_INDEX_1, CAMERA_INDEX_2, CANVAS_WIDTH, CANVAS_HEIGHT
from mapping.homography import HomographyMapper
sys.path.insert(0, os.path.dirname(__file__))
from utils import open_camera, configure_cameras, detect_and_draw, render_to_world, compose_world_view

app = Flask(__name__)

mapper1 = HomographyMapper()
mapper2 = HomographyMapper()

cap1 = open_camera(CAMERA_INDEX_1)
cap2 = open_camera(CAMERA_INDEX_2)

latest_frame = None
frame_lock = threading.Lock()


def process_camera(cap, mapper, result, key):
    ret, frame = cap.read()
    if not ret:
        result[key] = None
        return
    frame, detections = detect_and_draw(frame)
    if mapper.H is None:
        mapper.compute_homography(detections)
    result[key] = frame


def capture_loop():
    global latest_frame
    while True:
        result = {}
        t1 = threading.Thread(target=process_camera, args=(cap1, mapper1, result, "frame1"))
        t2 = threading.Thread(target=process_camera, args=(cap2, mapper2, result, "frame2"))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        world1 = render_to_world(result.get("frame1"), mapper1.H)
        world2 = render_to_world(result.get("frame2"), mapper2.H)
        canvas = compose_world_view(world1, world2)

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

    configure_cameras(CAMERA_INDEX_1, CAMERA_INDEX_2)

    t = threading.Thread(target=capture_loop, daemon=True)
    t.start()

    print(f"World-view stream → http://0.0.0.0:8080  ({CANVAS_WIDTH}×{CANVAS_HEIGHT}px)")
    app.run(host="0.0.0.0", port=8080)
