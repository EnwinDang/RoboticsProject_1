# Integration Guide

This document explains how the system operates and how the frontend team can integrate with it.

---

## How it works

The Jetson runs three services:

| Service | What it does | When |
|---------|-------------|------|
| `control_api.py` | HTTP + MQTT control interface to start/stop localisation | **Always on** |
| FTP cronjob | Opens cameras, takes snapshot, uploads to FTP, closes cameras | Every minute when localisation is stopped |
| `main.py` | Detects robots, publishes positions via MQTT | Only when started via control |

---

## Operational flow

### What always runs
`control_api.py` is the only process that runs permanently. It is set up as a systemd service and starts automatically when the Jetson boots. You never need to start it manually.

It is extremely lightweight — ~20MB RAM and ~0% CPU when idle. It only reacts to incoming HTTP requests or MQTT messages, so it has no impact on system performance.

### FTP mode (default state)
When localisation is not running, a cron job fires every minute:

1. **Opens** both cameras
2. **Warms up** for ~3 seconds to let the image stabilise and compute the homography from calibration markers
3. **Takes one snapshot** and uploads it to FTP
4. **Closes** the cameras immediately after

The cameras are only on for a few seconds per minute. This is intentional — keeping cameras open permanently is a security and resource risk. The cronjob approach means cameras are off 95% of the time.

### Localisation mode
When you send a start command:

1. `control_api.py` starts `main.py`
2. `main.py` creates a lock file at `/tmp/localisation.lock`
3. The cron job checks for this lock file every minute and **skips** if it exists — so cameras are not shared between processes
4. `main.py` opens cameras, computes homography, and publishes robot positions to MQTT continuously

### When you stop localisation
1. `main.py` shuts down and removes the lock file
2. The next cron job run (within a minute) resumes FTP uploads automatically

### Auto-stop
If no robot moves for **5 minutes**, `main.py` shuts down automatically — even if nobody pressed stop. This prevents the cameras from staying on indefinitely when the session is over. FTP uploads resume within a minute after auto-stop.

---

## What happens when the Jetson goes down

**During FTP mode:** The cron job stops. The last uploaded FTP image stays on the server — it just stops updating.

**During localisation:** `main.py` stops publishing. The lock file is stored in `/tmp/` which is cleared on reboot, so it will not block the FTP cronjob after restart.

**When the Jetson comes back online:**
- `control_api.py` restarts automatically (systemd)
- The cron job resumes automatically (persistent crontab)
- FTP uploads resume within 1 minute
- Localisation does **not** restart automatically — it must be started again via the control interface

---

## How the FTP snapshot works

The FTP image is always available at:

```
http://botopiabe.webhosting.be/cams/camera_snapshot.jpg
```

It updates every minute when localisation is stopped. It shows a top-down view of the field with ArUco markers highlighted. It does **not** show real-time robot positions.

> **Note:** If calibration markers are not detected (e.g. camera out of position), the image will show the raw camera feed with a red warning banner instead of a black screen.

To display it with auto-refresh:

```html
<img id="map" src="http://botopiabe.webhosting.be/cams/camera_snapshot.jpg">
<script>
  setInterval(() => {
    document.getElementById('map').src =
      'http://botopiabe.webhosting.be/cams/camera_snapshot.jpg?t=' + Date.now();
  }, 60000); // image updates every minute
</script>
```

---

## Control

The localisation system can be started/stopped via **HTTP API** or **MQTT**.

---

### Option 1 — HTTP API

Base URL:
```
http://jetson-dang.local:8081
```

> **Note:** If mDNS is blocked, use the Jetson's IP address directly.

All write endpoints require an API key header:
```
X-API-Key: <your-api-key>
```

#### Start
```
POST /start
X-API-Key: <your-api-key>
```
**Response:** `{"status": "started"}`

#### Stop
```
POST /stop
X-API-Key: <your-api-key>
```
**Response:** `{"status": "stopped"}`

#### Status
```
GET /status
```
**Response:**
```json
{"localisation": "running", "ftp": "stopped"}
```

---

### Option 2 — MQTT control topic (recommended)

Use the same HiveMQ connection you already have for robot positions. Publish to `city/control`:

```javascript
// Same client as robot position subscription
client.publish('city/control', JSON.stringify({ action: 'start' }))
client.publish('city/control', JSON.stringify({ action: 'stop' }))
```

No extra credentials needed — HiveMQ username/password is the authentication.

Both options start/stop the same `main.py` process.

---

## Robot positions (MQTT)

When localisation is running, robot positions are published to:

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
- If a robot is physically moved more than 0.5m between frames, its position is reset and re-confirmed

Subscribe via HiveMQ cloud:

```javascript
const client = mqtt.connect('mqtts://e26688c7fd4c4f238a2e04f8d12199af.s1.eu.hivemq.cloud:8883', {
  username: 'Robot',
  password: 'your_mqtt_password_here'
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

1. Page loads → call `GET /status` to check current state
2. Show FTP image while localisation is stopped
3. User clicks **Start** → publish `{"action":"start"}` to `city/control` → listen to MQTT for live robot positions
4. User clicks **Stop** → publish `{"action":"stop"}` to `city/control` → FTP image resumes updating within 1 minute
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
