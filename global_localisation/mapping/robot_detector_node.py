import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import rclpy
from rclpy.node import Node

from sensor_msgs.msg import Image
from geometry_msgs.msg import Pose2D

from cv_bridge import CvBridge

from vision.detector import ArucoDetector
from config import WORLD_WIDTH, WORLD_HEIGHT, CALIBRATION_IDS, POSITION_THRESHOLD, ANGLE_THRESHOLD


PIXELS_PER_METER = 100


class RobotDetectorNode(Node):

    def __init__(self):
        super().__init__('robot_detector')

        self.bridge = CvBridge()

        self.subscription = self.create_subscription(
            Image,
            '/map/image',
            self.image_callback,
            10
        )

        self.pose_publisher = self.create_publisher(
            Pose2D,
            '/robots/pose',
            10
        )

        self.detector = ArucoDetector()
        self.active_robots = {}

        self.get_logger().info("Robot Detector Node started")

    def image_callback(self, msg):

        frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')

        detections = self.detector.detect(frame)

        detected_ids = set()

        for det in detections:

            marker_id = det["id"]

            if marker_id in CALIBRATION_IDS:
                continue

            detected_ids.add(marker_id)

            x_m = det["x_pixel"] / PIXELS_PER_METER
            y_m = det["y_pixel"] / PIXELS_PER_METER
            theta = det["theta_image"]

            pose = (x_m, y_m, theta)

            if marker_id not in self.active_robots:

                self.active_robots[marker_id] = pose
                self.publish_pose(pose)
                self.get_logger().info(f"ADD Robot {marker_id} → x={x_m:.2f} y={y_m:.2f}")

            else:

                old_pose = self.active_robots[marker_id]

                if (abs(old_pose[0] - x_m) > POSITION_THRESHOLD or
                        abs(old_pose[1] - y_m) > POSITION_THRESHOLD or
                        abs(old_pose[2] - theta) > ANGLE_THRESHOLD):

                    self.active_robots[marker_id] = pose
                    self.publish_pose(pose)
                    self.get_logger().info(f"UPDATE Robot {marker_id} → x={x_m:.2f} y={y_m:.2f}")

        # remove robots no longer visible
        for marker_id in set(self.active_robots.keys()) - detected_ids:
            del self.active_robots[marker_id]
            self.get_logger().info(f"REMOVE Robot {marker_id}")

    def publish_pose(self, pose):
        x, y, theta = pose
        msg = Pose2D()
        msg.x = float(x)
        msg.y = float(y)
        msg.theta = float(theta)
        self.pose_publisher.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = RobotDetectorNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
