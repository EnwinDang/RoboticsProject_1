# System Architecture

This project implements a **vision-based global localisation system** for multiple mobile robots using **ArUco markers, OpenCV, and ROS2**.

The system runs on a **Jetson Orin Nano** with two USB cameras and processes camera images to detect robots and estimate their positions in a shared map.

---

# Processing Pipeline

All processing runs in a single `main.py` loop:

```
Camera 1 (video4)       Camera 2 (video0)
       ↓                        ↓
 ArUco detection          ArUco detection
       ↓                        ↓
 HomographyMapper 1       HomographyMapper 2
       ↓                        ↓
 pixel → world coords     pixel → world coords
              ↘          ↙
           pose merge
               ↓
        /robots/pose  (ROS2)
        city/robots/tag{id}  (MQTT)
```

---

# Data Flow

1. Both cameras capture frames simultaneously at 2560×1440 (MJPG).
2. ArUco markers are detected in each frame.
3. Calibration markers (IDs 0–5) are used to compute a homography per camera.
4. Robot markers (IDs 10+) are mapped to world coordinates using the homography.
5. Camera 1 has priority; camera 2 only fills in robots not seen by camera 1.
6. Poses are published event-driven (ADD / UPDATE / REMOVE) via ROS2 and MQTT.

---

# Robot Pose Representation

Robot pose uses:

```
(x, y, θ)
```

| Variable | Meaning                      |
| -------- | ---------------------------- |
| x        | robot position in meters     |
| y        | robot position in meters     |
| θ        | robot orientation in radians |

---

# System Hardware

- **Jetson Orin Nano**
- **2x USB cameras** mounted overhead (`/dev/video4` right, `/dev/video0` left)
- **Mobile robots with ArUco markers** (IDs 10+)
- **6 fixed calibration markers** (IDs 0–5)

---

# ROS2 Topics

| Topic        | Type                 | Description    |
|--------------|----------------------|----------------|
| /robots/pose | geometry_msgs/Pose2D | Robot pose     |

---

# Design Goals

The architecture is designed to:

- support multiple robots simultaneously
- allow real-time localisation across the full 6m × 3m map
- allow robots to share positions via MQTT
- render a seamless top-down world view from two cameras

---

# Multi-Camera World View

Both cameras are rendered into a single top-down canvas (1200×600 px, 200 px/m) using `cv2.warpPerspective`. Each camera owns its half of the canvas — the split is at x = 3m.

```
Camera 1 (video4)  │  Camera 2 (video0)
      x: 0–3m         │     x: 3–6m
```

This view is available live via `tools/camera_stream.py` and as periodic FTP snapshots via `tools/camera_snapshot_ftp.py`.
