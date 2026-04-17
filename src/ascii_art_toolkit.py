from pathlib import Path
from typing import TYPE_CHECKING, Optional

import cv2
import numpy as np

if TYPE_CHECKING:
    from segment_anything import SamPredictor

_sam_model = None
_sam_pred: Optional["SamPredictor"] = None

# Fixed cell dimensions (half-width monospace character proportions).
CELL_H = 16
CELL_W = 8  # half-width: exactly CELL_H / 2

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

_H_CHARS = frozenset("-_='.")
_V_CHARS = frozenset("|()")
_D1_CHARS = frozenset("\\")
_D2_CHARS = frozenset("/")
_ALL_EDGE = _H_CHARS | _V_CHARS | _D1_CHARS | _D2_CHARS | frozenset("+=")


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


def _merge_edge_segments(rows: list[str], max_gap: int = 2) -> list[str]:
    """Fill small gaps between co-directional edge chars and remove isolated noise.

    For each direction (H / V / diagonal), scans sequences and fills spaces
    of length <= max_gap that lie between two runs of the same char family.
    Then removes any edge char with no non-space 8-connected neighbor.
    """
    if not rows:
        return rows

    nrows = len(rows)
    ncols = max(len(r) for r in rows)
    grid = [list(r.ljust(ncols)) for r in rows]

    def _fill_seq(seq: list[str], char_set: frozenset[str]) -> None:
        n = len(seq)
        runs: list[tuple[int, int]] = []
        i = 0
        while i < n:
            if seq[i] in char_set:
                s = i
                while i < n and seq[i] in char_set:
                    i += 1
                runs.append((s, i))
            else:
                i += 1
        for k in range(len(runs) - 1):
            gap_s, gap_e = runs[k][1], runs[k + 1][0]
            if 0 < gap_e - gap_s <= max_gap and all(
                seq[j] == " " for j in range(gap_s, gap_e)
            ):
                fill = seq[gap_s - 1]
                for j in range(gap_s, gap_e):
                    seq[j] = fill

    # Horizontal
    for r in range(nrows):
        _fill_seq(grid[r], _H_CHARS)

    # Vertical
    for c in range(ncols):
        col = [grid[r][c] for r in range(nrows)]
        _fill_seq(col, _V_CHARS)
        for r in range(nrows):
            grid[r][c] = col[r]

    # Diagonal \ (c - r = k)
    for k in range(-(nrows - 1), ncols):
        r0 = max(0, -k)
        c0 = r0 + k
        length = min(nrows - r0, ncols - c0)
        coords = [(r0 + i, c0 + i) for i in range(length)]
        if len(coords) >= 2:
            seq = [grid[r][c] for r, c in coords]
            _fill_seq(seq, _D1_CHARS)
            for i, (r, c) in enumerate(coords):
                grid[r][c] = seq[i]

    # Diagonal / (r + c = k)
    for k in range(nrows + ncols - 1):
        r0 = max(0, k - ncols + 1)
        c0 = k - r0
        length = min(nrows - r0, c0 + 1)
        coords = [(r0 + i, c0 - i) for i in range(length)]
        if len(coords) >= 2:
            seq = [grid[r][c] for r, c in coords]
            _fill_seq(seq, _D2_CHARS)
            for i, (r, c) in enumerate(coords):
                grid[r][c] = seq[i]

    # Remove isolated noise: edge chars with no non-space 8-neighbor
    to_clear = [
        (r, c)
        for r in range(nrows)
        for c in range(ncols)
        if grid[r][c] in _ALL_EDGE
        and not any(
            0 <= r + dr < nrows and 0 <= c + dc < ncols and grid[r + dr][c + dc] != " "
            for dr in (-1, 0, 1)
            for dc in (-1, 0, 1)
            if (dr, dc) != (0, 0)
        )
    ]
    for r, c in to_clear:
        grid[r][c] = " "

    return ["".join(row).rstrip() for row in grid]


def _sam_fg_mask(img_rgb: np.ndarray) -> np.ndarray:
    """Return boolean foreground mask using SAM predictor with a center-point prompt."""
    h, w = img_rgb.shape[:2]
    predictor = _get_sam_pred()
    predictor.set_image(img_rgb)

    input_point = np.array([[w // 2, h // 2]])
    input_label = np.array([1])

    masks, scores, logits = predictor.predict(
        point_coords=input_point,
        point_labels=input_label,
        multimask_output=True,
    )
    return masks[np.argmax(scores)]


def generate_ascii_art(
    img_bgr: np.ndarray,
    num_rows: Optional[int] = None,
    sam_mask: bool = False,
    edge_threshold: int = 20,
    out_dir: Optional[Path] = None,
    stem: Optional[str] = None,
) -> list[str]:
    """Convert image to ASCII art and return rows as a list of strings.

    num_rows controls exactly how many lines the output has. The image is
    resized so its pixel height equals num_rows * CELL_H, preserving aspect
    ratio, so columns scale proportionally.

    Pipeline:
    1. Resize to num_rows * CELL_H tall (preserve aspect ratio) if provided
    2. SAM-based foreground extraction (optional) — background set to white
    3. Canny edge detection (bilateral pre-filter + Otsu thresholds)
    4. Per 8×16 cell, classify angle char via Sobel on edge map
    5. Write <stem>_ascii.txt to out_dir if both are given
    """
    if num_rows is not None:
        h, w = img_bgr.shape[:2]
        target_h = num_rows * CELL_H
        scale = target_h / h
        target_w = int(w * scale)
        interp = cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR
        img_bgr = cv2.resize(img_bgr, (target_w, target_h), interpolation=interp)

    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

    if sam_mask:
        fg_mask = _sam_fg_mask(img_rgb)
        gray[~fg_mask] = 255

    if out_dir is not None:
        cv2.imwrite(str(out_dir / f"{stem}_gray.png"), gray)

    h, w = gray.shape
    grid_rows = max(1, h // CELL_H)
    grid_cols = max(1, w // CELL_W)

    if _is_line_art(img_rgb):
        edges = _line_art_edges(gray, grid_rows * CELL_H, grid_cols * CELL_W)
    else:
        edges = _canny_edges(gray, grid_rows * CELL_H, grid_cols * CELL_W)

    if out_dir is not None:
        cv2.imwrite(str(out_dir / f"{stem}_edges.png"), edges)

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
                char = _classify_edge_cell(gx[y0:y1, x0:x1], gy[y0:y1, x0:x1], CELL_H)
            else:
                char = " "
            row_chars.append(char)
        rows.append("".join(row_chars))

    rows = _merge_edge_segments(rows)

    if out_dir is not None and stem is not None:
        txt_path = out_dir / f"{stem}_ascii.txt"
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write("\n".join(rows))

    return rows


def ascii_art_font_available() -> bool:
    from pathlib import Path as _Path

    sarasa = str(_Path(__file__).parent.parent / "SarasaMonoSC-Regular.ttf")
    return _Path(sarasa).exists()
