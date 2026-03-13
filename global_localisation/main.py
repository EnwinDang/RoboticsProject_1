import json
import cv2
import paho.mqtt.client as mqtt

from vision.detector import ArucoDetector
from mapping.homography import HomographyMapper
from config import CAMERA_INDEX, CALIBRATION_IDS, MQTT_BROKER, MQTT_PORT, MQTT_TOPIC_PREFIX


def main():
    cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_V4L2)
    detector = ArucoDetector()
    mapper = HomographyMapper()

    client = mqtt.Client()
    client.connect(MQTT_BROKER, MQTT_PORT)
    client.loop_start()

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        detections = detector.detect(frame)

        mapper.compute_homography(detections)

        for det in detections:
            if det["id"] in CALIBRATION_IDS:
                continue

            world = mapper.pixel_to_world(
                det["x_pixel"], det["y_pixel"]
            )

            if world is not None:
                x_w, y_w = world
                theta = det["theta_image"]

                print(
                    f"ID {det['id']} → "
                    f"World: ({x_w:.2f}, {y_w:.2f}), "
                    f"theta: {theta:.2f}"
                )

                topic = f"{MQTT_TOPIC_PREFIX}{det['id']}"
                payload = json.dumps({
                    "x": round(x_w, 3),
                    "y": round(y_w, 3),
                    "theta": round(theta, 3)
                })
                client.publish(topic, payload)

    cap.release()
    client.loop_stop()
    client.disconnect()


if __name__ == "__main__":
    main()
