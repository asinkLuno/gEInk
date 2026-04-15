from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

SARASA_FONT_PATH = "/usr/share/fonts/sarasa-gothic/Sarasa-Regular.ttc"

# Edge angle [0°, 180°) → straight-line chars
# Canonical angles: 0°=horizontal, 45°=\, 90°=vertical, 135°=/
_EDGE_THRESHOLDS = [11.25, 67.5, 112.5, 168.75]
_EDGE_CHARS = ["_", "\\", "|", "/", "-"]


def _angle_to_edge_char(edge_angle: float) -> str:
    for i, t in enumerate(_EDGE_THRESHOLDS):
        if edge_angle < t:
            return _EDGE_CHARS[i]
    return _EDGE_CHARS[-1]


def _circular_mean_angle(angles_deg: np.ndarray) -> tuple[float, float]:
    """Return (mean_angle_deg, consistency) for angles in [0°, 180°).

    Uses double-angle trick to handle the 180° periodicity of edge directions.
    consistency is in [0, 1]: 1 = perfectly aligned, 0 = uniform spread.
    """
    a2 = np.radians(angles_deg * 2.0)
    mc, ms = float(np.cos(a2).mean()), float(np.sin(a2).mean())
    mean = float(np.degrees(np.arctan2(ms, mc))) / 2.0 % 180.0
    consistency = float(np.sqrt(mc**2 + ms**2))
    return mean, consistency


def _classify_edge_cell(cell_gx: np.ndarray, cell_gy: np.ndarray, cell_h: int) -> str:
    """Map a cell's gradient data to one edge character.

    Priority order:
    1. ( ) : curved vertical — each half is locally consistent but angles diverge
    2. +   : intersection — low overall consistency AND not a clean curve
    3. ' . : horizontal edge concentrated at cell top / bottom
    4. =   : thick horizontal — edge spans most columns
    5. _ \\ | / - : dominant-angle fallback
    """
    mag = np.hypot(cell_gx, cell_gy)
    peak = float(mag.max())
    if peak == 0:
        return " "

    mask = mag > peak * 0.3
    if not mask.any():
        return " "

    edge_angles = (np.degrees(np.arctan2(cell_gy, cell_gx)) + 90.0) % 180.0
    mean_angle, consistency = _circular_mean_angle(edge_angles[mask])

    # 1. Curve detection first — must precede intersection check because a perfect
    #    ( or ) cell has two opposing halves that cancel to near-zero consistency.
    mid = cell_h // 2
    top_mask = mask[:mid, :]
    bot_mask = mask[mid:, :]
    if top_mask.any() and bot_mask.any():
        top_mean, top_cons = _circular_mean_angle(edge_angles[:mid, :][top_mask])
        bot_mean, bot_cons = _circular_mean_angle(edge_angles[mid:, :][bot_mask])
        if top_cons > 0.5 and bot_cons > 0.5:
            diff = bot_mean - top_mean
            if diff > 90:
                diff -= 180
            elif diff < -90:
                diff += 180
            if abs(diff) > 25:
                # mid_angle via circular mean of the two half-means
                pair = np.array([top_mean, bot_mean])
                a2 = np.radians(pair * 2.0)
                mid_angle = (
                    float(np.degrees(np.arctan2(np.sin(a2).mean(), np.cos(a2).mean())))
                    / 2.0
                    % 180.0
                )
                if 45.0 < mid_angle < 135.0:
                    # ( : top is /, bottom is \ → diff < 0
                    # ) : top is \, bottom is / → diff > 0
                    return ")" if diff > 0 else "("

    # 2. Intersection
    if consistency < 0.4:
        return "+"

    # 3 & 4. Horizontal: position and thickness
    is_horiz = mean_angle < 22.5 or mean_angle > 157.5
    if is_horiz:
        ys, xs = np.where(mask)
        y_ratio = float(ys.mean()) / cell_h
        if y_ratio < 0.35:
            return "'"
        if y_ratio > 0.65:
            return "."
        # = : thick horizontal — edge spans most rows of the cell
        row_coverage = float(np.unique(ys).size) / cell_h
        if row_coverage > 0.4:
            return "="

    return _angle_to_edge_char(mean_angle)


def render_ascii_art(
    img_bgr: np.ndarray, cell_height: int = 12, input_height: int = 400
) -> np.ndarray:
    """Convert image to ASCII art rendered with Sarasa Gothic font.

    Pipeline:
    1. Downscale to input_height (preserve aspect ratio)
    2. CLAHE + unsharp mask for contrast/edge enhancement
    3. Canny edge detection + Sobel gradients
    4. Per cell: classify edge char, space for non-edge
    5. Render onto white canvas with Sarasa Gothic
    """
    font = ImageFont.truetype(SARASA_FONT_PATH, cell_height)

    probe = Image.new("L", (cell_height * 2, cell_height * 2))
    bbox = ImageDraw.Draw(probe).textbbox((0, 0), "M", font=font)
    cell_w = int(bbox[2] - bbox[0])
    cell_h = int(bbox[3] - bbox[1])

    h, w = img_bgr.shape[:2]
    if h > input_height:
        scale = input_height / h
        img_bgr = cv2.resize(
            img_bgr, (int(w * scale), input_height), interpolation=cv2.INTER_AREA
        )

    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray)
    blurred = cv2.GaussianBlur(gray, (0, 0), sigmaX=2)
    gray = cv2.addWeighted(gray, 1.8, blurred, -0.8, 0)

    h, w = gray.shape
    grid_rows = max(1, h // cell_h)
    grid_cols = max(1, w // cell_w)

    resized = cv2.resize(gray, (int(grid_cols * cell_w), int(grid_rows * cell_h)))
    edges = cv2.Canny(resized, 40, 120)
    gx = cv2.Sobel(resized, cv2.CV_64F, 1, 0, ksize=3)
    gy = cv2.Sobel(resized, cv2.CV_64F, 0, 1, ksize=3)

    canvas = Image.new(
        "RGB", (int(grid_cols * cell_w), int(grid_rows * cell_h)), (255, 255, 255)
    )
    draw = ImageDraw.Draw(canvas)

    for row in range(grid_rows):
        y0, y1 = row * cell_h, (row + 1) * cell_h
        for col in range(grid_cols):
            x0, x1 = col * cell_w, (col + 1) * cell_w

            if edges[y0:y1, x0:x1].mean() > 8:
                char = _classify_edge_cell(gx[y0:y1, x0:x1], gy[y0:y1, x0:x1], cell_h)
            else:
                char = " "

            if char != " ":
                draw.text((x0, y0), char, fill=(0, 0, 0), font=font)

    return cv2.cvtColor(np.array(canvas), cv2.COLOR_RGB2BGR)


def ascii_art_font_available() -> bool:
    return Path(SARASA_FONT_PATH).exists()
