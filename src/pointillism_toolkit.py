import cv2
import numpy as np
from loguru import logger

# 默认 7 色调色盘: 黑, 白, 红, 绿, 蓝, 黄, 橙 (BGR 顺序)
# 选色参考 ACeP 七色标准并进行审美优化
DEFAULT_PALETTE = np.array([
    [0, 0, 0],          # Black
    [255, 255, 255],    # White
    [0, 0, 200],        # Red (沉稳红)
    [0, 160, 0],        # Green (森林绿)
    [160, 0, 0],        # Blue (深海蓝)
    [0, 220, 255],      # Yellow (明黄)
    [0, 110, 255]       # Orange (活力橙)
], dtype=np.float32)

ATKINSON_KERNEL = [
    (0, 1, 1 / 8),
    (0, 2, 1 / 8),
    (1, -1, 1 / 8),
    (1, 0, 1 / 8),
    (1, 1, 1 / 8),
    (2, 0, 1 / 8),
]


def color_dither_atkinson(img: np.ndarray, palette: np.ndarray) -> np.ndarray:
    h, w, _ = img.shape
    dithered = img.astype(np.float32).copy()
    for y in range(h):
        for x in range(w):
            old = dithered[y, x].copy()
            new = palette[np.argmin(np.linalg.norm(palette - old, axis=1))]
            dithered[y, x] = new
            error = old - new
            for dy, dx, weight in ATKINSON_KERNEL:
                ny, nx = y + dy, x + dx
                if 0 <= ny < h and 0 <= nx < w:
                    dithered[ny, nx] += error * weight
    return np.clip(dithered, 0, 255).astype(np.uint8)


def _draw_dot(canvas: np.ndarray, cx: int, cy: int, radius: int, color: np.ndarray):
    h, w = canvas.shape[:2]
    y0, y1 = max(0, cy - radius), min(h, cy + radius + 1)
    x0, x1 = max(0, cx - radius), min(w, cx + radius + 1)
    ys = np.arange(y0, y1) - cy
    xs = np.arange(x0, x1) - cx
    DX, DY = np.meshgrid(xs, ys)
    dist2 = (DX ** 2 + DY ** 2).astype(np.float32)

    # 高斯衰减：中心全色，边缘渐淡，圆外截断
    sigma2 = (radius * 0.5) ** 2
    alpha = np.exp(-dist2 / (2 * sigma2))
    alpha[dist2 > radius ** 2] = 0.0

    region = canvas[y0:y1, x0:x1].astype(np.float32)
    alpha3 = alpha[:, :, np.newaxis]
    canvas[y0:y1, x0:x1] = np.clip(
        region * (1 - alpha3) + np.array(color, dtype=np.float32) * alpha3, 0, 255
    ).astype(np.uint8)


def _render_dots(
    canvas: np.ndarray,
    dithered_small: np.ndarray,
    h_grid: int,
    w_grid: int,
    spacing: int,
    dot_radius: int,
    mask: np.ndarray | None = None,
):
    """将 dithered_small 渲染为规则点阵到 canvas。
    mask 为全图分辨率的布尔遮罩，仅在点中心落入 mask=True 区域时绘制。
    """
    for gy in range(h_grid):
        for gx in range(w_grid):
            cy = int((gy + 0.5) * spacing)
            cx = int((gx + 0.5) * spacing)
            if mask is not None:
                if not mask[min(cy, mask.shape[0] - 1), min(cx, mask.shape[1] - 1)]:
                    continue
            _draw_dot(canvas, cx, cy, dot_radius, dithered_small[gy, gx])


def apply_pointillism(
    img: np.ndarray,
    palette: np.ndarray = DEFAULT_PALETTE,
    dot_radius: int = 3,
    spacing: int = 8,
) -> np.ndarray:
    """基础点彩：Atkinson 抖动 + 不重叠实心圆点。"""
    h, w, _ = img.shape
    h_grid = max(1, h // spacing)
    w_grid = max(1, w // spacing)
    img_small = cv2.resize(img, (w_grid, h_grid), interpolation=cv2.INTER_AREA)
    logger.info(f"在 {w_grid}x{h_grid} 点阵上做 Atkinson 减色抖动...")
    dithered_small = color_dither_atkinson(img_small, palette)
    canvas = np.full((h, w, 3), 255, dtype=np.uint8)
    _render_dots(canvas, dithered_small, h_grid, w_grid, spacing, dot_radius)
    logger.info(f"完成：共渲染 {h_grid * w_grid} 个点")
    return canvas


def apply_pointillism_layered(
    img: np.ndarray,
    palette: np.ndarray = DEFAULT_PALETTE,
    dot_radius: int = 3,
    spacing: int = 8,
    mean_shift_sp: int = 20,
    mean_shift_sr: int = 40,
    highlight_thresh: int = 220,
    shadow_thresh: int = 35,
    overlay_dot_radius: int = 2,
    overlay_spacing: int = 5,
) -> np.ndarray:
    """
    分层点彩画：

    Layer 1 - 大色块底层：Mean Shift 平滑消除细纹理 → Atkinson 抖动 → 全图不重叠点。
    Layer 2 - 高光叠加：原图亮度 >= highlight_thresh 的区域，叠加更细密的点。
    Layer 3 - 阴影叠加：原图亮度 <= shadow_thresh 的区域，叠加更细密的点。

    高光/阴影层基于原图（不用平滑图），保真极值区域的颜色。
    叠加层可与底层重叠，增强光感对比。
    """
    h, w, _ = img.shape

    # --- Layer 1: 大色块底层 ---
    logger.info("Mean Shift 平滑，分割大色块...")
    smoothed = cv2.pyrMeanShiftFiltering(img, mean_shift_sp, mean_shift_sr)

    h_base = max(1, h // spacing)
    w_base = max(1, w // spacing)
    base_small = cv2.resize(smoothed, (w_base, h_base), interpolation=cv2.INTER_AREA)

    logger.info(f"大色块层：{w_base}x{h_base} 网格 Atkinson 抖动...")
    dithered_base = color_dither_atkinson(base_small, palette)

    canvas = np.full((h, w, 3), 255, dtype=np.uint8)
    _render_dots(canvas, dithered_base, h_base, w_base, spacing, dot_radius)
    logger.info(f"大色块层完成：{h_base * w_base} 个点")

    # --- 高光/阴影遮罩（基于原图，保留真实极值）---
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    highlight_mask = gray >= highlight_thresh
    shadow_mask = gray <= shadow_thresh

    # 叠加层在更细的网格上抖动（dot 更小更密）
    h_ov = max(1, h // overlay_spacing)
    w_ov = max(1, w // overlay_spacing)
    ov_small = cv2.resize(img, (w_ov, h_ov), interpolation=cv2.INTER_AREA)

    logger.info(f"叠加层：{w_ov}x{h_ov} 网格 Atkinson 抖动...")
    dithered_ov = color_dither_atkinson(ov_small, palette)

    if highlight_mask.any():
        logger.info(f"绘制高光叠加层（覆盖 {highlight_mask.mean():.1%} 面积）...")
        _render_dots(canvas, dithered_ov, h_ov, w_ov, overlay_spacing, overlay_dot_radius, highlight_mask)

    if shadow_mask.any():
        logger.info(f"绘制阴影叠加层（覆盖 {shadow_mask.mean():.1%} 面积）...")
        _render_dots(canvas, dithered_ov, h_ov, w_ov, overlay_spacing, overlay_dot_radius, shadow_mask)

    return canvas
