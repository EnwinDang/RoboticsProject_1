"""
Live camera stream viewable in browser.
Run on Jetson: python tools/camera_stream.py [camera_index]
Then open: http://<jetson-ip>:5000
"""
import sys
import cv2
import cv2.aruco as aruco
from flask import Flask, Response

camera_index = int(sys.argv[1]) if len(sys.argv) > 1 else 0

app = Flask(__name__)
cap = cv2.VideoCapture(camera_index, cv2.CAP_V4L2)

aruco_dict = aruco.getPredefinedDictionary(aruco.DICT_4X4_50)
aruco_params = aruco.DetectorParameters()
detector = aruco.ArucoDetector(aruco_dict, aruco_params)


def generate_frames():
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # detect and draw ArUco markers
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        corners, ids, _ = detector.detectMarkers(gray)
        if ids is not None:
            aruco.drawDetectedMarkers(frame, corners, ids)

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
    if not cap.isOpened():
        print(f"Error: Could not open camera {camera_index}")
        sys.exit(1)
    print(f"Streaming camera {camera_index} → http://0.0.0.0:8080")
    app.run(host="0.0.0.0", port=8080)
