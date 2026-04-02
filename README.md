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
- 2x USB cameras (`/dev/video4` left, `/dev/video0` right)
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

### 3. Install and start MQTT broker

```bash
sudo apt install mosquitto mosquitto-clients
sudo systemctl start mosquitto
```

To allow other devices on the network to connect, add to `/etc/mosquitto/mosquitto.conf`:

```
listener 1883 0.0.0.0
allow_anonymous true
```

Then restart:

```bash
sudo systemctl restart mosquitto
```

> Mosquitto is enabled on boot — no need to start it manually after the initial setup.

---

## Configuration

Edit `global_localisation/config.py`:

```python
WORLD_WIDTH = 6.0        # map width in meters
WORLD_HEIGHT = 3.0       # map height in meters
CALIBRATION_IDS = [0, 1, 2, 3, 4, 5]  # fixed marker IDs
CAMERA_INDEX_1 = 4       # left camera (/dev/video4)
CAMERA_INDEX_2 = 0       # right camera (/dev/video0)
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC_PREFIX = "city/robots/tag"
```

---

## Running the System

### One-time setup — auto-source ROS2 on login (per machine)

If ROS2 is not automatically sourced on your machine, run this once:

```bash
echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc
source ~/.bashrc
```

### Run

```bash
cd ~/RoboticsProject_1/global_localisation
python main.py
```

### Expected terminal output

```
[ADD]    ID 10 → World: (1.20, 0.80), theta: 0.12
[UPDATE] ID 10 → World: (1.45, 0.95), theta: 0.15
[REMOVE] ID 10
```

Only prints when a robot appears, moves significantly (>5cm or >0.15 rad), or disappears.

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

Robot positions are published to `city/robots/tag{id}` as JSON:

```json
{"x": 2.14, "y": 1.39, "theta": 1.57}
```

Any device on the same network can subscribe — see `docs/mqtt.md` for details.

---

## Project Structure

```
global_localisation/
├── main.py                     # Entry point (cameras + detection + ROS2 + MQTT)
├── config.py                   # All configuration
├── vision/
│   ├── detector.py             # ArucoDetector class
│   └── camera_node.py          # ROS2 camera node
├── mapping/
│   ├── homography.py           # HomographyMapper class
│   ├── homography_node.py      # ROS2 homography node
│   └── robot_detector_node.py  # ROS2 robot detector node
└── tools/
    ├── aruco_generate.py           # Generate ArUco marker images
    ├── generate_calibration_pdf.py # Generate printable ArUco PDF
    └── camera_stream.py            # Live camera stream in browser (debugging)
```

---

## Debugging

### Live camera stream

View the camera feed with ArUco detections overlaid in your browser:

```bash
source .venv/bin/activate
python3 global_localisation/tools/camera_stream.py 0   # or 2 for left camera
```

Then open `http://jetson-dang.local:8080` in your browser.

> Note: stop the stream before running `main.py` — two processes cannot use the same camera simultaneously.

### Single camera mode

To run with only one camera, set the unused camera index to a non-existent value in `config.py`:

```python
CAMERA_INDEX_1 = 0    # active camera
CAMERA_INDEX_2 = 99   # disabled
```

At least 4 calibration markers (IDs 0–5) must be visible to the active camera for homography to work.

---

## Documentation

- `docs/architecture.md` — system architecture and data flow
- `docs/calibration.md` — marker layout and homography calibration
- `docs/mqtt.md` — MQTT interface for other teams
- `docs/roadmap.md` — planned features
- `docs/next_session.md` — TODO for next session
