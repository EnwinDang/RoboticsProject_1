import cv2
from vision.detector import ArucoDetector
from mapping.homography import HomographyMapper
from config import CAMERA_INDEX


def main():
    cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_V4L2)
    detector = ArucoDetector()
    mapper = HomographyMapper()

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        detections = detector.detect(frame)

        # Try to compute homography
        mapper.compute_homography(detections)

        for det in detections:
            world = mapper.pixel_to_world(
                det["x_pixel"], det["y_pixel"]
            )

            if world is not None:
                x_w, y_w = world
                print(
                    f"ID {det['id']} → "
                    f"World: ({x_w:.2f}, {y_w:.2f}), "
                    f"theta: {det['theta_image']:.2f}"
                )

    cap.release()


if __name__ == "__main__":
    main()
