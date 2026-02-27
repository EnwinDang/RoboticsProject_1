# Global Localisation with ArUco Markers

This project implements a simple global localisation pipeline using ArUco markers and homography. A calibrated overhead (or fixed) camera observes a field with known ArUco calibration markers; the system detects markers in the image, estimates a pixel-to-world homography, and reports marker positions in world coordinates.

## Project Structure

- `global_localisation/main.py`  
  Main entry point. Captures frames from the camera, runs ArUco detection, updates the homography, and prints detected marker positions in world coordinates.

- `global_localisation/config.py`  
  Basic configuration:
  - `WORLD_WIDTH`, `WORLD_HEIGHT`: world dimensions (in meters) used to define the calibration grid.
  - `CALIBRATION_IDS`: list of ArUco IDs used as calibration markers.
  - `CAMERA_INDEX`: index of the camera device for OpenCV.

- `global_localisation/vision/detector.py`  
  Defines `ArucoDetector`, which:
  - Uses OpenCV's ArUco utilities to detect markers in a frame.
  - Computes each marker's pixel center and orientation.
  - Returns a list of detection dictionaries with keys like `id`, `x_pixel`, `y_pixel`, `theta_image`, and `corners`.

- `global_localisation/vision/cam1.py`  
  Example script that opens the camera, runs `ArucoDetector`, and uses the homography mapper to convert detected pixel positions to world coordinates, displaying the camera feed in a window.

- `global_localisation/mapping/homography.py`  
  Defines `HomographyMapper`, which:
  - Stores world coordinates for calibration marker IDs based on `WORLD_WIDTH` and `WORLD_HEIGHT`.
  - Builds a pixel-to-world homography from detected calibration markers.
  - Provides `pixel_to_world(x_pixel, y_pixel)` to map image coordinates into world coordinates (returns `None` until a homography has been estimated).

- `global_localisation/tools/aruco_generate.py`  
  Utility for working with / generating ArUco markers (e.g. to print calibration and robot markers). Exact usage depends on how you extend this script.

- `global_localisation/aruco_layout.pdf`  
  Reference layout for the physical placement of ArUco markers in the environment.

## Environment Setup

It is recommended to run this project inside a dedicated Python virtual environment to avoid dependency conflicts with other projects.

From the project root:

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

Once the virtual environment is active, install the dependencies below.

## Requirements

Install dependencies with `pip` (inside your virtual environment, Python 3.10+ recommended):

```bash
pip install opencv-python numpy flask
```

If you need ArUco support via `cv2.aruco` and it is missing from your OpenCV build, you may need to install the contrib package instead:

```bash
pip install opencv-contrib-python numpy flask
```

## Running the System

1. **Set up the camera and markers**
   - Place the ArUco calibration markers in the environment according to `aruco_layout.pdf`.
   - Ensure the camera has a clear, stable view of the entire calibration area.

2. **Adjust configuration**
   - Edit `global_localisation/config.py`:
     - Set `WORLD_WIDTH` and `WORLD_HEIGHT` to match your real-world field size (in meters).
     - Update `CALIBRATION_IDS` if your calibration markers use different IDs.
     - Set `CAMERA_INDEX` to match your camera device (0, 1, ...).

3. **Run the main script**

   From the project root:

   ```bash
   python -m global_localisation.main
   ```

   or directly (depending on your PYTHONPATH / working directory):

   ```bash
   python global_localisation/main.py
   ```

   You should see:
   - A camera window displaying the live feed.
   - Printed lines in the terminal like:
     `ID 3 → World: (x.xx, y.yy)`

4. **Alternative camera script**

   You can also run `cam1.py` directly if you prefer that entry point:

   ```bash
   python global_localisation/vision/cam1.py
   ```

## How It Works (High Level)

1. **Detection**
   - Each frame from the camera is converted to grayscale.
   - `ArucoDetector` finds ArUco markers and computes their pixel centers and orientations.

2. **Homography Estimation**
   - When calibration markers (IDs listed in `CALIBRATION_IDS`) are visible, `HomographyMapper` collects their pixel positions and corresponding world coordinates.
   - It uses `cv2.findHomography` to compute a homography matrix \( H \) mapping image coordinates \((x_\text{pixel}, y_\text{pixel})\) into world coordinates \((x_\text{world}, y_\text{world})\).

3. **World Mapping**
   - For any detected marker, `pixel_to_world` applies the homography (via `cv2.perspectiveTransform`) to convert its center pixel location into world coordinates.
   - Until at least four calibration markers are detected and a valid homography is found, `pixel_to_world` returns `None`.

## Notes and Extensions

- You can extend `ArucoDetector` to estimate full 6D pose if you have camera intrinsics and marker sizes.
- `HomographyMapper` currently assumes a flat 2D field; for 3D environments you would need a different mapping strategy.
- The `tools/` folder is a good place to add utilities for generating new marker sheets, visualising layouts, or debugging detections.

# RoboticsProject_1