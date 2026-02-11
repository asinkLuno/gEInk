import numpy as np
from loguru import logger

from .config import COLOR_LEVELS

# Error diffusion kernels (normalized to 1.0)
# Structure: [(dy, dx, weight), ...]
FLOYD_STEINBERG_KERNEL = [
    (0, 1, 7 / 16),
    (1, -1, 3 / 16),
    (1, 0, 5 / 16),
    (1, 1, 1 / 16),
]

JARVIS_JUDICE_NINKE_KERNEL = [
    # Current row
    (0, 1, 7 / 48),
    (0, 2, 5 / 48),
    # Next row
    (1, -2, 3 / 48),
    (1, -1, 5 / 48),
    (1, 0, 7 / 48),
    (1, 1, 5 / 48),
    (1, 2, 3 / 48),
    # Two rows down
    (2, -2, 1 / 48),
    (2, -1, 3 / 48),
    (2, 0, 5 / 48),
    (2, 1, 3 / 48),
    (2, 2, 1 / 48),
]

STUCKI_KERNEL = [
    # Current row
    (0, 1, 8 / 42),
    (0, 2, 4 / 42),
    # Next row
    (1, -2, 2 / 42),
    (1, -1, 4 / 42),
    (1, 0, 8 / 42),
    (1, 1, 4 / 42),
    (1, 2, 2 / 42),
    # Two rows down
    (2, -2, 1 / 42),
    (2, -1, 2 / 42),
    (2, 0, 4 / 42),
    (2, 1, 2 / 42),
    (2, 2, 1 / 42),
]


def _apply_error_diffusion(
    gray_img: np.ndarray, kernel: list, color_levels: int
) -> np.ndarray:
    """
    Apply error diffusion dithering with a given kernel.

    Args:
        gray_img: Input grayscale numpy.ndarray (0-255)
        kernel: List of (dy, dx, weight) tuples for error diffusion
        color_levels: Number of output color levels

    Returns:
        Dithered grayscale numpy.ndarray
    """
    if color_levels < 2:
        logger.warning(f"色阶数量必须至少为2，已自动调整为2。")
        color_levels = 2

    dithered = gray_img.astype(np.float32)
    height, width = dithered.shape

    # Pre-compute quantization levels
    levels = np.linspace(0, 255, color_levels)

    # Pre-compute level indices for fast lookup
    # Create level boundaries: [0, mid1, mid2, ..., 255]
    level_centers = (levels[:-1] + levels[1:]) / 2

    for y in range(height):
        row = dithered[y]
        for x in range(width):
            old_pixel = row[x]

            # Quantize to nearest level using binary search (O(log n))
            idx = np.searchsorted(level_centers, old_pixel)
            idx = min(idx, color_levels - 1)
            new_pixel = levels[idx]
            row[x] = new_pixel

            # Diffuse error
            quant_error = old_pixel - new_pixel
            for dy, dx, weight in kernel:
                ny, nx = y + dy, x + dx
                if 0 <= ny < height and 0 <= nx < width:
                    dithered[ny, nx] += quant_error * weight

    return np.clip(dithered, 0, 255).astype(np.uint8)


def floyd_steinberg_dithering(
    gray_img: np.ndarray, color_levels: int = COLOR_LEVELS
) -> np.ndarray:
    """
    对灰度图应用 Floyd-Steinberg 抖动算法。
    Args:
        gray_img: 灰度 numpy.ndarray
        color_levels: 目标灰度色阶数量
    Returns:
        抖动后的灰度 numpy.ndarray
    """
    logger.info(f"应用 Floyd-Steinberg 抖动到 {color_levels} 级灰度。")
    return _apply_error_diffusion(gray_img, FLOYD_STEINBERG_KERNEL, color_levels)


def jarvis_judice_ninke_dithering(
    gray_img: np.ndarray, color_levels: int = COLOR_LEVELS
) -> np.ndarray:
    """
    对灰度图应用 Jarvis-Judice-Ninke (JJN) 抖动算法。
    误差扩散范围比 Floyd-Steinberg 更大，适合高质量图像。
    Args:
        gray_img: 灰度 numpy.ndarray
        color_levels: 目标灰度色阶数量
    Returns:
        抖动后的灰度 numpy.ndarray
    """
    logger.info(f"应用 Jarvis-Judice-Ninke 抖动到 {color_levels} 级灰度。")
    return _apply_error_diffusion(gray_img, JARVIS_JUDICE_NINKE_KERNEL, color_levels)


def stucki_dithering(
    gray_img: np.ndarray, color_levels: int = COLOR_LEVELS
) -> np.ndarray:
    """
    对灰度图应用 Stucki 抖动算法。
    是 Jarvis-Judice-Ninke 的变体，产生更平滑的结果。
    Args:
        gray_img: 灰度 numpy.ndarray
        color_levels: 目标灰度色阶数量
    Returns:
        抖动后的灰度 numpy.ndarray
    """
    logger.info(f"应用 Stucki 抖动到 {color_levels} 级灰度。")
    return _apply_error_diffusion(gray_img, STUCKI_KERNEL, color_levels)


def apply_dithering(
    gray_img: np.ndarray,
    dither_method: str = "jarvis_judice_ninke",
    color_levels: int = COLOR_LEVELS,
) -> np.ndarray:
    """
    对灰度图应用抖动算法。
    Args:
        gray_img: 灰度图
        dither_method: 抖动方法，支持 "floyd_steinberg"、"jarvis_judice_ninke" 和 "stucki"
        color_levels: 目标灰度色阶数量
    Returns:
        抖动后的灰度 numpy.ndarray
    """
    methods = {
        "floyd_steinberg": floyd_steinberg_dithering,
        "jarvis_judice_ninke": jarvis_judice_ninke_dithering,
        "stucki": stucki_dithering,
    }
    if dither_method not in methods:
        raise ValueError(
            f"不支持的抖动方法: {dither_method}，可选方法: {list(methods.keys())}"
        )
    return methods[dither_method](gray_img, color_levels)
