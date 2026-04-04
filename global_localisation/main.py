import json
import subprocess
import threading

import cv2
import paho.mqtt.client as mqtt
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Pose2D

from vision.detector import ArucoDetector
from mapping.homography import HomographyMapper
from config import (
    CAMERA_INDEX_1, CAMERA_INDEX_2,
    CALIBRATION_IDS,
    MQTT_BROKER, MQTT_PORT, MQTT_TOPIC_PREFIX,
    POSITION_THRESHOLD, ANGLE_THRESHOLD,
    CAMERA_WIDTH, CAMERA_HEIGHT,
    CAMERA_FOCUS, CAMERA_SHARPNESS, CAMERA_ZOOM_1, CAMERA_ZOOM_2,
)


class LocalisationNode(Node):
    def __init__(self):
        super().__init__('localisation_node')
        self.pose_publisher = self.create_publisher(Pose2D, '/robots/pose', 10)


def publish_pose(node, robot_id, x, y, theta):
    msg = Pose2D()
    msg.x = float(x)
    msg.y = float(y)
    msg.theta = float(theta)
    node.pose_publisher.publish(msg)


def open_camera(index):
    cap = cv2.VideoCapture(index, cv2.CAP_V4L2)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
    cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)
    cap.set(cv2.CAP_PROP_FOCUS, CAMERA_FOCUS)
    cap.set(cv2.CAP_PROP_FPS, 10)
    return cap


def configure_cameras():
    for idx, zoom in ((CAMERA_INDEX_1, CAMERA_ZOOM_1), (CAMERA_INDEX_2, CAMERA_ZOOM_2)):
        dev = f"/dev/video{idx}"
        subprocess.run(["v4l2-ctl", "-d", dev, "-c", "focus_automatic_continuous=0"], check=False)
        subprocess.run(["v4l2-ctl", "-d", dev, "-c", f"focus_absolute={CAMERA_FOCUS}"], check=False)
        subprocess.run(["v4l2-ctl", "-d", dev, "-c", f"sharpness={CAMERA_SHARPNESS}"], check=False)
        subprocess.run(["v4l2-ctl", "-d", dev, "-c", f"zoom_absolute={zoom}"], check=False)


def process_camera(cap, detector, mapper, result, key):
    """Capture and detect in one camera; store detections in result[key]."""
    ret, frame = cap.read()
    if not ret:
        result[key] = []
        return
    detections = detector.detect(frame)
    if mapper.H is None:
        mapper.compute_homography(detections)
    result[key] = detections


def main():
    rclpy.init()
    node = LocalisationNode()

    cap1 = open_camera(CAMERA_INDEX_1)
    cap2 = open_camera(CAMERA_INDEX_2)

    configure_cameras()

    detector = ArucoDetector()
    mapper1 = HomographyMapper()
    mapper2 = HomographyMapper()

    mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT)
    mqtt_client.loop_start()

    # tracks last known pose per robot
    active_robots = {}

    while True:
        result = {}
        t1 = threading.Thread(target=process_camera, args=(cap1, detector, mapper1, result, "cam1"))
        t2 = threading.Thread(target=process_camera, args=(cap2, detector, mapper2, result, "cam2"))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        poses = {}

        for det in result.get("cam1", []):
            if det["id"] in CALIBRATION_IDS:
                continue
            world = mapper1.pixel_to_world(det["x_pixel"], det["y_pixel"])
            if world is not None:
                poses[det["id"]] = (world[0], world[1], det["theta_image"])

        for det in result.get("cam2", []):
            if det["id"] in CALIBRATION_IDS:
                continue
            if det["id"] in poses:
                continue
            world = mapper2.pixel_to_world(det["x_pixel"], det["y_pixel"])
            if world is not None:
                poses[det["id"]] = (world[0], world[1], det["theta_image"])

        # event-driven publishing
        for robot_id, (x_w, y_w, theta) in poses.items():
            x_w = float(x_w)
            y_w = float(y_w)
            theta = float(theta)

            if robot_id not in active_robots:
                active_robots[robot_id] = (x_w, y_w, theta)
                event = "ADD"
            else:
                old_x, old_y, old_theta = active_robots[robot_id]
                if (abs(old_x - x_w) > POSITION_THRESHOLD or
                        abs(old_y - y_w) > POSITION_THRESHOLD or
                        abs(old_theta - theta) > ANGLE_THRESHOLD):
                    active_robots[robot_id] = (x_w, y_w, theta)
                    event = "UPDATE"
                else:
                    continue

            print(f"[{event}] ID {robot_id} → World: ({x_w:.2f}, {y_w:.2f}), theta: {theta:.2f}")

            publish_pose(node, robot_id, x_w, y_w, theta)

            topic = f"{MQTT_TOPIC_PREFIX}{robot_id}"
            payload = json.dumps({
                "x": round(x_w, 3),
                "y": round(y_w, 3),
                "theta": round(theta, 3)
            })
            mqtt_client.publish(topic, payload)

        # REMOVE robots no longer visible
        missing = set(active_robots.keys()) - set(poses.keys())
        for robot_id in missing:
            del active_robots[robot_id]
            print(f"[REMOVE] ID {robot_id}")

        if not cap1.isOpened() and not cap2.isOpened():
            break

    cap1.release()
    cap2.release()
    mqtt_client.loop_stop()
    mqtt_client.disconnect()
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
