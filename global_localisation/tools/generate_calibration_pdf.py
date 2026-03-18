"""
Generates a PDF with all 6 calibration ArUco markers (IDs 0-5) on a single A4 page.
2 columns x 3 rows grid.
Run: python tools/generate_calibration_pdf.py
Output: calibration_markers.pdf
"""
import cv2
import cv2.aruco as aruco
import numpy as np
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas as pdf_canvas
import tempfile
import os

MARKER_SIZE_PX = 1000
OUTPUT_PDF = "aruco_markers.pdf"

page_w, page_h = A4
margin = 1.5 * cm
cols, rows = 2, 4
cell_w = (page_w - 2 * margin) / cols
cell_h = (page_h - 2 * margin) / rows
marker_size = min(cell_w, cell_h) - 1 * cm

MARKER_IDS = list(range(10, 18))
LABELS = {i: f"ID {i} (robot)" for i in MARKER_IDS}

aruco_dict = aruco.getPredefinedDictionary(aruco.DICT_4X4_50)

c = pdf_canvas.Canvas(OUTPUT_PDF, pagesize=A4)
tmp_files = []

for i, marker_id in enumerate(MARKER_IDS):
    col = i % cols
    row = i // cols

    # generate marker image
    marker = aruco.generateImageMarker(aruco_dict, marker_id, MARKER_SIZE_PX)
    border = 60
    canvas_size = MARKER_SIZE_PX + 2 * border
    img = np.ones((canvas_size, canvas_size), dtype="uint8") * 255
    img[border:border+MARKER_SIZE_PX, border:border+MARKER_SIZE_PX] = marker

    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    cv2.imwrite(tmp.name, img)
    tmp_files.append(tmp.name)

    # position on page (reportlab origin is bottom-left)
    x = margin + col * cell_w + (cell_w - marker_size) / 2
    y = page_h - margin - (row + 1) * cell_h + (cell_h - marker_size) / 2

    c.drawImage(tmp.name, x, y, width=marker_size, height=marker_size)

c.save()

for f in tmp_files:
    os.unlink(f)

print(f"PDF saved: {OUTPUT_PDF}")
