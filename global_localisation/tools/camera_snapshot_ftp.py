"""
Capture both cameras, render them into a single top-down world view, and upload
it to FTP every 30 seconds.

The remote filename is reused on every upload, so the previous image is overwritten.

Environment variables:
  FTP_HOST
  FTP_USER
  FTP_PASSWORD
  FTP_REMOTE_DIR   (optional, default: /cams)
  FTP_REMOTE_NAME  (optional, default: camera_snapshot.jpg)
  SNAPSHOT_INTERVAL_SECONDS (optional, default: 30)
"""

import io
import os
import sys
import time
from ftplib import FTP, FTP_TLS

import cv2

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import (
    CAMERA_INDEX_1,
    CAMERA_INDEX_2,
    FTP_HOST as CONFIG_FTP_HOST,
    FTP_PASSWORD as CONFIG_FTP_PASSWORD,
    FTP_REMOTE_DIR as CONFIG_FTP_REMOTE_DIR,
    FTP_REMOTE_NAME as CONFIG_FTP_REMOTE_NAME,
    FTP_USER as CONFIG_FTP_USER,
    SNAPSHOT_INTERVAL_SECONDS as CONFIG_SNAPSHOT_INTERVAL_SECONDS,
)
from mapping.homography import HomographyMapper
sys.path.insert(0, os.path.dirname(__file__))
from utils import open_camera, configure_cameras, detect_and_draw, render_to_world, compose_world_view

FTP_HOST = os.environ.get("FTP_HOST", CONFIG_FTP_HOST)
FTP_USER = os.environ.get("FTP_USER", CONFIG_FTP_USER)
FTP_PASSWORD = os.environ.get("FTP_PASSWORD", CONFIG_FTP_PASSWORD)
FTP_REMOTE_DIR = os.environ.get("FTP_REMOTE_DIR", CONFIG_FTP_REMOTE_DIR)
FTP_REMOTE_NAME = os.environ.get("FTP_REMOTE_NAME", CONFIG_FTP_REMOTE_NAME)
SNAPSHOT_INTERVAL_SECONDS = float(
    os.environ.get("SNAPSHOT_INTERVAL_SECONDS", str(CONFIG_SNAPSHOT_INTERVAL_SECONDS))
)

mapper1 = HomographyMapper()
mapper2 = HomographyMapper()


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
    return compose_world_view(world1, world2)


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


def take_snapshot():
    """Open cameras, capture one frame, close cameras. Returns world canvas."""
    cap1 = open_camera(CAMERA_INDEX_1)
    cap2 = open_camera(CAMERA_INDEX_2)
    configure_cameras(CAMERA_INDEX_1, CAMERA_INDEX_2)

    if not cap1.isOpened():
        print(f"Error: Could not open camera {CAMERA_INDEX_1}")
    if not cap2.isOpened():
        print(f"Error: Could not open camera {CAMERA_INDEX_2}")
    if not cap1.isOpened() and not cap2.isOpened():
        cap1.release()
        cap2.release()
        return None

    # Read a few frames to let the camera stabilise, then capture
    for _ in range(10):
        capture_world_frame(cap1, cap2)

    frame = capture_world_frame(cap1, cap2)
    cap1.release()
    cap2.release()
    return frame


LOCK_FILE = "/tmp/localisation.lock"


def main():
    if os.path.exists(LOCK_FILE):
        print("Localisation is running — skipping FTP snapshot")
        return

    frame = take_snapshot()
    if frame is None:
        print("Could not capture frame — skipping upload")
        return

    try:
        ftp = get_ftp_connection()
        upload_frame(ftp, frame)
        print(f"Uploaded {FTP_REMOTE_NAME} to {FTP_HOST}")
        ftp.quit()
    except Exception as e:
        print(f"Upload failed: {e}")


if __name__ == "__main__":
    main()
