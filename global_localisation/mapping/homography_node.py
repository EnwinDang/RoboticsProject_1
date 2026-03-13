import rclpy
from rclpy.node import Node

from sensor_msgs.msg import Image
from cv_bridge import CvBridge

import cv2
import cv2.aruco as aruco
import numpy as np


# Known map layout (meters) - must match physical placement
MAP_MARKERS = {
    0: (0.0, 0.0),
    1: (0.0, 3.0),
    2: (3.0, 0.0),
    3: (3.0, 3.0),
    4: (6.0, 0.0),
    5: (6.0, 3.0),
}

PIXELS_PER_METER = 100
MAP_WIDTH = int(6 * PIXELS_PER_METER)
MAP_HEIGHT = int(3 * PIXELS_PER_METER)


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

        self.aruco_dict = aruco.getPredefinedDictionary(aruco.DICT_4X4_50)
        self.detector = aruco.ArucoDetector(self.aruco_dict)

        self.get_logger().info("Homography node started")


    def compute_homography(self, frame):

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        corners, ids, _ = self.detector.detectMarkers(gray)

        if ids is None:
            return None

        ids = ids.flatten()

        src_points = []
        dst_points = []

        for i, marker_id in enumerate(ids):

            if marker_id not in MAP_MARKERS:
                continue

            marker_corners = corners[i][0]

            map_x, map_y = MAP_MARKERS[marker_id]

            marker_size = 0.15  # meters

            world_corners = [
                (map_x, map_y),
                (map_x + marker_size, map_y),
                (map_x + marker_size, map_y + marker_size),
                (map_x, map_y + marker_size)
            ]

            for j in range(4):

                px = marker_corners[j][0]
                py = marker_corners[j][1]

                src_points.append([px, py])

                wx, wy = world_corners[j]

                dst_points.append([
                    wx * PIXELS_PER_METER,
                    wy * PIXELS_PER_METER
                ])

        if len(src_points) < 4:
            return None

        src_points = np.array(src_points, dtype=np.float32)
        dst_points = np.array(dst_points, dtype=np.float32)

        H, _ = cv2.findHomography(src_points, dst_points)

        return H


    def image_callback(self, msg):

        frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')

        H = self.compute_homography(frame)

        if H is None:
            return

        warped = cv2.warpPerspective(
            frame,
            H,
            (MAP_WIDTH, MAP_HEIGHT)
        )

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
