import cv2
import cv2.aruco as aruco
import numpy as np
import os
import sys

DICTIONARY = aruco.DICT_4X4_50
MARKER_SIZE = 600
BORDER_SIZE = 100  # extra white border (pixels)
OUTPUT_DIR = "markers"

GROUPS = {
    "calibration": range(0, 6),
    "robots": range(10, 30)
}

def generate_markers(group_name):
    if group_name not in GROUPS:
        print("Invalid group. Use: calibration or robots")
        return

    aruco_dict = aruco.getPredefinedDictionary(DICTIONARY)

    folder = os.path.join(OUTPUT_DIR, group_name)
    os.makedirs(folder, exist_ok=True)

    for marker_id in GROUPS[group_name]:
        marker = aruco.generateImageMarker(
            aruco_dict,
            marker_id,
            MARKER_SIZE
        )

        # Create larger white canvas
        canvas_size = MARKER_SIZE + 2 * BORDER_SIZE
        canvas = np.ones((canvas_size, canvas_size), dtype="uint8") * 255

        # Place marker in center
        canvas[BORDER_SIZE:BORDER_SIZE+MARKER_SIZE,
               BORDER_SIZE:BORDER_SIZE+MARKER_SIZE] = marker

        filename = os.path.join(folder, f"marker_{marker_id}.png")
        cv2.imwrite(filename, canvas)

        print(f"Generated {group_name} marker {marker_id}")

    print("Done.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python generate_markers.py [calibration|robots]")
    else:
        generate_markers(sys.argv[1])
