# Pre-Demo Test Checklist

Run through this list on the Jetson before every demo. Each section maps to a graded deliverable.

---

## 1. Setup

```bash
cd ~/RoboticsProject_1
source .venv/bin/activate
source /opt/ros/humble/setup.bash
```

Verify cameras are detected:
```bash
ls /dev/video0 /dev/video4
```

Verify MQTT broker is running:
```bash
systemctl status mosquitto
```

---

## 2. Camera stream + ArUco detection (20 pts)

```bash
cd global_localisation
python tools/camera_stream.py
```

Open `http://jetson-dang.local:8080` in browser.

- [ ] Both camera halves are visible (left = video0, right = video4)
- [ ] Calibration markers (IDs 0–5) are highlighted in **red**
- [ ] Robot markers (IDs 10+) are highlighted in **green**
- [ ] The world view is not black (homography computed successfully)
- [ ] At least 4 calibration markers visible per camera half

> If the view stays black: not enough calibration markers visible. Check marker placement and lighting.

---

## 3. World coordinates / homography (20 pts)

Still in the camera stream — check the terminal or run `main.py`:

- [ ] Detected robot positions are printed as `World: (x.xx, y.xx)` in meters
- [ ] Coordinates are within the expected range: x = 0–6m, y = 0–3m
- [ ] Positions match the physical robot location on the map

---

## 4. Tracking & events (15 pts)

Run `main.py`:

```bash
cd global_localisation
python main.py
```

- [ ] `[ADD] ID xx` printed when a robot marker enters the frame
- [ ] `[UPDATE] ID xx` printed only when the robot moves > 5cm or > 0.15 rad
- [ ] `[REMOVE] ID xx` printed when a robot marker leaves the frame
- [ ] No spam updates when robot is stationary

---

## 5. ROS 2 publishing (15 pts)

In a second terminal:

```bash
source /opt/ros/humble/setup.bash
ros2 topic echo /robots/pose
```

- [ ] Pose messages appear when robots are detected
- [ ] `x`, `y`, `theta` values match what main.py prints
- [ ] No messages published when no robots are visible

---

## 6. MQTT publishing (10 pts)

In a second terminal:

```bash
mosquitto_sub -h localhost -t "city/robots/#" -v
```

- [ ] Messages published to `city/robots/tag10`, `city/robots/tag11`, etc.
- [ ] Payload is valid JSON: `{"x": 2.14, "y": 1.39, "theta": 1.57}`
- [ ] Subscribe from a laptop on the same network using `jetson-dang.local` instead of `localhost`

---

## 7. Orientation / theta (bonus, +10 pts)

- [ ] `theta` value changes as the robot rotates
- [ ] `theta ≈ 0` when marker faces right, `theta ≈ 1.57` when facing up

---

## 8. FTP snapshot

```bash
python tools/camera_snapshot_ftp.py
```

- [ ] Uploads successfully every 30 seconds
- [ ] Image visible at the configured FTP URL

---

## 9. Detection quality tuning

This is the hardest part to get right. Work through these in order.

### Step 1 — Check zoom

The zoom is set per camera in `config.py`:
```python
CAMERA_ZOOM_1 = 130   # /dev/video4
CAMERA_ZOOM_2 = 113   # /dev/video0
```
Since the stream uses homography (not raw camera view), zoom changes are only visible in detection quality, not in the stream image. To test:
- Open `camera_stream.py`, check if more/fewer markers are detected when you adjust zoom values
- Higher zoom = markers appear larger in the raw frame = easier to detect
- Lower zoom = more of the field visible but markers smaller

### Step 2 — Check focus

Focus is applied via v4l2-ctl (value `10` = close focus). To verify it's sharp:

```bash
# Capture a raw frame and inspect it
v4l2-ctl -d /dev/video4 --stream-mmap --stream-count=1 --stream-to=/tmp/cam4.jpg
```

Or check the FTP snapshot — if the raw image looks blurry, adjust `CAMERA_FOCUS` in `config.py`.

### Step 3 — Check lighting and reflections

- [ ] No direct light reflections on the markers (glare = failed bit decoding)
- [ ] Even lighting across the whole field — dark corners cause missed detections
- [ ] Markers are flat and not crumpled or bent

### Step 4 — Check marker size

The minimum detectable marker size is controlled by `minMarkerPerimeterRate = 0.01` in `vision/detector.py` and `tools/utils.py`.

Rule of thumb: a marker should appear as **at least 20×20 pixels** in the raw 2560×1440 frame to decode reliably. If robot markers are being missed:
- [ ] Print markers larger (A5 instead of A6)
- [ ] Lower the cameras closer to the field
- [ ] Or reduce `minMarkerPerimeterRate` to `0.005` (detects smaller but more false positives)

### Step 5 — Verify all 4 robot markers are detected

Run `main.py` with all 4 robots on the field and check:
- [ ] All 4 IDs appear in `[ADD]` events
- [ ] Any missed robot: check if it's in the seam area (x ≈ 3m) — it may fall in the blind spot between cameras

### Step 6 — Check seam area

The two camera halves meet at x = 3m. Robots near the seam may not be detected if they fall outside both cameras' homography zones. To test:
- [ ] Place a robot at x ≈ 3m, y ≈ 1.5m
- [ ] Confirm it's detected by at least one camera

---

## Known issues to watch for

| Issue | Cause | Fix |
|-------|-------|-----|
| World view stays black | < 4 calibration markers visible | Reposition markers or improve lighting |
| Robot markers not detected | Marker too small, bad angle, or reflection | Use larger prints, reduce glare |
| Only 1 camera side showing | Homography failed for that camera | Check that camera has 4+ calibration markers |
| Stream not loading in browser | Chrome blocks MJPEG stream | Use Safari or Firefox |
| Camera not found | Wrong device index or USB not connected | Check `ls /dev/video*` |
| Coordinates outside 0–6m / 0–3m | Homography computed with wrong marker positions | Re-check physical marker placement matches `docs/calibration.md` |
| Robot detected but wrong position | Marker ID collision or wrong homography side | Confirm each robot has a unique ID ≥ 10 |
