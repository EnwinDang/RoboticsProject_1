# Next Session TODO

---

## 1. Open Mosquitto to the Network (Jetson)

Mosquitto is currently only accessible locally. To allow other devices to subscribe:

```bash
sudo nano /etc/mosquitto/mosquitto.conf
```

Add at the end:
```
listener 1883 0.0.0.0
allow_anonymous true
```

Restart:
```bash
sudo systemctl restart mosquitto
sudo ss -tlnp | grep 1883
```

Should show `0.0.0.0:1883`.

---

## 2. Test with the Other Team

Once mosquitto is open to the network, verify the other team can receive data:

1. Run the localisation system on the Jetson:
   ```bash
   cd ~/RoboticsProject_1
   python3 global_localisation/main.py
   ```

2. On the other team's device (same network), run:
   ```bash
   pip install paho-mqtt
   mosquitto_sub -h jetson-dang.local -t "city/robots/#" -v
   ```

   Or use the Python example in `docs/mqtt.md`.

---

## 3. Test Multi-Camera

The second camera (`/dev/video0`) was added but not fully tested with both cameras running simultaneously. Verify:

- Both cameras detect their respective calibration markers
- A robot moving from the left half to the right half is tracked continuously
- No duplicate or conflicting poses when a robot is in the overlap zone (markers 2 & 3)

---

## 4. Calibrate on Real Terrain

The system has only been tested on a flat surface. Before deploying on the actual robot city:

- Place all 6 calibration markers on the real terrain at their correct positions
- Run `main.py` and verify the calibration markers report their expected world coordinates (e.g. ID 0 → `(0.00, 0.00)`)
- Move a robot marker by hand across the full map and check the coordinates are consistent
- Pay attention to the overlap zone (x: 2.5–3.5m) where both cameras see the same area

If coordinates look off, the camera height or angle may need adjusting.

---

## 5. Physical Setup Verification

Confirm the calibration marker positions match the code exactly:

| Marker ID | Expected Position |
|-----------|------------------|
| 0         | Top-left (0, 0)      |
| 1         | Bottom-left (0, 3)   |
| 2         | Top-middle (3, 0)    |
| 3         | Bottom-middle (3, 3) |
| 4         | Top-right (6, 0)     |
| 5         | Bottom-right (6, 3)  |

If any marker is misplaced, update `global_localisation/mapping/homography.py` and `homography_node.py`.
