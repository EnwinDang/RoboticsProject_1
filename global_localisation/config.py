import os

# Load .env from repo root if it exists
_env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
if os.path.exists(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())

# World dimensions (meters)
WORLD_WIDTH = 6.0
WORLD_HEIGHT = 3.0

# Calibration marker IDs
CALIBRATION_IDS = [0, 1, 2, 3, 4, 5]

# Camera indices
CAMERA_INDEX_1 = 4  # left side
CAMERA_INDEX_2 = 0  # right side

# Camera resolution
CAMERA_WIDTH = 2560
CAMERA_HEIGHT = 1440

# Camera hardware settings (applied via v4l2-ctl)
CAMERA_FOCUS = 10
CAMERA_SHARPNESS = 255
CAMERA_ZOOM_1 = 100   # camera 4 — fully zoomed out
CAMERA_ZOOM_2 = 100   # camera 0 — fully zoomed out

# World canvas rendering
WORLD_SCALE = 200      # pixels per metre
CANVAS_PADDING = 60    # empty border around the world area (pixels)
CANVAS_WIDTH = int(WORLD_WIDTH * WORLD_SCALE) + 2 * CANVAS_PADDING
CANVAS_HEIGHT = int(WORLD_HEIGHT * WORLD_SCALE) + 2 * CANVAS_PADDING

# MQTT broker
MQTT_BROKER = "e26688c7fd4c4f238a2e04f8d12199af.s1.eu.hivemq.cloud"
MQTT_PORT = 8883
MQTT_TLS = True
MQTT_USERNAME = "Robot"
MQTT_PASSWORD = "Password123."
MQTT_TOPIC_PREFIX = "city/robots/tag"

# FTP upload defaults for camera snapshots
FTP_HOST = os.getenv("FTP_HOST", "")
FTP_USER = os.getenv("FTP_USER", "")
FTP_PASSWORD = os.getenv("FTP_PASSWORD", "")
FTP_REMOTE_DIR = os.getenv("FTP_REMOTE_DIR", "/cams")
FTP_REMOTE_NAME = os.getenv("FTP_REMOTE_NAME", "camera_snapshot.jpg")
SNAPSHOT_INTERVAL_SECONDS = 30

# Tracking thresholds
POSITION_THRESHOLD = 0.05  # meters
ANGLE_THRESHOLD = 0.15     # radians
