import cv2
import numpy as np
from config import WORLD_WIDTH, WORLD_HEIGHT


class HomographyMapper:
    def __init__(self):
        self.H = None

        # Define world coordinates of calibration markers
        self.world_points = {
            0: (0.0, 0.0),
            1: (0.0, WORLD_HEIGHT),
            2: (WORLD_WIDTH / 2, 0.0),
            3: (WORLD_WIDTH / 2, WORLD_HEIGHT),
            4: (WORLD_WIDTH, 0.0),
            5: (WORLD_WIDTH, WORLD_HEIGHT),
        }

    def compute_homography(self, detections):
        pixel_pts = []
        world_pts = []

        for det in detections:
            if det["id"] in self.world_points:
                pixel_pts.append([det["x_pixel"], det["y_pixel"]])
                world_pts.append(self.world_points[det["id"]])

        if len(pixel_pts) >= 4:
            pixel_pts = np.array(pixel_pts, dtype="float32")
            world_pts = np.array(world_pts, dtype="float32")
            self.H, _ = cv2.findHomography(pixel_pts, world_pts)

    def pixel_to_world(self, x_pixel, y_pixel):
        if self.H is None:
            return None

        point = np.array([[[x_pixel, y_pixel]]], dtype="float32")
        world = cv2.perspectiveTransform(point, self.H)

        return world[0][0][0], world[0][0][1]
