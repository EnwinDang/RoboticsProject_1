# Project Roadmap

This document outlines the planned improvements and future extensions of the robot localisation system.

---

# Current Implementation

Completed features:

- Camera streaming using OpenCV
- ROS2 image publishing
- Homography-based map correction
- ArUco robot detection
- Robot pose estimation (x, y, theta)
- ROS2 topic publishing

---

# Next Features

## MQTT Robot Communication

Robot positions will be broadcast through MQTT.

Example topics:

```
city/robots/tag10
city/robots/tag11
```

Example message:

```
{
  "x": 2.14,
  "y": 1.39,
  "theta": 1.57
}
```

This allows robots to **share positions in real time**.

---

# Multi-Camera Support

To cover the entire robot city:

- two cameras will be used
- each camera observes half of the environment

```
Camera 1 → left side
Camera 2 → right side
```

---

# Map Merging

A new ROS2 node will merge both homography outputs.

```
map_merge_node
```

This produces a **single global map**.

---

# Performance Optimisation

Target performance:

```
Camera FPS      ≥ 30
Processing FPS  ≥ 15
Latency         < 100 ms
```

Optimisations may include:

- GPU acceleration on Jetson
- multi-threaded detection
- image downscaling

---

# Multi-Robot Features

Future capabilities:

- robot collision avoidance
- cooperative navigation
- swarm robotics experiments

---

# Final Goal

The final system will provide **real-time global localisation** for multiple robots in a shared environment.

Robots will be able to:

- know each other's positions
- coordinate movements
- avoid collisions

