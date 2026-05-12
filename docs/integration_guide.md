# Integration Guide

This document explains how the system works and how the frontend team can integrate with it.

---

## How it works

The Jetson runs two services:

| Service | What it does | When |
|---------|-------------|------|
| FTP cronjob | Captures both cameras, renders top-down world view, uploads image to FTP every minute | When localisation is stopped |
| `main.py` | Detects robots, publishes positions via MQTT | Only when started via API |

When `main.py` is running, it creates a lock file — the FTP cronjob detects this and skips. When `main.py` stops, the lock file is removed and FTP uploads resume automatically.

---

## How the FTP works

A cron job runs every minute. When localisation is not active it:

1. Reads both cameras
2. Detects the calibration markers (IDs 0–5) to compute the homography
3. Warps both camera frames into a single top-down world view (6m × 3m)
4. Uploads the image to the FTP server, overwriting the previous one

The image is always available at:

```
http://botopiabe.webhosting.be/cams/camera_snapshot.jpg
```

This image updates every minute. It shows the full field from above with ArUco markers highlighted. It does **not** show real-time robot positions — it's a static snapshot.

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

> **Note:** `jetson-dang.local` resolves via mDNS and works as long as the frontend and Jetson are on the same network. If mDNS is blocked (e.g. some school networks), use the Jetson's IP address directly. The control API must be running: `python tools/control_api.py`

### Start localisation

```
POST /start
```

Creates a lock file and starts robot detection + MQTT publishing. The FTP cronjob detects the lock and skips until localisation stops.

**Response:**
```json
{"status": "started"}
```

### Stop localisation

```
POST /stop
```

Stops robot detection and removes the lock file. The FTP cronjob resumes automatically on the next minute.

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

- A robot must be detected in **8 consecutive frames** before it is published as appeared (filters false positives)
- A robot must be **missing for 15 consecutive frames** before it is published as disappeared
- Positions outside the field bounds (0–6m × 0–3m) are ignored automatically

Subscribe via HiveMQ cloud:

```javascript
const client = mqtt.connect('mqtts://e26688c7fd4c4f238a2e04f8d12199af.s1.eu.hivemq.cloud:8883', {
  username: 'Robot',
  password: 'Password123.'
})
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
