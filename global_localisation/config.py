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

# MQTT broker
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC_PREFIX = "city/robots/tag"

# FTP upload defaults for camera snapshots
FTP_HOST = "ftp.botopiabe.webhosting.be"
FTP_USER = "dashboard@botopiabe"
FTP_PASSWORD = "botopia123!"
FTP_REMOTE_DIR = "/cams"
FTP_REMOTE_NAME = "camera_snapshot.jpg"
SNAPSHOT_INTERVAL_SECONDS = 30

# Tracking thresholds
POSITION_THRESHOLD = 0.05  # meters
ANGLE_THRESHOLD = 0.15     # radians
