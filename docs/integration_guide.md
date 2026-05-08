# Integration Guide

This document explains how the system works and how the frontend team can integrate with it.

---

## How it works

The Jetson runs two services:

| Service | What it does | When |
|---------|-------------|------|
| `camera-ftp` | Captures both cameras, renders top-down world view, uploads image to FTP every 30s | Always on |
| `main.py` | Detects robots, publishes positions via ROS2 + MQTT | Only when started via API |

When `main.py` is running, `camera-ftp` is paused — both need the cameras and can't run at the same time. When `main.py` stops, `camera-ftp` resumes automatically.

---

## How the FTP works

The `camera-ftp` service runs continuously in the background. Every 30 seconds it:

1. Reads both cameras
2. Detects the calibration markers (IDs 0–5) to compute the homography
3. Warps both camera frames into a single top-down world view (6m × 3m)
4. Uploads the image to the FTP server, overwriting the previous one

The image is always available at:

```
http://botopiabe.webhosting.be/cams/camera_snapshot.jpg
```

This image updates every 30 seconds. It shows the full field from above with ArUco markers highlighted. It does **not** show real-time robot positions — it's a static snapshot.

To display it with auto-refresh in a browser:

```html
<img id="map" src="http://botopiabe.webhosting.be/cams/camera_snapshot.jpg">
<script>
  setInterval(() => {
    document.getElementById('map').src =
      'http://botopiabe.webhosting.be/cams/camera_snapshot.jpg?t=' + Date.now();
  }, 5000);
</script>
```

---

## Control API

The Jetson exposes a HTTP API on port **8081** to start/stop the localisation system.

Base URL:
```
http://jetson-dang.local:8081
```

### Start localisation

```
POST /start
```

Stops the FTP service and starts robot detection + ROS2 + MQTT publishing.

**Response:**
```json
{"status": "started"}
```

### Stop localisation

```
POST /stop
```

Stops robot detection and restarts the FTP service.

**Response:**
```json
{"status": "stopped"}
```

### Get status

```
GET /status
```

**Response:**
```json
{"localisation": "running", "ftp": "stopped"}
```
or
```json
{"localisation": "stopped", "ftp": "running"}
```

---

## Robot positions (MQTT)

When localisation is running, robot positions are published to MQTT:

```
city/robots/tag{id}
```

Example message on `city/robots/tag11`:
```json
{"x": 3.62, "y": 1.71, "theta": -0.10}
```

| Field | Unit | Description |
|-------|------|-------------|
| x | meters | Position along width (0–6m) |
| y | meters | Position along height (0–3m) |
| theta | radians | Orientation (0 = facing right) |

Messages are only published when a robot **appears**, **moves significantly** (>5cm or >0.15 rad), or **disappears**.

Subscribe from anywhere on the network:

```javascript
const client = mqtt.connect('mqtt://jetson-dang.local:1883')
client.subscribe('city/robots/#')
client.on('message', (topic, message) => {
  const id = topic.split('tag')[1]
  const pos = JSON.parse(message)
  console.log(`Robot ${id}: x=${pos.x}, y=${pos.y}, theta=${pos.theta}`)
})
```

---

## Typical frontend flow

1. Page loads → call `GET /status` to show current state
2. Show FTP image while localisation is stopped
3. User clicks **Start** → call `POST /start` → listen to MQTT for live robot positions
4. User clicks **Stop** → call `POST /stop` → FTP image resumes updating
5. Poll `GET /status` every few seconds to keep the UI in sync

---

## Map coordinate system

```
(0,0) ──────────────────── (6,0)
  │                            │
  │         6m × 3m            │
  │                            │
(0,3) ──────────────────── (6,3)
```

- Origin `(0,0)` = top-left corner
- `x` increases to the right
- `y` increases downward
