"""
Capture both cameras, stitch them into one image, and upload it to FTP every 30 seconds.

The remote filename is reused on every upload, so the previous image is overwritten.

Environment variables:
  FTP_HOST
  FTP_USER
  FTP_PASSWORD
  FTP_REMOTE_DIR   (optional, default: /)
  FTP_REMOTE_NAME  (optional, default: camera_snapshot.jpg)
  SNAPSHOT_INTERVAL_SECONDS (optional, default: 30)
"""

import io
import os
import subprocess
import sys
import time
from ftplib import FTP, FTP_TLS

import cv2
import cv2.aruco as aruco
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import (
    CAMERA_INDEX_1,
    CAMERA_INDEX_2,
    CALIBRATION_IDS,
    CAMERA_WIDTH,
    CAMERA_HEIGHT,
    FTP_HOST as CONFIG_FTP_HOST,
    FTP_PASSWORD as CONFIG_FTP_PASSWORD,
    FTP_REMOTE_DIR as CONFIG_FTP_REMOTE_DIR,
    FTP_REMOTE_NAME as CONFIG_FTP_REMOTE_NAME,
    FTP_USER as CONFIG_FTP_USER,
    SNAPSHOT_INTERVAL_SECONDS as CONFIG_SNAPSHOT_INTERVAL_SECONDS,
)


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

FTP_HOST = os.environ.get("FTP_HOST", CONFIG_FTP_HOST)
FTP_USER = os.environ.get("FTP_USER", CONFIG_FTP_USER)
FTP_PASSWORD = os.environ.get("FTP_PASSWORD", CONFIG_FTP_PASSWORD)
FTP_REMOTE_DIR = os.environ.get("FTP_REMOTE_DIR", CONFIG_FTP_REMOTE_DIR)
FTP_REMOTE_NAME = os.environ.get("FTP_REMOTE_NAME", CONFIG_FTP_REMOTE_NAME)
SNAPSHOT_INTERVAL_SECONDS = float(os.environ.get("SNAPSHOT_INTERVAL_SECONDS", str(CONFIG_SNAPSHOT_INTERVAL_SECONDS)))


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


def capture_frame(cap1, cap2):
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

    return compose_frame(frame1, frame2)


def get_ftp_connection():
    if not FTP_HOST or not FTP_USER or not FTP_PASSWORD:
        raise SystemExit("Set FTP_HOST, FTP_USER, and FTP_PASSWORD environment variables first.")

    ftp = FTP_TLS() if FTP_HOST.startswith("ftps://") else FTP()
    host = FTP_HOST.replace("ftps://", "").replace("ftp://", "")
    ftp.connect(host, 21, timeout=30)
    ftp.login(FTP_USER, FTP_PASSWORD)

    if isinstance(ftp, FTP_TLS):
        ftp.prot_p()

    if FTP_REMOTE_DIR and FTP_REMOTE_DIR != "/":
        ftp.cwd(FTP_REMOTE_DIR)

    return ftp


def upload_frame(ftp, frame):
    success, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 100])
    if not success:
        raise RuntimeError("Could not encode stitched frame as JPEG")

    buffer = io.BytesIO(encoded.tobytes())
    buffer.seek(0)
    ftp.storbinary(f"STOR {FTP_REMOTE_NAME}", buffer)


def main():
    cap1 = cv2.VideoCapture(CAMERA_INDEX_1, cv2.CAP_V4L2)
    cap1.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap1.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
    cap1.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
    cap2 = cv2.VideoCapture(CAMERA_INDEX_2, cv2.CAP_V4L2)
    cap2.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap2.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
    cap2.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)

    # Set focus via v4l2-ctl for both cameras
    for dev in [f"/dev/video{CAMERA_INDEX_1}", f"/dev/video{CAMERA_INDEX_2}"]:
        subprocess.run(["v4l2-ctl", "-d", dev, "-c", "focus_automatic_continuous=0"], check=False)
        subprocess.run(["v4l2-ctl", "-d", dev, "-c", "focus_absolute=10"], check=False)

    if not cap1.isOpened():
        print(f"Error: Could not open camera {CAMERA_INDEX_1}")
    if not cap2.isOpened():
        print(f"Error: Could not open camera {CAMERA_INDEX_2}")
    if not cap1.isOpened() and not cap2.isOpened():
        raise SystemExit(1)

    # Warm up cameras — discard first frames so exposure/focus stabilises
    for _ in range(10):
        cap1.read()
        cap2.read()

    ftp = get_ftp_connection()
    print(f"Uploading stitched camera image every {SNAPSHOT_INTERVAL_SECONDS:.0f} seconds as {FTP_REMOTE_NAME}")

    try:
        while True:
            frame = capture_frame(cap1, cap2)
            upload_frame(ftp, frame)
            print(f"Uploaded {FTP_REMOTE_NAME} to {FTP_HOST}")
            time.sleep(SNAPSHOT_INTERVAL_SECONDS)
    finally:
        cap1.release()
        cap2.release()
        try:
            ftp.quit()
        except Exception:
            pass


if __name__ == "__main__":
    main()