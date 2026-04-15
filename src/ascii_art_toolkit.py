from pathlib import Path
from typing import TYPE_CHECKING, Optional

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

if TYPE_CHECKING:
    from controlnet_aux import HEDdetector

_hed: Optional["HEDdetector"] = None


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
        # If it's a numpy array (Mat), convert to grayscale if needed
        edge = np.array(pil_out)
        if len(edge.shape) == 3:
            edge = cv2.cvtColor(edge, cv2.COLOR_RGB2GRAY)

    if edge.shape != (h, w):
        edge = cv2.resize(edge, (w, h), interpolation=cv2.INTER_LINEAR)

    # Connect and thin
    # 1. Binary mask to work with morphological operations and skeletonization
    # We use a low threshold to preserve weak edges
    mask = (edge > 20).astype(np.uint8) * 255

    # 2. Morphological closing to bridge small gaps (e.g. 1-2 pixels)
    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    # 3. Skeletonize to get 1-pixel wide connected lines
    skel = skeletonize(mask > 0)

    # Return thinned edges. We use 255 to ensure they are picked up by the mean threshold check.
    return skel.astype(np.uint8) * 255


SARASA_FONT_PATH = str(Path(__file__).parent.parent / "SarasaMonoSC-Regular.ttf")

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


def _draw_info_panel(
    draw: ImageDraw.ImageDraw,
    x_offset: int,
    y_offset: int,
    height: int,
    info: dict,  # 雖然傳入 info，但我們在這裡忽略它，直接畫五月天面板
    font_path: str,
    base_font_size: int = 14,
) -> None:
    """Draw the Mayday #5525 LIVE TOUR info panel on the right side."""

    # 設定字體大小
    font_large = ImageFont.truetype(font_path, int(base_font_size * 1.5))
    font_normal = ImageFont.truetype(font_path, base_font_size)

    # 面板寬度預設為 240，計算中心點以便文字置中
    panel_center_x = x_offset + 120
    current_y = y_offset + 20

    def draw_centered(
        y: int, text: str, font: ImageFont.FreeTypeFont, fill: tuple
    ) -> int:
        """輔助函數：將文字水平置中繪製，並回傳下一個 Y 座標"""
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        x = panel_center_x - (text_w / 2)
        draw.text((x, y), text, fill=fill, font=font)
        return int(y + text_h + 10)  # 預留行距

    # 1. 繪製上方的 ASCII 皇冠/M字 Logo 與 25
    ascii_logo = ["25", "", " /\\ ", "/  \\", "/|  |\\", "| |  | |", "|_|__|_|"]

    # 頂部 25
    current_y = draw_centered(current_y, ascii_logo[0], font_normal, (200, 200, 200))
    current_y += 10  # 額外空行

    # 繪製圖形
    for line in ascii_logo[2:]:
        # 圖形行距可以緊湊一點
        bbox = draw.textbbox((0, 0), line, font=font_normal)
        text_w = bbox[2] - bbox[0]
        x = panel_center_x - (text_w / 2)
        draw.text((x, current_y), line, fill=(200, 200, 200), font=font_normal)
        current_y += base_font_size + 2

    current_y += 30  # 與下方文字的間距

    # 2. 歡迎光臨 (紅色)
    current_y = draw_centered(current_y, "歡 迎 光 臨", font_large, (255, 50, 50))
    current_y += 10

    # 3. 站點資訊 (青綠色)
    current_y = draw_centered(
        current_y, "5525 回到那一天 XMN 站", font_normal, (100, 255, 200)
    )
    current_y += 5

    # 4. 英文歡迎詞 (黃色)
    current_y = draw_centered(
        current_y, "Welcome to #5525 LIVE TOUR", font_normal, (255, 255, 50)
    )

    # 5. 分隔星號 (綠色)
    current_y = draw_centered(
        current_y,
        "****************************************",
        font_normal,
        (50, 200, 100),
    )
    current_y += 10

    # 6. 日期與數字 (黃色)
    current_y = draw_centered(current_y, "In 2025.5.25", font_normal, (255, 255, 50))
    current_y = draw_centered(current_y, "5521~5525", font_normal, (255, 255, 50))


def render_ascii_art(
    img_bgr: np.ndarray,
    cell_height: int = 12,
    input_height: Optional[int] = None,
    grabcut: bool = False,
    edge_threshold: int = 20,
    out_dir: Optional[Path] = None,
    stem: Optional[str] = None,
    info_panel: bool = False,
) -> np.ndarray:
    """Convert image to ASCII art rendered with Sarasa Gothic font.

    Pipeline:
    1. Downscale to input_height (preserve aspect ratio) if provided
    2. GrabCut foreground extraction (optional) — background set to white
    3. HED edge detection (connect gaps + skeletonize thinning) + Sobel gradients
    4. Per cell: classify edge char, space for non-edge
    5. Render onto white canvas with Sarasa Gothic
    """
    font = ImageFont.truetype(SARASA_FONT_PATH, cell_height)

    probe = Image.new("L", (cell_height * 2, cell_height * 2))
    bbox = ImageDraw.Draw(probe).textbbox((0, 0), "M", font=font)
    cell_w = int(bbox[2] - bbox[0])
    cell_h = int(bbox[3] - bbox[1])

    h, w = img_bgr.shape[:2]
    orig_h, orig_w = h, w
    if input_height is not None and h > input_height:
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
    grid_rows = max(1, h // cell_h)
    grid_cols = max(1, w // cell_w)

    resized = cv2.resize(gray, (int(grid_cols * cell_w), int(grid_rows * cell_h)))

    edges = _hed_edges(resized)

    if out_dir is not None:
        cv2.imwrite(str(out_dir / f"{stem}_edges.png"), edges)

    gx = cv2.Sobel(resized, cv2.CV_64F, 1, 0, ksize=3)
    gy = cv2.Sobel(resized, cv2.CV_64F, 0, 1, ksize=3)

    panel_width = 240 if info_panel else 0
    img_canvas_w = int(grid_cols * cell_w)
    canvas_w = img_canvas_w + panel_width
    canvas_h = int(grid_rows * cell_h)

    canvas = Image.new("RGB", (canvas_w, canvas_h), (0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    ascii_rows = []

    for row in range(grid_rows):
        y0, y1 = row * cell_h, (row + 1) * cell_h
        current_row_chars = []
        for col in range(grid_cols):
            x0, x1 = col * cell_w, (col + 1) * cell_w

            if edges[y0:y1, x0:x1].mean() > edge_threshold:
                char = _classify_edge_cell(gx[y0:y1, x0:x1], gy[y0:y1, x0:x1], cell_h)
            else:
                char = " "

            current_row_chars.append(char)
            if char != " ":
                draw.text((x0, y0), char, fill=(0, 255, 0), font=font)

        ascii_rows.append("".join(current_row_chars))

    if info_panel:
        from datetime import datetime

        info = {
            "Title": stem.replace("_", " ").title() if stem else "Untitled Image",
            "Date": datetime.now().strftime("%Y-%m-%d"),
            "Original": f"{orig_w}x{orig_h}",
            "Output": f"{img_canvas_w}x{canvas_h}",
            "Grid": f"{grid_cols}x{grid_rows}",
            "Cell": f"{cell_height}px",
            "Thresh": f"{edge_threshold}",
        }
        _draw_info_panel(
            draw,
            img_canvas_w + 40,
            60,
            canvas_h,
            info,
            SARASA_FONT_PATH,
            base_font_size=12,
        )

    if out_dir is not None and stem is not None:
        txt_path = out_dir / f"{stem}_ascii.txt"
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write("\n".join(ascii_rows))

    return cv2.cvtColor(np.array(canvas), cv2.COLOR_RGB2BGR)


def ascii_art_font_available() -> bool:
    return Path(SARASA_FONT_PATH).exists()
