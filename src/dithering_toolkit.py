import numpy as np
from loguru import logger

from .config import COLOR_LEVELS


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
    if color_levels < 2:
        logger.warning(f"色阶数量必须至少为2，已自动调整为2。")
        color_levels = 2
    logger.info(f"应用 Jarvis-Judice-Ninke 抖动到 {color_levels} 级灰度。")

    dithered_img = gray_img.copy().astype(np.float32)

    height, width = dithered_img.shape
    levels = np.linspace(0, 255, color_levels)

    for y in range(height):
        for x in range(width):
            old_pixel = dithered_img[y, x]
            new_pixel = levels[np.argmin(np.abs(levels - old_pixel))]
            dithered_img[y, x] = new_pixel

            quant_error = old_pixel - new_pixel
            factor = quant_error / 16.0

            # 扩散到右边的像素
            if x + 1 < width:
                dithered_img[y, x + 1] += factor * 7
            if x + 2 < width:
                dithered_img[y, x + 2] += factor * 5

            # 扩散到下一行
            if y + 1 < height:
                if x - 2 >= 0:
                    dithered_img[y + 1, x - 2] += factor * 3
                if x - 1 >= 0:
                    dithered_img[y + 1, x - 1] += factor * 5
                dithered_img[y + 1, x] += factor * 7
                if x + 1 < width:
                    dithered_img[y + 1, x + 1] += factor * 5
                if x + 2 < width:
                    dithered_img[y + 1, x + 2] += factor * 3

            # 扩散到下下一行
            if y + 2 < height:
                if x - 2 >= 0:
                    dithered_img[y + 2, x - 2] += factor * 1
                if x - 1 >= 0:
                    dithered_img[y + 2, x - 1] += factor * 3
                dithered_img[y + 2, x] += factor * 5
                if x + 1 < width:
                    dithered_img[y + 2, x + 1] += factor * 3
                if x + 2 < width:
                    dithered_img[y + 2, x + 2] += factor * 1

    return np.clip(dithered_img, 0, 255).astype(np.uint8)


def floyd_steinberg_dithering(
    gray_img: np.ndarray, color_levels: int = COLOR_LEVELS
) -> np.ndarray:
    """
    对灰度图应用 Floyd-Steinberg 抖动算法。
    Args:
        gray_img: 灰度 numpy.ndarray
        color_levels: 目标灰度色阶数量 (例如，16代表4位深度)
    Returns:
        抖动后的灰度 numpy.ndarray
    """
    if color_levels < 2:
        logger.warning(f"色阶数量必须至少为2，已自动调整为2。")
        color_levels = 2
    logger.info(f"应用 Floyd-Steinberg 抖动到 {color_levels} 级灰度。")

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
    dither_method: str = "jarvis_judice_ninke",
    color_levels: int = COLOR_LEVELS,
) -> np.ndarray:
    """
    对灰度图应用抖动算法。
    Args:
        gray_img: 灰度图
        dither_method: 抖动方法，支持 "floyd_steinberg" 和 "jarvis_judice_ninke"
        color_levels: 目标灰度色阶数量
    Returns:
        抖动后的灰度 numpy.ndarray
    """
    if dither_method == "floyd_steinberg":
        return floyd_steinberg_dithering(gray_img, color_levels)
    elif dither_method == "jarvis_judice_ninke":
        return jarvis_judice_ninke_dithering(gray_img, color_levels)
    else:
        raise ValueError(f"不支持的抖动方法: {dither_method}")
