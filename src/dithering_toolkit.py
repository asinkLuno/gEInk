import numpy as np
from loguru import logger

from .config import COLOR_LEVELS


def floyd_steinberg_dithering(
    gray_img: np.ndarray, color_levels: int = COLOR_LEVELS
) -> np.ndarray:
    """
    对灰度图应用Floyd-Steinberg抖动算法。
    Args:
        gray_img: 灰度 numpy.ndarray
        color_levels: 目标灰度色阶数量 (例如，16代表4位深度)
    Returns:
        抖动后的灰度 numpy.ndarray
    """
    if color_levels < 2:
        logger.warning(f"色阶数量必须至少为2，已自动调整为2。")
        color_levels = 2
    logger.info(f"应用Floyd-Steinberg抖动到 {color_levels} 级灰度。")

    dithered_img = gray_img.copy().astype(np.float32)

    height, width = dithered_img.shape

    levels = np.linspace(0, 255, color_levels)

    for y in range(height):
        for x in range(width):
            old_pixel = dithered_img[y, x]
            new_pixel = levels[np.argmin(np.abs(levels - old_pixel))]
            dithered_img[y, x] = new_pixel

            quant_error = old_pixel - new_pixel

            if x + 1 < width:
                dithered_img[y, x + 1] += quant_error * 7 / 16
            if y + 1 < height:
                if x - 1 >= 0:
                    dithered_img[y + 1, x - 1] += quant_error * 3 / 16
                dithered_img[y + 1, x] += quant_error * 5 / 16
                if x + 1 < width:
                    dithered_img[y + 1, x + 1] += quant_error * 1 / 16

    return np.clip(dithered_img, 0, 255).astype(np.uint8)


def apply_dithering(
    gray_img: np.ndarray,
    dither_method: str = "floyd_steinberg",
    color_levels: int = COLOR_LEVELS,
) -> np.ndarray:
    """
    对灰度图应用抖动算法。
    Currently only supports "floyd_steinberg".
    """
    if dither_method == "floyd_steinberg":
        return floyd_steinberg_dithering(gray_img, color_levels)
    else:
        raise ValueError(f"Unsupported dithering method: {dither_method}")
