from pathlib import Path
from typing import TYPE_CHECKING, Optional

import cv2
import numpy as np
from PIL import Image

if TYPE_CHECKING:
    from controlnet_aux import HEDdetector

_hed: Optional["HEDdetector"] = None

# Fixed cell dimensions (half-width monospace character proportions).
# CELL_H controls grid density: more rows → higher ASCII complexity.
# Expose only input_height to callers; cell size is an internal detail.
CELL_H = 16
CELL_W = 8  # half-width: exactly CELL_H / 2


def _get_hed() -> "HEDdetector":
    global _hed
    if _hed is None:
        from controlnet_aux import HEDdetector

        _hed = HEDdetector.from_pretrained("lllyasviel/Annotators")
    return _hed


def _hed_edges(gray: np.ndarray) -> np.ndarray:
    """Return a thinned and connected edge map via HED.

    Applies morphological closing to bridge gaps and skeletonization to extract
    the 1-pixel wide 'spine' of the edges, resulting in cleaner ASCII art.
    """
    from skimage.morphology import skeletonize

    h, w = gray.shape
    rgb = cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB)
    pil_in = Image.fromarray(rgb)
    long_side = max(h, w)

    # HED produces a soft probability map
    pil_out = _get_hed()(
        pil_in, detect_resolution=long_side, image_resolution=long_side
    )
    if isinstance(pil_out, Image.Image):
        edge = np.array(pil_out.convert("L"))
    else:
        edge = np.array(pil_out)
        if len(edge.shape) == 3:
            edge = cv2.cvtColor(edge, cv2.COLOR_RGB2GRAY)

    if edge.shape != (h, w):
        edge = cv2.resize(edge, (w, h), interpolation=cv2.INTER_LINEAR)

    mask = (edge > 20).astype(np.uint8) * 255
    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    skel = skeletonize(mask > 0)
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


def _grabcut_fg_mask(
    img_bgr: np.ndarray, margin: float = 0.05, iters: int = 5
) -> np.ndarray:
    """Return boolean foreground mask via GrabCut with auto-rect initialization."""
    h, w = img_bgr.shape[:2]
    my, mx = max(1, int(h * margin)), max(1, int(w * margin))
    rect = (mx, my, w - 2 * mx, h - 2 * my)
    mask = np.zeros((h, w), dtype=np.uint8)
    bgd = np.zeros((1, 65), dtype=np.float64)
    fgd = np.zeros((1, 65), dtype=np.float64)
    cv2.grabCut(img_bgr, mask, rect, bgd, fgd, iters, cv2.GC_INIT_WITH_RECT)
    return (mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD)


def generate_ascii_art(
    img_bgr: np.ndarray,
    input_height: Optional[int] = None,
    grabcut: bool = False,
    edge_threshold: int = 20,
    out_dir: Optional[Path] = None,
    stem: Optional[str] = None,
) -> list[str]:
    """Convert image to ASCII art and return rows as a list of strings.

    Complexity is controlled solely by input_height: a taller input produces
    more rows (and proportionally more columns), giving finer detail.

    Pipeline:
    1. Downscale to input_height (preserve aspect ratio) if provided
    2. GrabCut foreground extraction (optional) — background set to white
    3. HED edge detection (connect gaps + skeletonize thinning) + Sobel gradients
    4. Per cell: classify edge char, space for non-edge
    5. Write <stem>_ascii.txt to out_dir if both are given
    """
    if input_height is not None:
        h, w = img_bgr.shape[:2]
        if h > input_height:
            scale = input_height / h
            img_bgr = cv2.resize(
                img_bgr, (int(w * scale), input_height), interpolation=cv2.INTER_AREA
            )

    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

    if grabcut:
        fg_mask = _grabcut_fg_mask(img_bgr)
        gray[~fg_mask] = 255

    if out_dir is not None:
        cv2.imwrite(str(out_dir / f"{stem}_gray.png"), gray)

    h, w = gray.shape
    grid_rows = max(1, h // CELL_H)
    grid_cols = max(1, w // CELL_W)

    resized = cv2.resize(gray, (grid_cols * CELL_W, grid_rows * CELL_H))

    edges = _hed_edges(resized)

    if out_dir is not None:
        cv2.imwrite(str(out_dir / f"{stem}_edges.png"), edges)

    gx = cv2.Sobel(resized, cv2.CV_64F, 1, 0, ksize=3)
    gy = cv2.Sobel(resized, cv2.CV_64F, 0, 1, ksize=3)

    ascii_rows: list[str] = []
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
        ascii_rows.append("".join(row_chars))

    if out_dir is not None and stem is not None:
        txt_path = out_dir / f"{stem}_ascii.txt"
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write("\n".join(ascii_rows))

    return ascii_rows


def ascii_art_font_available() -> bool:
    from pathlib import Path as _Path
    sarasa = str(_Path(__file__).parent.parent / "SarasaMonoSC-Regular.ttf")
    return _Path(sarasa).exists()
