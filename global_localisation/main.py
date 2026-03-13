import json
import cv2
import paho.mqtt.client as mqtt

from vision.detector import ArucoDetector
from mapping.homography import HomographyMapper
from config import CAMERA_INDEX_1, CAMERA_INDEX_2, CALIBRATION_IDS, MQTT_BROKER, MQTT_PORT, MQTT_TOPIC_PREFIX


def main():
    cap1 = cv2.VideoCapture(CAMERA_INDEX_1, cv2.CAP_V4L2)
    cap2 = cv2.VideoCapture(CAMERA_INDEX_2, cv2.CAP_V4L2)

    detector = ArucoDetector()
    mapper1 = HomographyMapper()
    mapper2 = HomographyMapper()

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.connect(MQTT_BROKER, MQTT_PORT)
    client.loop_start()

    while True:
        ret1, frame1 = cap1.read()
        ret2, frame2 = cap2.read()

        poses = {}

        # process camera 1
        if ret1:
            detections1 = detector.detect(frame1)
            mapper1.compute_homography(detections1)
            for det in detections1:
                if det["id"] in CALIBRATION_IDS:
                    continue
                world = mapper1.pixel_to_world(det["x_pixel"], det["y_pixel"])
                if world is not None:
                    poses[det["id"]] = (world[0], world[1], det["theta_image"])

        # process camera 2 (overwrites only if cam1 didn't see this robot)
        if ret2:
            detections2 = detector.detect(frame2)
            mapper2.compute_homography(detections2)
            for det in detections2:
                if det["id"] in CALIBRATION_IDS:
                    continue
                if det["id"] in poses:
                    continue
                world = mapper2.pixel_to_world(det["x_pixel"], det["y_pixel"])
                if world is not None:
                    poses[det["id"]] = (world[0], world[1], det["theta_image"])

        # publish all robot poses
        for robot_id, (x_w, y_w, theta) in poses.items():
            print(f"ID {robot_id} → World: ({x_w:.2f}, {y_w:.2f}), theta: {theta:.2f}")

            topic = f"{MQTT_TOPIC_PREFIX}{robot_id}"
            payload = json.dumps({
                "x": round(float(x_w), 3),
                "y": round(float(y_w), 3),
                "theta": round(float(theta), 3)
            })
            client.publish(topic, payload)

        if not ret1 and not ret2:
            break

    cap1.release()
    cap2.release()
    client.loop_stop()
    client.disconnect()


if __name__ == "__main__":
    main()
