import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import rclpy
from rclpy.node import Node

from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import cv2

from vision.detector import ArucoDetector
from mapping.homography import HomographyMapper
from config import WORLD_WIDTH, WORLD_HEIGHT


PIXELS_PER_METER = 100
MAP_WIDTH = int(WORLD_WIDTH * PIXELS_PER_METER)
MAP_HEIGHT = int(WORLD_HEIGHT * PIXELS_PER_METER)


class HomographyNode(Node):

    def __init__(self):
        super().__init__('homography_node')

        self.bridge = CvBridge()

        self.subscription = self.create_subscription(
            Image,
            '/camera/image',
            self.image_callback,
            10
        )

        self.publisher = self.create_publisher(
            Image,
            '/map/image',
            10
        )

        self.detector = ArucoDetector()
        self.mapper = HomographyMapper()

        self.get_logger().info("Homography node started")

    def image_callback(self, msg):

        frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')

        detections = self.detector.detect(frame)
        self.mapper.compute_homography(detections)

        if self.mapper.H is None:
            return

        warped = cv2.warpPerspective(frame, self.mapper.H, (MAP_WIDTH, MAP_HEIGHT))

        map_msg = self.bridge.cv2_to_imgmsg(warped, encoding="bgr8")
        self.publisher.publish(map_msg)


def main(args=None):
    rclpy.init(args=args)
    node = HomographyNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
