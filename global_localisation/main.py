import cv2
from vision.detector import ArucoDetector
from mapping.homography import HomographyMapper


def main():
    cap = cv2.VideoCapture(
        "nvarguscamerasrc ! "
        "video/x-raw(memory:NVMM), width=1280, height=720, framerate=30/1 ! "
        "nvvidconv ! video/x-raw, format=BGRx ! "
        "videoconvert ! video/x-raw, format=BGR ! "
        "appsink drop=true",
        cv2.CAP_GSTREAMER
    )
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
                    f"World: ({x_w:.2f}, {y_w:.2f})"
                )

        cv2.imshow("Frame", frame)

        if cv2.waitKey(1) == 27:
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
