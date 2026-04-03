# Project Roadmap

This document outlines the planned improvements and future extensions of the robot localisation system.

---

# Completed

- Camera streaming using OpenCV
- ROS2 pose publishing (`/robots/pose`)
- Homography-based pixel → world coordinate mapping
- ArUco robot detection and pose estimation (x, y, theta)
- Event-driven MQTT publishing (`city/robots/tag{id}`)
- Dual camera support with seamless top-down world view
- FTP snapshot upload (periodic world-view image)
- Focus and sharpness tuning via v4l2-ctl

---

# Planned

## Performance Optimisation

Target performance:

```
Camera FPS      ≥ 30
Processing FPS  ≥ 15
Latency         < 100 ms
```

Optimisations may include:

- GPU acceleration on Jetson
- multi-threaded detection
- image downscaling for detection pass

---

## Multi-Robot Features

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
