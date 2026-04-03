"""
Capture both cameras, render them into a single top-down world view, and upload
it to FTP every 30 seconds.

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
    WORLD_WIDTH,
    WORLD_HEIGHT,
    FTP_HOST as CONFIG_FTP_HOST,
    FTP_PASSWORD as CONFIG_FTP_PASSWORD,
    FTP_REMOTE_DIR as CONFIG_FTP_REMOTE_DIR,
    FTP_REMOTE_NAME as CONFIG_FTP_REMOTE_NAME,
    FTP_USER as CONFIG_FTP_USER,
    SNAPSHOT_INTERVAL_SECONDS as CONFIG_SNAPSHOT_INTERVAL_SECONDS,
)
from mapping.homography import HomographyMapper


aruco_dict = aruco.getPredefinedDictionary(aruco.DICT_4X4_50)
aruco_params = aruco.DetectorParameters()
aruco_params.adaptiveThreshWinSizeMin = 3
aruco_params.adaptiveThreshWinSizeMax = 53
aruco_params.adaptiveThreshWinSizeStep = 4
aruco_params.minMarkerPerimeterRate = 0.01
aruco_params.perspectiveRemovePixelPerCell = 8
aruco_params.minOtsuStdDev = 3.0
detector = aruco.ArucoDetector(aruco_dict, aruco_params)

# World canvas: 200 px per metre → 1200 × 600 + padding
WORLD_SCALE = 200
PADDING = 60  # pixels of empty border around the world area
CANVAS_WIDTH = int(WORLD_WIDTH * WORLD_SCALE) + 2 * PADDING
CANVAS_HEIGHT = int(WORLD_HEIGHT * WORLD_SCALE) + 2 * PADDING

mapper1 = HomographyMapper()
mapper2 = HomographyMapper()

FTP_HOST = os.environ.get("FTP_HOST", CONFIG_FTP_HOST)
FTP_USER = os.environ.get("FTP_USER", CONFIG_FTP_USER)
FTP_PASSWORD = os.environ.get("FTP_PASSWORD", CONFIG_FTP_PASSWORD)
FTP_REMOTE_DIR = os.environ.get("FTP_REMOTE_DIR", CONFIG_FTP_REMOTE_DIR)
FTP_REMOTE_NAME = os.environ.get("FTP_REMOTE_NAME", CONFIG_FTP_REMOTE_NAME)
SNAPSHOT_INTERVAL_SECONDS = float(os.environ.get("SNAPSHOT_INTERVAL_SECONDS", str(CONFIG_SNAPSHOT_INTERVAL_SECONDS)))


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


def capture_world_frame(cap1, cap2):
    """Read both cameras and return a stitched top-down world canvas."""
    ret1, frame1 = cap1.read()
    ret2, frame2 = cap2.read()

    if ret1:
        frame1, det1 = detect_and_draw(frame1)
        if mapper1.H is None:
            mapper1.compute_homography(det1)
    else:
        frame1, det1 = None, []

    if ret2:
        frame2, det2 = detect_and_draw(frame2)
        if mapper2.H is None:
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
    return canvas


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
        raise RuntimeError("Could not encode world frame as JPEG")

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

    # Set focus and sharpness via v4l2-ctl for both cameras
    for dev in [f"/dev/video{CAMERA_INDEX_1}", f"/dev/video{CAMERA_INDEX_2}"]:
        subprocess.run(["v4l2-ctl", "-d", dev, "-c", "focus_automatic_continuous=0"], check=False)
        subprocess.run(["v4l2-ctl", "-d", dev, "-c", "focus_absolute=10"], check=False)
        subprocess.run(["v4l2-ctl", "-d", dev, "-c", "sharpness=255"], check=False)

    if not cap1.isOpened():
        print(f"Error: Could not open camera {CAMERA_INDEX_1}")
    if not cap2.isOpened():
        print(f"Error: Could not open camera {CAMERA_INDEX_2}")
    if not cap1.isOpened() and not cap2.isOpened():
        raise SystemExit(1)

    # Warm up cameras and build homography during warmup
    print("Warming up cameras and computing homography...")
    for _ in range(120):
        capture_world_frame(cap1, cap2)

    ftp = get_ftp_connection()
    print(f"Uploading world-view image every {SNAPSHOT_INTERVAL_SECONDS:.0f} seconds as {FTP_REMOTE_NAME}")

    try:
        while True:
            frame = capture_world_frame(cap1, cap2)
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
