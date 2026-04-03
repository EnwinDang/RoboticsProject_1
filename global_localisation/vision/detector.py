import cv2
import cv2.aruco as aruco
import numpy as np


class ArucoDetector:
    def __init__(self):
        aruco_dict = aruco.getPredefinedDictionary(aruco.DICT_4X4_50)
        parameters = aruco.DetectorParameters()
        parameters.adaptiveThreshWinSizeMin = 3
        parameters.adaptiveThreshWinSizeMax = 53
        parameters.adaptiveThreshWinSizeStep = 4
        parameters.minMarkerPerimeterRate = 0.01
        parameters.perspectiveRemovePixelPerCell = 8
        parameters.minOtsuStdDev = 3.0
        self.detector = aruco.ArucoDetector(aruco_dict, parameters)

    def detect(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        corners, ids, _ = self.detector.detectMarkers(gray)

        detections = []

        if ids is not None:
            for i in range(len(ids)):
                c = corners[i][0]
                center_x = float(c[:, 0].mean())
                center_y = float(c[:, 1].mean())

                # orientation from bottom-left to bottom-right corner
                dx = c[1][0] - c[0][0]
                dy = c[1][1] - c[0][1]
                theta = float(np.arctan2(dy, dx))

                detections.append({
                    "id": int(ids[i][0]),
                    "x_pixel": center_x,
                    "y_pixel": center_y,
                    "theta_image": theta,
                    "corners": c,
                })

        return detections


if __name__ == "__main__":
    import sys
    camera_index = int(sys.argv[1]) if len(sys.argv) > 1 else 0

    cap = cv2.VideoCapture(camera_index, cv2.CAP_V4L2)

    if not cap.isOpened():
        print(f"Error: Could not open camera {camera_index}")
        exit()

    print(f"Camera {camera_index} started. Press Ctrl+C to quit.")

    detector = ArucoDetector()

    try:
        while True:
            ret, frame = cap.read()

            if not ret:
                print("Frame grab failed")
                break

            detections = detector.detect(frame)

            if detections:
                for det in detections:
                    print(f"Marker {det['id']} at pixel ({det['x_pixel']:.0f}, {det['y_pixel']:.0f}), theta={det['theta_image']:.2f}")
            else:
                print("No markers detected")
    except KeyboardInterrupt:
        pass

    cap.release()
