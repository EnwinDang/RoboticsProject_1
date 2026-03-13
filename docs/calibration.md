# Map Calibration

To convert camera pixels into **real-world coordinates**, the system performs **homography calibration** using fixed ArUco markers.

---

# Map Dimensions

The robot environment represents a rectangular map.

```
Width  = 6 meters
Height = 3 meters
```

The processed map image is scaled to:

```
600 × 300 pixels
```

Which corresponds to:

```
100 pixels = 1 meter
```

---

# Cameras

Two USB cameras are mounted overhead, each covering half of the map.

| Camera | Device      | Coverage         |
|--------|-------------|------------------|
| Cam 1  | /dev/video2 | Left side (x: 0–3m) |
| Cam 2  | /dev/video0 | Right side (x: 3–6m) |

Both cameras are configured in `config.py`:

```python
CAMERA_INDEX_1 = 2  # left side
CAMERA_INDEX_2 = 0  # right side
```

---

# Calibration Markers

Six fixed ArUco markers (IDs 0–5, DICT_4X4_50) are placed at known positions on the map.

These markers must remain **fixed and visible** to the camera at all times.

---

# Marker Layout

```
(0,0)          (3,0)          (6,0)
  [0]────────────[2]────────────[4]
   │                             │
   │                             │
   │                             │
  [1]────────────[3]────────────[5]
(0,3)          (3,3)          (6,3)
```

World coordinates per marker:

| Marker ID | X (m) | Y (m) | Position      |
|-----------|-------|-------|---------------|
| 0         | 0.0   | 0.0   | Top-left      |
| 1         | 0.0   | 3.0   | Bottom-left   |
| 2         | 3.0   | 0.0   | Top-middle    |
| 3         | 3.0   | 3.0   | Bottom-middle |
| 4         | 6.0   | 0.0   | Top-right     |
| 5         | 6.0   | 3.0   | Bottom-right  |

---

# Robot Markers

Robot ArUco markers use IDs starting from 10 (DICT_4X4_50).

| Marker ID | Role  |
|-----------|-------|
| 0–5       | Calibration (fixed) |
| 10+       | Robots (moving) |

---

# Homography Transformation

The homography transformation maps:

```
camera pixels → world coordinates (meters)
```

Requires a minimum of **4 calibration markers** visible at once.

Computed using:

```python
cv2.findHomography(pixel_points, world_points)
```

Applied using:

```python
cv2.perspectiveTransform(point, H)
```

---

# Calibration Process

1. Camera captures a frame.
2. ArUco markers are detected in the frame.
3. Pixel coordinates of calibration markers (IDs 0–5) are extracted.
4. Known world coordinates are looked up from the table above.
5. Homography matrix H is computed.
6. H is used to convert any pixel position to world coordinates.

---

# Output

For each robot marker detected:

```
ID 10 → World: (2.14, 1.39), theta: 1.57
```

Published over MQTT to:

```
city/robots/tag10
```
