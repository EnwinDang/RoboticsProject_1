"""
Generates a PDF with 6 robot ArUco markers (IDs 10–15) on a single A4 page.
2 columns x 3 rows — as large as possible.
Run: python tools/generate_robot_pdf.py
Output: robot_markers.pdf
"""
import os
import tempfile

import cv2
import cv2.aruco as aruco
import numpy as np
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas as pdf_canvas

MARKER_IDS = list(range(10, 34))  # 24 markers across 4 pages
OUTPUT_PDF = "robot_markers.pdf"
MARKER_SIZE_PX = 1000

page_w, page_h = A4
margin = 1.0 * cm
cols, rows = 2, 3
cell_w = (page_w - 2 * margin) / cols
cell_h = (page_h - 2 * margin) / rows
marker_size = min(cell_w, cell_h) - 0.5 * cm

aruco_dict = aruco.getPredefinedDictionary(aruco.DICT_4X4_50)
c = pdf_canvas.Canvas(OUTPUT_PDF, pagesize=A4)
tmp_files = []

for i, marker_id in enumerate(MARKER_IDS):
    pos_on_page = i % (cols * rows)
    col = pos_on_page % cols
    row = pos_on_page // cols

    if pos_on_page == 0 and i != 0:
        c.showPage()

    marker_img = aruco.generateImageMarker(aruco_dict, marker_id, MARKER_SIZE_PX)
    border = 40
    canvas_size = MARKER_SIZE_PX + 2 * border
    img = np.ones((canvas_size, canvas_size), dtype="uint8") * 255
    img[border:border + MARKER_SIZE_PX, border:border + MARKER_SIZE_PX] = marker_img

    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    cv2.imwrite(tmp.name, img)
    tmp_files.append(tmp.name)

    x = margin + col * cell_w + (cell_w - marker_size) / 2
    y = page_h - margin - (row + 1) * cell_h + (cell_h - marker_size) / 2

    c.drawImage(tmp.name, x, y, width=marker_size, height=marker_size)

    label = f"ID {marker_id}"
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(x + marker_size / 2, y - 0.5 * cm, label)

c.save()

for f in tmp_files:
    os.unlink(f)

print(f"PDF saved: {OUTPUT_PDF}")
