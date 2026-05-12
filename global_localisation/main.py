import json
import logging
import signal
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
    MQTT_BROKER, MQTT_PORT, MQTT_TLS, MQTT_USERNAME, MQTT_PASSWORD, MQTT_TOPIC_PREFIX,
    POSITION_THRESHOLD, ANGLE_THRESHOLD,
    WORLD_WIDTH, WORLD_HEIGHT,
)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "tools"))
from utils import open_camera, configure_cameras, detect_and_draw

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


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

    log.info("Stopping camera-ftp service...")
    subprocess.run(["sudo", "systemctl", "stop", "camera-ftp"], check=False)

    log.info("Initialising ROS2...")
    rclpy.init()
    node = LocalisationNode()
    log.info("ROS2 ready")

    log.info(f"Opening cameras (index {CAMERA_INDEX_1} and {CAMERA_INDEX_2})...")
    cap1 = open_camera(CAMERA_INDEX_1)
    cap2 = open_camera(CAMERA_INDEX_2)
    if not cap1.isOpened():
        log.error(f"Cannot open camera {CAMERA_INDEX_1}")
    if not cap2.isOpened():
        log.error(f"Cannot open camera {CAMERA_INDEX_2}")
    log.info("Cameras opened, applying hardware settings...")
    configure_cameras(CAMERA_INDEX_1, CAMERA_INDEX_2)
    log.info("Cameras configured")

    mapper1 = HomographyMapper()
    mapper2 = HomographyMapper()

    log.info(f"Connecting to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}...")
    mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    mqtt_connected = False
    try:
        if MQTT_TLS:
            mqtt_client.tls_set()
        mqtt_client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
        mqtt_client.loop_start()
        mqtt_connected = True
        log.info("MQTT connected")
    except Exception as e:
        log.error(f"MQTT connection failed: {e} — continuing without MQTT")

    active_robots = {}
    missing_count = {}
    confirm_count = {}  # frames a candidate robot has been seen consecutively
    REMOVE_THRESHOLD = 15
    CONFIRM_THRESHOLD = 8  # frames before a new robot is published
    MAX_JUMP = 0.5         # metres — max position jump between frames
    frame_count = 0

    log.info("Starting detection loop — waiting for calibration markers...")

    def handle_sigint(sig, frame):
        log.info("Shutting down...")
        cap1.release()
        cap2.release()
        if mqtt_connected:
            mqtt_client.loop_stop()
            mqtt_client.disconnect()
        node.destroy_node()
        rclpy.shutdown()
        subprocess.run(["sudo", "systemctl", "start", "camera-ftp"], check=False)
        os._exit(0)

    signal.signal(signal.SIGINT, handle_sigint)

    while True:
        result = {}
        frame_count += 1

        def read_cam(cap, mapper, key, cam_index):
            ret, frame = cap.read()
            if not ret:
                log.warning(f"Camera {cam_index}: failed to read frame")
                result[key] = []
                return
            _, detections = detect_and_draw(frame)
            cal_ids = sorted(d["id"] for d in detections if d["id"] in CALIBRATION_IDS)
            rob_ids = sorted(d["id"] for d in detections if d["id"] not in CALIBRATION_IDS)
            if frame_count % 10 == 0:
                h_status = "ready" if mapper.H is not None else "waiting for 4+ markers"
                log.info(f"CAM{cam_index}: cal={cal_ids} rob={rob_ids} homography={h_status}")
            if mapper.H is None:
                if len(cal_ids) >= 4:
                    log.info(f"CAM{cam_index}: computing homography with markers {cal_ids}")
                    mapper.compute_homography(detections)
                    if mapper.H is not None:
                        log.info(f"CAM{cam_index}: homography computed successfully")
                else:
                    if frame_count % 30 == 0:
                        log.warning(f"CAM{cam_index}: need 4 calibration markers, only see {cal_ids}")
            result[key] = detections

        t1 = threading.Thread(target=read_cam, args=(cap1, mapper1, "cam1", CAMERA_INDEX_1))
        t2 = threading.Thread(target=read_cam, args=(cap2, mapper2, "cam2", CAMERA_INDEX_2))
        t1.start(); t2.start()
        t1.join(); t2.join()

        poses = {}
        def in_bounds(x, y):
            return 0 <= x <= WORLD_WIDTH and 0 <= y <= WORLD_HEIGHT

        for det in result.get("cam1", []):
            if det["id"] in CALIBRATION_IDS:
                continue
            world = mapper1.pixel_to_world(det["x_pixel"], det["y_pixel"])
            if world is not None and in_bounds(world[0], world[1]):
                poses[det["id"]] = (world[0], world[1], det["theta_image"])

        for det in result.get("cam2", []):
            if det["id"] in CALIBRATION_IDS or det["id"] in poses:
                continue
            world = mapper2.pixel_to_world(det["x_pixel"], det["y_pixel"])
            if world is not None and in_bounds(world[0], world[1]):
                poses[det["id"]] = (world[0], world[1], det["theta_image"])

        for robot_id, (x_w, y_w, theta) in poses.items():
            x_w, y_w, theta = float(x_w), float(y_w), float(theta)

            if robot_id not in active_robots:
                confirm_count[robot_id] = confirm_count.get(robot_id, 0) + 1
                if confirm_count[robot_id] < CONFIRM_THRESHOLD:
                    continue
                active_robots[robot_id] = (x_w, y_w, theta)
                event = "ADD"
            else:
                confirm_count.pop(robot_id, None)
                old_x, old_y, old_theta = active_robots[robot_id]
                dist = ((old_x - x_w) ** 2 + (old_y - y_w) ** 2) ** 0.5
                if dist > MAX_JUMP:
                    log.warning(f"ID {robot_id} jumped {dist:.2f}m — ignored")
                    continue
                if (abs(old_x - x_w) > POSITION_THRESHOLD or
                        abs(old_y - y_w) > POSITION_THRESHOLD or
                        abs(old_theta - theta) > ANGLE_THRESHOLD):
                    active_robots[robot_id] = (x_w, y_w, theta)
                    event = "UPDATE"
                else:
                    continue

            log.info(f"[{event}] ID {robot_id} → ({x_w:.2f}, {y_w:.2f}) theta={theta:.2f}")
            node.publish_pose(x_w, y_w, theta)
            if mqtt_connected:
                try:
                    mqtt_client.publish(
                        f"{MQTT_TOPIC_PREFIX}{robot_id}",
                        json.dumps({"x": round(x_w, 3), "y": round(y_w, 3), "theta": round(theta, 3)})
                    )
                except Exception as e:
                    log.error(f"MQTT publish failed: {e}")

        for robot_id in set(active_robots) - set(poses):
            missing_count[robot_id] = missing_count.get(robot_id, 0) + 1
            if missing_count[robot_id] >= REMOVE_THRESHOLD:
                del active_robots[robot_id]
                missing_count.pop(robot_id, None)
                log.info(f"[REMOVE] ID {robot_id}")

        for robot_id in set(poses):
            missing_count.pop(robot_id, None)


if __name__ == "__main__":
    main()
