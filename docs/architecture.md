# System Architecture

This project implements a **vision-based global localisation system** for multiple mobile robots using **ArUco markers, OpenCV, and ROS2**.

The system runs on a **Jetson Orin Nano** and processes camera images to detect robots and estimate their positions in a shared map.

---

# Processing Pipeline

The localisation pipeline is composed of several ROS2 nodes:

```
camera_node
      ↓
/camera/image
      ↓
homography_node
      ↓
/map/image
      ↓
robot_detector_node
      ↓
/robots/pose
```

Each node performs a specific task.

| Node                | Responsibility                                |
| ------------------- | --------------------------------------------- |
| camera_node         | Captures frames from the USB camera           |
| homography_node     | Converts camera perspective to a top-down map |
| robot_detector_node | Detects robot ArUco markers                   |
| robot_tracker_node  | Tracks robots and publishes pose              |

---

# Data Flow

1. The **camera node** captures images from the USB camera.
2. Images are published to the ROS2 topic:

```
/camera/image
```

3. The **homography node** corrects the camera perspective using calibration markers.

This produces a **top-down map view**:

```
/map/image
```

4. The **robot detector node** detects robot ArUco markers and calculates:

```
x position
y position
theta (orientation)
```

5. The robot pose is published via:

```
/robots/pose
```

---

# Robot Pose Representation

Robot pose uses:

```
(x, y, θ)
```

Where:

| Variable | Meaning                      |
| -------- | ---------------------------- |
| x        | robot position in meters     |
| y        | robot position in meters     |
| θ        | robot orientation in radians |

---

# System Hardware

The system runs on:

- **Jetson Orin Nano**
- **USB camera** mounted above the map
- **Mobile robots with ArUco markers**

---

# ROS2 Topics

| Topic         | Type                 | Description              |
| ------------- | -------------------- | ------------------------ |
| /camera/image | sensor_msgs/Image    | Raw camera image         |
| /map/image    | sensor_msgs/Image    | Homography corrected map |
| /robots/pose  | geometry_msgs/Pose2D | Robot pose               |

---

# Design Goals

The architecture is designed to:

- support multiple robots
- allow real-time localisation
- allow robots to share positions
- scale to multiple cameras

---

# Future Multi-Camera Architecture

To cover the full **6m × 3m map**, the system will later support **two cameras**.

Each camera will process half of the environment.

```
camera_node_1          camera_node_2
      ↓                      ↓
/camera1/image        /camera2/image
      ↓                      ↓
homography_node_1    homography_node_2
      ↓                      ↓
/map1/image           /map2/image
        \              /
         \            /
          map_merge_node
                ↓
             /map/full
                ↓
        robot_detector_node
                ↓
           /robots/pose
```

This allows full map coverage and improved robot tracking.

