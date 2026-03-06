import rclpy
from rclpy.node import Node

from sensor_msgs.msg import Image
from geometry_msgs.msg import Pose2D

from cv_bridge import CvBridge
import cv2
import cv2.aruco as aruco
import numpy as np


# ---------- MAP CONFIG ----------

MAP_WIDTH_METERS = 6.0
MAP_HEIGHT_METERS = 3.0

MAP_WIDTH_PIXELS = 600
MAP_HEIGHT_PIXELS = 300

PIXELS_PER_METER = MAP_WIDTH_PIXELS / MAP_WIDTH_METERS


# ---------- MOVEMENT THRESHOLD ----------

POSITION_THRESHOLD = 0.05   # meters
ANGLE_THRESHOLD = 0.15     # radians


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

        # ---------- ARUCO ----------

        self.aruco_dict = aruco.getPredefinedDictionary(aruco.DICT_4X4_50)
        self.parameters = aruco.DetectorParameters()

        self.detector = aruco.ArucoDetector(self.aruco_dict, self.parameters)

        # ---------- ROBOT TRACKING ----------

        self.active_robots = {}

        self.get_logger().info("Robot Detector Node started")


    def image_callback(self, msg):

        frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        corners, ids, rejected = self.detector.detectMarkers(gray)

        detected_ids = set()

        if ids is None:
            ids = []

        for i, marker_id in enumerate(ids.flatten()):

            if marker_id < 10:
                continue

            detected_ids.add(marker_id)

            marker_corners = corners[i][0]

            # ---------- POSITION ----------

            center_x = np.mean(marker_corners[:,0])
            center_y = np.mean(marker_corners[:,1])

            x_m = center_x / PIXELS_PER_METER
            y_m = center_y / PIXELS_PER_METER

            # ---------- ORIENTATION ----------

            top_left = marker_corners[0]
            top_right = marker_corners[1]

            dx = top_right[0] - top_left[0]
            dy = top_right[1] - top_left[1]

            theta = np.arctan2(dy, dx)

            pose = (x_m, y_m, theta)

            # ---------- EVENT LOGIC ----------

            if marker_id not in self.active_robots:

                self.active_robots[marker_id] = pose

                self.publish_pose(marker_id, pose)

                self.get_logger().info(
                    f"ADD Robot {marker_id} → x={x_m:.2f} y={y_m:.2f}"
                )

            else:

                old_pose = self.active_robots[marker_id]

                dx = abs(old_pose[0] - x_m)
                dy = abs(old_pose[1] - y_m)
                dtheta = abs(old_pose[2] - theta)

                if dx > POSITION_THRESHOLD or dy > POSITION_THRESHOLD or dtheta > ANGLE_THRESHOLD:

                    self.active_robots[marker_id] = pose

                    self.publish_pose(marker_id, pose)

                    self.get_logger().info(
                        f"UPDATE Robot {marker_id} → x={x_m:.2f} y={y_m:.2f}"
                    )

        # ---------- REMOVE ROBOTS ----------

        current_ids = set(self.active_robots.keys())

        missing = current_ids - detected_ids

        for marker_id in missing:

            del self.active_robots[marker_id]

            self.get_logger().info(f"REMOVE Robot {marker_id}")


    def publish_pose(self, marker_id, pose):

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
