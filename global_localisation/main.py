import json
import sys
import os
import threading

import paho.mqtt.client as mqtt
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Pose2D

from mapping.homography import HomographyMapper
from config import (
    CAMERA_INDEX_1, CAMERA_INDEX_2,
    CALIBRATION_IDS,
    MQTT_BROKER, MQTT_PORT, MQTT_TOPIC_PREFIX,
    POSITION_THRESHOLD, ANGLE_THRESHOLD,
)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "tools"))
from utils import open_camera, configure_cameras, detect_and_draw


class LocalisationNode(Node):
    def __init__(self):
        super().__init__('localisation_node')
        self.pose_publisher = self.create_publisher(Pose2D, '/robots/pose', 10)

    def publish_pose(self, x, y, theta):
        msg = Pose2D()
        msg.x = float(x)
        msg.y = float(y)
        msg.theta = float(theta)
        self.pose_publisher.publish(msg)


def main():
    import subprocess
    subprocess.run(["sudo", "systemctl", "stop", "camera-ftp"], check=False)

    rclpy.init()
    node = LocalisationNode()

    cap1 = open_camera(CAMERA_INDEX_1)
    cap2 = open_camera(CAMERA_INDEX_2)
    configure_cameras(CAMERA_INDEX_1, CAMERA_INDEX_2)

    mapper1 = HomographyMapper()
    mapper2 = HomographyMapper()

    mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT)
    mqtt_client.loop_start()

    active_robots = {}
    missing_count = {}  # frames a robot has been consecutively missing
    REMOVE_THRESHOLD = 5

    while True:
        result = {}

        def read_cam(cap, mapper, key):
            ret, frame = cap.read()
            if not ret:
                result[key] = []
                return
            _, detections = detect_and_draw(frame)
            if mapper.H is None:
                mapper.compute_homography(detections)
            result[key] = detections

        t1 = threading.Thread(target=read_cam, args=(cap1, mapper1, "cam1"))
        t2 = threading.Thread(target=read_cam, args=(cap2, mapper2, "cam2"))
        t1.start(); t2.start()
        t1.join(); t2.join()

        poses = {}
        for det in result.get("cam1", []):
            if det["id"] in CALIBRATION_IDS:
                continue
            world = mapper1.pixel_to_world(det["x_pixel"], det["y_pixel"])
            if world is not None:
                poses[det["id"]] = (world[0], world[1], det["theta_image"])

        for det in result.get("cam2", []):
            if det["id"] in CALIBRATION_IDS or det["id"] in poses:
                continue
            world = mapper2.pixel_to_world(det["x_pixel"], det["y_pixel"])
            if world is not None:
                poses[det["id"]] = (world[0], world[1], det["theta_image"])

        for robot_id, (x_w, y_w, theta) in poses.items():
            x_w, y_w, theta = float(x_w), float(y_w), float(theta)

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
            node.publish_pose(x_w, y_w, theta)
            mqtt_client.publish(
                f"{MQTT_TOPIC_PREFIX}{robot_id}",
                json.dumps({"x": round(x_w, 3), "y": round(y_w, 3), "theta": round(theta, 3)})
            )

        for robot_id in set(active_robots) - set(poses):
            missing_count[robot_id] = missing_count.get(robot_id, 0) + 1
            if missing_count[robot_id] >= REMOVE_THRESHOLD:
                del active_robots[robot_id]
                missing_count.pop(robot_id, None)
                print(f"[REMOVE] ID {robot_id}")

        for robot_id in set(poses):
            missing_count.pop(robot_id, None)

    cap1.release()
    cap2.release()
    mqtt_client.loop_stop()
    mqtt_client.disconnect()
    node.destroy_node()
    rclpy.shutdown()
    subprocess.run(["sudo", "systemctl", "start", "camera-ftp"], check=False)


if __name__ == "__main__":
    main()
