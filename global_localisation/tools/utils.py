"""
Shared utilities for camera tools (camera_stream.py, camera_snapshot_ftp.py).
"""
import subprocess
import sys
import os

import cv2
import cv2.aruco as aruco
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import (
    CALIBRATION_IDS,
    CAMERA_WIDTH,
    CAMERA_HEIGHT,
    CAMERA_FOCUS,
    CAMERA_SHARPNESS,
    CAMERA_ZOOM_1,
    CAMERA_ZOOM_2,
    CANVAS_WIDTH,
    CANVAS_HEIGHT,
    WORLD_SCALE,
    CANVAS_PADDING,
    WORLD_WIDTH,
)

aruco_dict = aruco.getPredefinedDictionary(aruco.DICT_4X4_50)
aruco_params = aruco.DetectorParameters()
aruco_params.adaptiveThreshWinSizeMin = 3
aruco_params.adaptiveThreshWinSizeMax = 53
aruco_params.adaptiveThreshWinSizeStep = 4
aruco_params.minMarkerPerimeterRate = 0.01
aruco_params.perspectiveRemovePixelPerCell = 8
aruco_params.minOtsuStdDev = 3.0
_detector = aruco.ArucoDetector(aruco_dict, aruco_params)


def open_camera(index):
    """Open a V4L2 camera at the given index with standard settings."""
    cap = cv2.VideoCapture(index, cv2.CAP_V4L2)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
    cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)
    cap.set(cv2.CAP_PROP_FOCUS, CAMERA_FOCUS)
    cap.set(cv2.CAP_PROP_FPS, 10)
    return cap


def configure_cameras(index1, index2):
    """Apply v4l2-ctl hardware settings (focus, sharpness, zoom) for both cameras."""
    for idx, zoom in ((index1, CAMERA_ZOOM_1), (index2, CAMERA_ZOOM_2)):
        dev = f"/dev/video{idx}"
        subprocess.run(["v4l2-ctl", "-d", dev, "-c", "focus_automatic_continuous=0"], check=False)
        subprocess.run(["v4l2-ctl", "-d", dev, "-c", f"focus_absolute={CAMERA_FOCUS}"], check=False)
        subprocess.run(["v4l2-ctl", "-d", dev, "-c", f"sharpness={CAMERA_SHARPNESS}"], check=False)
        subprocess.run(["v4l2-ctl", "-d", dev, "-c", f"zoom_absolute={zoom}"], check=False)


def detect_and_draw(frame):
    """Detect ArUco markers, annotate frame, return (frame, detections)."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    corners, ids, _ = _detector.detectMarkers(gray)
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
    S = np.array([[WORLD_SCALE, 0, CANVAS_PADDING],
                  [0, WORLD_SCALE, CANVAS_PADDING],
                  [0, 0,          1]], dtype=np.float64)
    return cv2.warpPerspective(frame, S @ H, (CANVAS_WIDTH, CANVAS_HEIGHT))


def compose_world_view(world1, world2):
    """Stitch two warped world frames: cam2 owns left half, cam1 owns right half."""
    seam_x = CANVAS_PADDING + int(WORLD_WIDTH / 2 * WORLD_SCALE)
    canvas = np.zeros((CANVAS_HEIGHT, CANVAS_WIDTH, 3), dtype=np.uint8)
    canvas[:, :seam_x] = world2[:, :seam_x]
    canvas[:, seam_x:] = world1[:, seam_x:]
    return canvas
