import cv2
import numpy as np
import math


class ArucoDetector:
    def __init__(self):
        self.aruco_dict = cv2.aruco.getPredefinedDictionary(
            cv2.aruco.DICT_4X4_50
        )
        self.detector = cv2.aruco.ArucoDetector(self.aruco_dict)

    def detect(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        corners, ids, _ = self.detector.detectMarkers(gray)

        detections = []

        if ids is not None:
            for i in range(len(ids)):
                pts = corners[i].reshape((4, 2)).astype(int)

                center_x = int(np.mean(pts[:, 0]))
                center_y = int(np.mean(pts[:, 1]))

                dx = pts[1][0] - pts[0][0]
                dy = pts[1][1] - pts[0][1]
                theta = math.atan2(dy, dx)

                detections.append({
                    "id": int(ids[i][0]),
                    "x_pixel": center_x,
                    "y_pixel": center_y,
                    "theta_image": theta,
                    "corners": pts
                })

        return detections
