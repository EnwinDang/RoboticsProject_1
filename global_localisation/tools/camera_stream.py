"""
Live camera stream viewable in browser.
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
from config import CAMERA_INDEX_1, CAMERA_INDEX_2, CALIBRATION_IDS

app = Flask(__name__)

aruco_dict = aruco.getPredefinedDictionary(aruco.DICT_4X4_50)
aruco_params = aruco.DetectorParameters()
aruco_params.adaptiveThreshWinSizeMin = 3
aruco_params.adaptiveThreshWinSizeMax = 23
aruco_params.adaptiveThreshWinSizeStep = 10
detector = aruco.ArucoDetector(aruco_dict, aruco_params)

PANEL_WIDTH = 1180
PANEL_HEIGHT = 664
TOTAL_WIDTH = 2100
TOTAL_HEIGHT = PANEL_HEIGHT
LABEL_STYLE = cv2.FONT_HERSHEY_SIMPLEX

# Stitch anchors: these x-ratios are aligned onto the same seam line.
SEAM_X = 980
LEFT_ANCHOR_RATIO = 0.84
RIGHT_ANCHOR_RATIO = 0.14

# Crop the outer edges a bit so both cameras blend into one continuous track view.
CROP_LEFT = (0.0, 1.0, 0.0, 1.0)
CROP_RIGHT = (0.0, 1.0, 0.0, 1.0)
ROTATE_LEFT_DEGREES = 90.0
ROTATE_RIGHT_DEGREES = -90.0

cap1 = cv2.VideoCapture(CAMERA_INDEX_1, cv2.CAP_V4L2)
cap2 = cv2.VideoCapture(CAMERA_INDEX_2, cv2.CAP_V4L2)

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
    return cv2.warpAffine(frame, matrix, (width, height), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)


def compose_frame(frame1, frame2):
    canvas = np.zeros((TOTAL_HEIGHT, TOTAL_WIDTH, 3), dtype=np.uint8)
    left_label_x = None
    right_label_x = None

    left_image = None
    right_image = None

    if frame1 is not None:
        left_image = crop_frame(frame1, CROP_LEFT)
        left_image = rotate_frame(left_image, ROTATE_LEFT_DEGREES)
        left_image = cv2.resize(left_image, (PANEL_WIDTH, PANEL_HEIGHT))

    if frame2 is not None:
        right_image = crop_frame(frame2, CROP_RIGHT)
        right_image = rotate_frame(right_image, ROTATE_RIGHT_DEGREES)
        right_image = cv2.resize(right_image, (PANEL_WIDTH, PANEL_HEIGHT))

    if left_image is None and right_image is None:
        return canvas

    left_buffer = np.zeros_like(canvas, dtype=np.float32)
    right_buffer = np.zeros_like(canvas, dtype=np.float32)
    left_mask = np.zeros((TOTAL_HEIGHT, TOTAL_WIDTH), dtype=bool)
    right_mask = np.zeros((TOTAL_HEIGHT, TOTAL_WIDTH), dtype=bool)

    if left_image is not None:
        left_anchor_x = int(PANEL_WIDTH * LEFT_ANCHOR_RATIO)
        left_x = SEAM_X - left_anchor_x
        left_start = max(0, left_x)
        left_end = min(TOTAL_WIDTH, left_x + PANEL_WIDTH)
        src_left_start = max(0, -left_x)
        src_left_end = src_left_start + (left_end - left_start)

        if left_end > left_start:
            left_chunk = left_image[:, src_left_start:src_left_end]
            left_buffer[:, left_start:left_end] = left_chunk.astype(np.float32)
            left_mask[:, left_start:left_end] = True

            left_label_x = max(12, min(left_start + 12, TOTAL_WIDTH - 320))

    if right_image is not None:
        right_anchor_x = int(PANEL_WIDTH * RIGHT_ANCHOR_RATIO)
        right_x = SEAM_X - right_anchor_x
        right_start = max(0, right_x)
        right_end = min(TOTAL_WIDTH, right_x + PANEL_WIDTH)
        src_right_start = max(0, -right_x)
        src_right_end = src_right_start + (right_end - right_start)

        if right_end > right_start:
            right_chunk = right_image[:, src_right_start:src_right_end]
            right_buffer[:, right_start:right_end] = right_chunk.astype(np.float32)
            right_mask[:, right_start:right_end] = True

            right_label_x = max(12, min(right_start + 12, TOTAL_WIDTH - 320))

    both_mask = left_mask & right_mask
    only_left_mask = left_mask & (~right_mask)
    only_right_mask = right_mask & (~left_mask)

    canvas_float = np.zeros_like(left_buffer)
    canvas_float[only_left_mask] = left_buffer[only_left_mask]
    canvas_float[only_right_mask] = right_buffer[only_right_mask]
    canvas_float[both_mask] = 0.5 * left_buffer[both_mask] + 0.5 * right_buffer[both_mask]

    stitched = np.clip(canvas_float, 0, 255).astype(np.uint8)
    non_black = (stitched[:, :, 0] > 0) | (stitched[:, :, 1] > 0) | (stitched[:, :, 2] > 0)
    canvas[non_black] = stitched[non_black]

    if left_label_x is not None:
        cv2.rectangle(canvas, (left_label_x, 12), (left_label_x + 308, 58), (0, 0, 0), -1)
        cv2.putText(canvas, "LEFT", (left_label_x + 8, 45), LABEL_STYLE, 1.0, (255, 255, 255), 2, cv2.LINE_AA)

    if right_label_x is not None:
        cv2.rectangle(canvas, (right_label_x, 12), (right_label_x + 308, 58), (0, 0, 0), -1)
        cv2.putText(canvas, "RIGHT", (right_label_x + 8, 45), LABEL_STYLE, 1.0, (255, 255, 255), 2, cv2.LINE_AA)

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

    print(f"Streaming cameras {CAMERA_INDEX_1} + {CAMERA_INDEX_2} (LEFT/RIGHT) → http://0.0.0.0:8080")
    app.run(host="0.0.0.0", port=8080)
