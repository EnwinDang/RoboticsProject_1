# Global Robot Localisation using Vision (ROS2 + ArUco)

Vision-based localisation system for multiple robots using ArUco markers, OpenCV, ROS2, and MQTT.

---

## Features

- Real-time ArUco marker detection
- Homography-based pixel → world coordinate mapping
- Robot pose estimation (x, y, theta)
- Event-driven updates (ADD / UPDATE / REMOVE)
- ROS2 topic publishing (`/robots/pose`)
- MQTT publishing (`city/robots/tag{id}`)
- Dual camera support with automatic merge

---

## Hardware

- Jetson Orin Nano
- 2x USB cameras (`/dev/video4` right, `/dev/video0` left)
(Voeg hier een foto toe van de usb poorten)
- Robots with ArUco markers (IDs 10+)
- 6 fixed calibration markers (IDs 0–5)

---

## Installation

### 1. Clone and set up virtual environment

```bash
git clone https://github.com/EnwinDang/RoboticsProject_1.git
cd RoboticsProject_1
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
```

### 2. Install Python dependencies

```bash
pip install opencv-contrib-python numpy paho-mqtt
```

For debugging tools (camera stream):

```bash
pip install flask
```

### 3. Configure environment variables

Create a `.env` file in the repo root:

```
FTP_HOST=ftp.botopiabe.webhosting.be
FTP_USER=dashboard@botopiabe
FTP_PASSWORD=...
FTP_REMOTE_DIR=/cams
FTP_REMOTE_NAME=camera_snapshot.jpg
MQTT_USERNAME=Robot
MQTT_PASSWORD=...
API_KEY=...
```

Contact the team for the credentials.

---

## Configuration

Edit `global_localisation/config.py` for world dimensions, camera indices, and zoom. MQTT broker and credentials are loaded from `.env`.

---

## Running the System

### One-time setup — auto-source ROS2 on login (per machine)

If ROS2 is not automatically sourced on your machine, run this once:

```bash
echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc
source ~/.bashrc
```

### Run

`main.py` is started/stopped via the control API — do not run it directly.

Start the control API (runs as systemd service automatically on boot):

```bash
sudo systemctl start control-api
```

Start/stop localisation via HTTP or MQTT — see `docs/integration_guide.md`.

---

## ROS2 Topics

| Topic | Type | Description |
|---|---|---|
| `/robots/pose` | `geometry_msgs/Pose2D` | Active robot poses |
| `/camera/image` | `sensor_msgs/Image` | Raw camera frames (via camera_node) |
| `/map/image` | `sensor_msgs/Image` | Warped map image (via homography_node) |

Monitor poses:

```bash
source /opt/ros/humble/setup.bash
ros2 topic echo /robots/pose
```

---

## MQTT

Robot positions are published to HiveMQ cloud on topic `city/robots/tag{id}`:

```json
{"x": 2.14, "y": 1.39, "theta": 1.57}
```

See `docs/integration_guide.md` for broker details and credentials.

---

## Project Structure

```
global_localisation/
├── main.py                     # Robot detection + MQTT publishing
├── config.py                   # All configuration
├── mapping/
│   └── homography.py           # HomographyMapper class
├── vision/
│   └── detector.py             # ArucoDetector class
└── tools/
    ├── utils.py                    # Shared camera/detection utilities
    ├── control_api.py              # HTTP + MQTT control API (always-on service)
    ├── camera_snapshot_ftp.py      # One-shot FTP upload (run via cronjob every minute)
    ├── camera_test.py              # Live dual-camera stream for debugging
    ├── aruco_generate.py           # Generate ArUco marker images
    └── generate_calibration_pdf.py # Generate printable ArUco PDF
```

---

## Debugging

### Live camera stream (debug)

```bash
cd global_localisation && python tools/camera_test.py
```

Open SSH tunnel on Mac: `ssh -L 8082:localhost:8082 jetson@<ip>`
Then open `http://localhost:8082` in browser.

### FTP snapshot

A cronjob runs `camera_snapshot_ftp.py` every minute. It uploads a top-down world-view image to:
```
http://botopiabe.webhosting.be/cams/camera_snapshot.jpg
```
The cronjob automatically skips when `main.py` is running (lock file mechanism).

---

## Documentation

- `docs/architecture.md` — system architecture and data flow
- `docs/calibration.md` — marker layout and homography calibration
- `docs/mqtt.md` — MQTT interface for other teams
- `docs/integration_guide.md` — HTTP control API, FTP image, MQTT — full guide for the frontend team
