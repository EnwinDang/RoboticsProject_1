import json
import cv2
import paho.mqtt.client as mqtt
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Pose2D

from vision.detector import ArucoDetector
from mapping.homography import HomographyMapper
from config import CAMERA_INDEX_1, CAMERA_INDEX_2, CALIBRATION_IDS, MQTT_BROKER, MQTT_PORT, MQTT_TOPIC_PREFIX, POSITION_THRESHOLD, ANGLE_THRESHOLD


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


def main():
    rclpy.init()
    node = LocalisationNode()

    cap1 = cv2.VideoCapture(CAMERA_INDEX_1, cv2.CAP_V4L2)
    cap2 = cv2.VideoCapture(CAMERA_INDEX_2, cv2.CAP_V4L2)

    detector = ArucoDetector()
    mapper1 = HomographyMapper()
    mapper2 = HomographyMapper()

    mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT)
    mqtt_client.loop_start()

    # tracks last known pose per robot
    active_robots = {}

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

        # process camera 2 (only if cam1 didn't see this robot)
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

        # event-driven publishing
        for robot_id, (x_w, y_w, theta) in poses.items():
            x_w = float(x_w)
            y_w = float(y_w)
            theta = float(theta)

            if robot_id not in active_robots:
                # ADD
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
                    continue  # no significant change, skip

            print(f"[{event}] ID {robot_id} → World: ({x_w:.2f}, {y_w:.2f}), theta: {theta:.2f}")

            # ROS2 publish
            publish_pose(node, robot_id, x_w, y_w, theta)

            # MQTT publish
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

        if not ret1 and not ret2:
            break

    cap1.release()
    cap2.release()
    mqtt_client.loop_stop()
    mqtt_client.disconnect()
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
