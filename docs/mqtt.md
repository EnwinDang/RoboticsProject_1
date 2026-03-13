# MQTT Interface

The localisation system broadcasts robot positions over MQTT in real time.

No SSH access is needed. Any device on the **same network** as the Jetson can subscribe.

---

# Broker

| Setting | Value |
|---------|-------|
| Host    | `jetson-dang.local` |
| Port    | `1883` |

---

# Topics

One topic per robot, based on its ArUco marker ID:

```
city/robots/tag10
city/robots/tag11
city/robots/tag12
...
```

To subscribe to all robots at once use the wildcard:

```
city/robots/#
```

---

# Message Format

Messages are published as JSON:

```json
{"x": 2.14, "y": 1.39, "theta": 1.57}
```

| Field   | Type  | Unit    | Description                        |
|---------|-------|---------|------------------------------------|
| `x`     | float | meters  | Position along the width of the map  |
| `y`     | float | meters  | Position along the height of the map |
| `theta` | float | radians | Orientation (0 = facing right)     |

---

# Map Coordinate System

```
(0,0)─────────────────────(6,0)
  │                          │
  │         6m × 3m          │
  │                          │
(0,3)─────────────────────(6,3)
```

- Origin `(0, 0)` is the **top-left** corner of the map
- `x` increases to the right
- `y` increases downward

---

# Example Subscriber (Python)

Install the MQTT client library:

```bash
pip install paho-mqtt
```

Subscribe to all robots:

```python
import paho.mqtt.client as mqtt
import json

def on_message(client, userdata, msg):
    data = json.loads(msg.payload)
    robot_id = msg.topic.split("tag")[-1]
    print(f"Robot {robot_id} → x={data['x']}, y={data['y']}, theta={data['theta']}")

client = mqtt.Client()
client.on_message = on_message
client.connect("jetson-dang.local", 1883)
client.subscribe("city/robots/#")
client.loop_forever()
```

---

# Update Rate

Robot positions are published every camera frame — approximately **27 times per second**.
