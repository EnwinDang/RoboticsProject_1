import cv2
import cv2.aruco as aruco
import numpy as np

# map layout in meters
MAP_MARKERS = {
    0: (0,0),
    1: (3,0),
    2: (6,0),
    3: (0,3),
    4: (3,3),
    5: (6,3)
}

PIXELS_PER_METER = 100


def compute_homography(frame):

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    aruco_dict = aruco.getPredefinedDictionary(aruco.DICT_4X4_50)
    detector = aruco.ArucoDetector(aruco_dict)

    corners, ids, _ = detector.detectMarkers(gray)

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

        # expected marker size (meters)
        marker_size = 0.15

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
