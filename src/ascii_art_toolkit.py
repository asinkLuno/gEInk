from pathlib import Path
from typing import TYPE_CHECKING, Optional

import cv2
import numpy as np

if TYPE_CHECKING:
    from segment_anything import SamPredictor

_sam_model = None
_sam_pred: Optional["SamPredictor"] = None

# Fixed cell dimensions (half-width monospace character proportions).
# CELL_H controls grid density: more rows → higher ASCII complexity.
# Expose only input_height to callers; cell size is an internal detail.
CELL_H = 16
CELL_W = 8  # half-width: exactly CELL_H / 2

# Braille cell: 2 columns × 4 rows of dots per character.
# Effective resolution is 4× higher than standard ASCII cells.
BRAILLE_CELL_H = 4
BRAILLE_CELL_W = 2
_BRAILLE_BASE = 0x2800
# Braille Unicode dot-to-bit mapping: pixel at (row, col) → bit position
#   col 0  col 1
#   bit 0  bit 3   row 0
#   bit 1  bit 4   row 1
#   bit 2  bit 5   row 2
#   bit 6  bit 7   row 3
_BRAILLE_BIT = ((0, 3), (1, 4), (2, 5), (6, 7))

_SAM_MODEL_TYPE = "vit_b"
_SAM_URL = "https://dl.fbaipublicfiles.com/segment_anything/sam_vit_b_01ec64.pth"
_SAM_FILENAME = "sam_vit_b_01ec64.pth"


def _get_sam_model():
    global _sam_model
    if _sam_model is None:
        import urllib.request

        from segment_anything import sam_model_registry

        cache_dir = Path.home() / ".cache" / "segment_anything"
        cache_dir.mkdir(parents=True, exist_ok=True)
        checkpoint = cache_dir / _SAM_FILENAME

        if not checkpoint.exists():
            print(f"Downloading SAM checkpoint to {checkpoint} …")
            urllib.request.urlretrieve(_SAM_URL, checkpoint)

        _sam_model = sam_model_registry[_SAM_MODEL_TYPE](checkpoint=str(checkpoint))
    return _sam_model


def _get_sam_pred() -> "SamPredictor":
    global _sam_pred
    if _sam_pred is None:
        from segment_anything import SamPredictor

        _sam_pred = SamPredictor(_get_sam_model())
    return _sam_pred


def _is_line_art(img_rgb: np.ndarray) -> bool:
    """Return True if the image looks like line art (bright background, low saturation)."""
    hsv = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2HSV)
    white_ratio = float((hsv[:, :, 2] > 200).mean())
    sat_mean = float(hsv[:, :, 1].mean())
    return white_ratio > 0.5 and sat_mean < 30


def _line_art_edges(gray: np.ndarray, target_h: int, target_w: int) -> np.ndarray:
    """Return a skeletonized edge map for line art via Otsu thresholding + Canny."""
    from skimage.morphology import skeletonize

    # Otsu binarizes dark strokes on bright background; invert so strokes = 255
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    if binary.shape != (target_h, target_w):
        binary = cv2.resize(
            binary, (target_w, target_h), interpolation=cv2.INTER_NEAREST
        )

    skel = skeletonize(binary > 0)
    return skel.astype(np.uint8) * 255


def _canny_edges(gray: np.ndarray, target_h: int, target_w: int) -> np.ndarray:
    """Return a skeletonized edge map via bilateral-filtered Canny.

    Bilateral filter smooths texture while preserving structural edges, giving
    Canny cleaner input than raw grayscale. Thresholds are auto-tuned via Otsu.
    """
    from skimage.morphology import skeletonize

    smooth = cv2.bilateralFilter(gray, d=9, sigmaColor=75, sigmaSpace=75)
    otsu, _ = cv2.threshold(smooth, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    edges = cv2.Canny(smooth, max(float(otsu) * 0.33, 10.0), float(otsu))

    if edges.shape != (target_h, target_w):
        edges = cv2.resize(edges, (target_w, target_h), interpolation=cv2.INTER_NEAREST)

    skel = skeletonize(edges > 0)
    return skel.astype(np.uint8) * 255


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
                pair = np.array([top_mean, bot_mean])
                a2 = np.radians(pair * 2.0)
                mid_angle = (
                    float(np.degrees(np.arctan2(np.sin(a2).mean(), np.cos(a2).mean())))
                    / 2.0
                    % 180.0
                )
                if 45.0 < mid_angle < 135.0:
                    return ")" if diff > 0 else "("

    if consistency < 0.4:
        return "+"

    is_horiz = mean_angle < 22.5 or mean_angle > 157.5
    if is_horiz:
        ys, xs = np.where(mask)
        y_ratio = float(ys.mean()) / cell_h
        if y_ratio < 0.35:
            return "'"
        if y_ratio > 0.65:
            return "."
        row_coverage = float(np.unique(ys).size) / cell_h
        if row_coverage > 0.4:
            return "="

    return _angle_to_edge_char(mean_angle)


def _sam_fg_mask(img_rgb: np.ndarray) -> np.ndarray:
    """Return boolean foreground mask using SAM predictor with a center-point prompt."""
    h, w = img_rgb.shape[:2]
    predictor = _get_sam_pred()
    predictor.set_image(img_rgb)

    # Prompt: Center point of the image
    input_point = np.array([[w // 2, h // 2]])
    input_label = np.array([1])  # 1 = foreground

    masks, scores, logits = predictor.predict(
        point_coords=input_point,
        point_labels=input_label,
        multimask_output=True,
    )
    # Pick the mask with highest score
    return masks[np.argmax(scores)]


def _edges_to_braille(edges: np.ndarray) -> list[str]:
    """Convert a binary edge map to Braille Unicode rows.

    Each 2×4 pixel block becomes one Braille character. Dots are lit wherever
    an edge pixel is non-zero, giving pixel-level fidelity without angle math.
    The edge map must already be sized to a multiple of (BRAILLE_CELL_H, BRAILLE_CELL_W).
    """
    bh, bw = BRAILLE_CELL_H, BRAILLE_CELL_W
    h, w = edges.shape
    grid_rows, grid_cols = h // bh, w // bw
    lit = edges > 0
    rows: list[str] = []
    for r in range(grid_rows):
        chars: list[str] = []
        for c in range(grid_cols):
            cell = lit[r * bh : (r + 1) * bh, c * bw : (c + 1) * bw]
            bits = 0
            for row in range(bh):
                for col in range(bw):
                    if cell[row, col]:
                        bits |= 1 << _BRAILLE_BIT[row][col]
            chars.append(chr(_BRAILLE_BASE + bits))
        rows.append("".join(chars))
    return rows


def generate_ascii_art(
    img_bgr: np.ndarray,
    input_height: Optional[int] = None,
    sam_mask: bool = False,
    edge_threshold: int = 20,
    braille: bool = False,
    out_dir: Optional[Path] = None,
    stem: Optional[str] = None,
) -> list[str]:
    """Convert image to ASCII art and return rows as a list of strings.

    Complexity is controlled solely by input_height: a taller input produces
    more rows (and proportionally more columns), giving finer detail.

    Pipeline:
    1. Downscale to input_height (preserve aspect ratio) if provided
    2. SAM-based foreground extraction (optional) — background set to white
    3. Canny edge detection (bilateral pre-filter + Otsu thresholds)
    4a. braille=False: per 8×16 cell, classify angle char via Sobel on edge map
    4b. braille=True:  per 2×4 cell, map lit edge pixels → Braille dots directly
    5. Write <stem>_ascii.txt to out_dir if both are given
    """
    if input_height is not None:
        h, w = img_bgr.shape[:2]
        if h > input_height:
            scale = input_height / h
            img_bgr = cv2.resize(
                img_bgr, (int(w * scale), input_height), interpolation=cv2.INTER_AREA
            )

    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

    if sam_mask:
        fg_mask = _sam_fg_mask(img_rgb)
        gray[~fg_mask] = 255

    if out_dir is not None:
        cv2.imwrite(str(out_dir / f"{stem}_gray.png"), gray)

    h, w = gray.shape

    if braille:
        cell_h, cell_w = BRAILLE_CELL_H, BRAILLE_CELL_W
    else:
        cell_h, cell_w = CELL_H, CELL_W

    grid_rows = max(1, h // cell_h)
    grid_cols = max(1, w // cell_w)

    if _is_line_art(img_rgb):
        edges = _line_art_edges(gray, grid_rows * cell_h, grid_cols * cell_w)
    else:
        edges = _canny_edges(gray, grid_rows * cell_h, grid_cols * cell_w)

    if out_dir is not None:
        cv2.imwrite(str(out_dir / f"{stem}_edges.png"), edges)

    if braille:
        rows = _edges_to_braille(edges)
    else:
        # Blur the edge map before Sobel so gradient direction comes from edge geometry,
        # not image texture — avoids mis-classified angles in textured regions.
        edge_blur = cv2.GaussianBlur(edges.astype(np.float32), (0, 0), sigmaX=2.0)
        gx = cv2.Sobel(edge_blur, cv2.CV_64F, 1, 0, ksize=3)
        gy = cv2.Sobel(edge_blur, cv2.CV_64F, 0, 1, ksize=3)

        rows = []
        for row in range(grid_rows):
            y0, y1 = row * CELL_H, (row + 1) * CELL_H
            row_chars: list[str] = []
            for col in range(grid_cols):
                x0, x1 = col * CELL_W, (col + 1) * CELL_W
                if edges[y0:y1, x0:x1].mean() > edge_threshold:
                    char = _classify_edge_cell(
                        gx[y0:y1, x0:x1], gy[y0:y1, x0:x1], CELL_H
                    )
                else:
                    char = " "
                row_chars.append(char)
            rows.append("".join(row_chars))

    if out_dir is not None and stem is not None:
        txt_path = out_dir / f"{stem}_ascii.txt"
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write("\n".join(rows))

    return rows


def ascii_art_font_available() -> bool:
    from pathlib import Path as _Path

    sarasa = str(_Path(__file__).parent.parent / "SarasaMonoSC-Regular.ttf")
    return _Path(sarasa).exists()
