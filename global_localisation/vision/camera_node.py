import rclpy
from rclpy.node import Node

import cv2

from sensor_msgs.msg import Image
from cv_bridge import CvBridge


class CameraNode(Node):

    def __init__(self):
        super().__init__('camera_node')

        self.publisher = self.create_publisher(
            Image,
            '/camera/image',
            10
        )

        self.bridge = CvBridge()

        self.cap = cv2.VideoCapture("/dev/video2", cv2.CAP_V4L2)

        self.timer = self.create_timer(0.03, self.publish_frame)

    def publish_frame(self):

        ret, frame = self.cap.read()

        if not ret:
            self.get_logger().warn("Frame not received")
            return

        msg = self.bridge.cv2_to_imgmsg(frame, encoding='bgr8')

        self.publisher.publish(msg)


def main():

    rclpy.init()

    node = CameraNode()

    rclpy.spin(node)

    node.destroy_node()

    rclpy.shutdown()


if __name__ == '__main__':
    main()
