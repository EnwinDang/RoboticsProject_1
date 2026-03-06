import cv2
import cv2.aruco as aruco

# open camera
cap = cv2.VideoCapture("/dev/video2", cv2.CAP_V4L2)

if not cap.isOpened():
    print("Error: Could not open camera")
    exit()

print("Camera started")

# choose ArUco dictionary
aruco_dict = aruco.getPredefinedDictionary(aruco.DICT_4X4_50)

# detector parameters
parameters = aruco.DetectorParameters()

detector = aruco.ArucoDetector(aruco_dict, parameters)

while True:

    ret, frame = cap.read()

    if not ret:
        print("Frame grab failed")
        break

    # convert to grayscale
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # detect markers
    corners, ids, rejected = detector.detectMarkers(gray)

    if ids is not None:

        for i in range(len(ids)):

            marker_id = ids[i][0]

            # calculate center of marker
            c = corners[i][0]
            center_x = int(c[:,0].mean())
            center_y = int(c[:,1].mean())

            print(f"Marker {marker_id} detected at pixel ({center_x}, {center_y})")

    else:
        print("No markers detected")

cap.release()
