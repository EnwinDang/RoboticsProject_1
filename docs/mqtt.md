# MQTT Interface

The localisation system publishes robot positions to a HiveMQ cloud broker in real time.

---

## Broker

| Setting  | Value |
|----------|-------|
| Host     | `e26688c7fd4c4f238a2e04f8d12199af.s1.eu.hivemq.cloud` |
| Port     | `8883` (TLS required) |
| Username | `Robot` |
| Password | contact the team |

---

## Topics

| Topic | Direction | Description |
|-------|-----------|-------------|
| `city/robots/tag{id}` | Jetson → frontend | Robot position updates |
| `city/control` | Frontend → Jetson | Start/stop localisation |

Subscribe to all robots:
```
city/robots/#
```

---

## Robot Position Messages

Published as JSON when a robot appears, moves significantly (>5cm or >0.15 rad), or disappears:

```json
{"x": 2.14, "y": 1.39, "theta": 1.57}
```

| Field   | Unit    | Description                    |
|---------|---------|--------------------------------|
| `x`     | meters  | Position along width (0–6m)    |
| `y`     | meters  | Position along height (0–3m)   |
| `theta` | radians | Orientation (0 = facing right) |

---

## Control Messages

Publish to `city/control` to start or stop localisation:

```json
{"action": "start"}
{"action": "stop"}
```

---

## Example Subscriber (JavaScript)

```javascript
const client = mqtt.connect('mqtts://e26688c7fd4c4f238a2e04f8d12199af.s1.eu.hivemq.cloud:8883', {
  username: 'Robot',
  password: '<password>'
})
client.subscribe('city/robots/#')
client.on('message', (topic, message) => {
  const id = topic.split('tag')[1]
  const pos = JSON.parse(message)
  console.log(`Robot ${id}: x=${pos.x}, y=${pos.y}, theta=${pos.theta}`)
})
```

---

## Map Coordinate System

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
