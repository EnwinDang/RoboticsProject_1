"""
Live dual-camera test with ArUco detection overlay.
Run on Jetson: python tools/camera_test.py
Press 'q' to quit.
"""
import sys
import os
import threading
import time

import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config import (
    CAMERA_INDEX_1,
    CAMERA_INDEX_2,
    CALIBRATION_IDS,
    CAMERA_FOCUS,
    CAMERA_ZOOM_1,
    CAMERA_ZOOM_2,
)
from tools.utils import open_camera, configure_cameras

DISPLAY_WIDTH = 960
DISPLAY_HEIGHT = 540

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


def draw_hud(frame, label, detected_ids, fps):
    h, w = frame.shape[:2]
    cv2.rectangle(frame, (0, 0), (w, 36), (0, 0, 0), -1)
    cal = [i for i in detected_ids if i in CALIBRATION_IDS]
    rob = [i for i in detected_ids if i not in CALIBRATION_IDS]
    cal_str = f"cal={sorted(cal)}" if cal else "cal=[]"
    rob_str = f"rob={sorted(rob)}" if rob else "rob=[]"
    text = f"{label}  {cal_str}  {rob_str}  {fps:.1f}fps"
    cv2.putText(frame, text, (8, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 1)
    return frame


class CameraThread:
    def __init__(self, index, label):
        self.index = index
        self.label = label
        self.cap = open_camera(index)
        self.frame = np.zeros((DISPLAY_HEIGHT, DISPLAY_WIDTH, 3), dtype=np.uint8)
        self.ids = []
        self.fps = 0.0
        self._lock = threading.Lock()
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self):
        t_prev = time.time()
        while self._running:
            ret, raw = self.cap.read()
            if not ret:
                continue
            annotated, detected_ids = detect_and_annotate(raw)
            small = cv2.resize(annotated, (DISPLAY_WIDTH, DISPLAY_HEIGHT))
            t_now = time.time()
            fps = 1.0 / max(t_now - t_prev, 1e-6)
            t_prev = t_now
            draw_hud(small, self.label, detected_ids, fps)
            with self._lock:
                self.frame = small
                self.ids = detected_ids
                self.fps = fps

    def get(self):
        with self._lock:
            return self.frame.copy(), list(self.ids), self.fps

    def stop(self):
        self._running = False
        self._thread.join()
        self.cap.release()


def main():
    print("Opening cameras...")
    cam1 = CameraThread(CAMERA_INDEX_1, f"CAM{CAMERA_INDEX_1} (left)")
    cam2 = CameraThread(CAMERA_INDEX_2, f"CAM{CAMERA_INDEX_2} (right)")

    if not cam1.cap.isOpened():
        print(f"ERROR: cannot open camera {CAMERA_INDEX_1}")
    if not cam2.cap.isOpened():
        print(f"ERROR: cannot open camera {CAMERA_INDEX_2}")
    if not cam1.cap.isOpened() and not cam2.cap.isOpened():
        raise SystemExit(1)

    configure_cameras(CAMERA_INDEX_1, CAMERA_INDEX_2)

    print("Press 'q' to quit.")
    print(f"Legend: RED border = calibration marker (IDs {CALIBRATION_IDS}), GREEN = robot marker")

    prev_ids1, prev_ids2 = [], []

    while True:
        f1, ids1, fps1 = cam1.get()
        f2, ids2, fps2 = cam2.get()

        combined = np.hstack([f2, f1])  # right cam on left half, left cam on right half
        cv2.imshow("Camera Test — both cameras (q to quit)", combined)

        # log to console when detected markers change
        if ids1 != prev_ids1 or ids2 != prev_ids2:
            print(f"  CAM{CAMERA_INDEX_1}: {sorted(ids1)}   CAM{CAMERA_INDEX_2}: {sorted(ids2)}")
            prev_ids1, prev_ids2 = ids1, ids2

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cam1.stop()
    cam2.stop()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
