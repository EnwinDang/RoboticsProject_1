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

# Calibration Markers

Six fixed ArUco markers are placed on the map.

```
Marker IDs: 0–5
```

These markers define known reference points used to compute the homography matrix.

---

# Marker Layout

Example layout of calibration markers:

```
+-----------------------------+
| 0                     1     |
|                             |
|                             |
| 2                     3     |
|                             |
|                             |
| 4                     5     |
+-----------------------------+
```

These markers must remain **fixed and visible** to the camera.

---

# Homography Transformation

The homography transformation maps:

```
camera pixels → world coordinates
```

This produces a **top-down view of the environment**, removing camera perspective distortion.

---

# Calibration Process

1. Capture image from camera.
2. Detect calibration ArUco markers.
3. Extract marker corner coordinates.
4. Define known world coordinates.
5. Compute homography matrix using OpenCV.

Example function:

```
cv2.findHomography()
```

6. Apply transformation:

```
cv2.warpPerspective()
```

---

# Output

The resulting image is a **rectified top-down map** where:

- distances correspond to real-world meters
- robots can be accurately localised
- coordinates are consistent across the map

---

# Importance

Homography calibration ensures:

- accurate robot localisation
- consistent coordinate system
- reliable multi-robot tracking

