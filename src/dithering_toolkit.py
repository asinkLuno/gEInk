import numpy as np
from loguru import logger

# Atkinson dithering: diffuses only 75% of the error (6/8)
# Crisper results on low-contrast displays like e-ink
#
#     * 1 1
#   1 1 1
#     1
#  (each = 1/8)
ATKINSON_KERNEL = [
    (0, 1, 1 / 8),
    (0, 2, 1 / 8),
    (1, -1, 1 / 8),
    (1, 0, 1 / 8),
    (1, 1, 1 / 8),
    (2, 0, 1 / 8),
]


def atkinson_dithering(gray_img: np.ndarray) -> np.ndarray:
    dithered = gray_img.astype(np.float32)
    height, width = dithered.shape

    for y in range(height):
        for x in range(width):
            old = dithered[y, x]
            new = 255.0 if old >= 128.0 else 0.0
            dithered[y, x] = new
            error = old - new
            if error == 0.0:
                continue
            for dy, dx, w in ATKINSON_KERNEL:
                ny, nx = y + dy, x + dx
                if 0 <= ny < height and 0 <= nx < width:
                    dithered[ny, nx] += error * w

    return dithered.astype(np.uint8)


def binary_thresholding(gray_img: np.ndarray, threshold: int = 128) -> np.ndarray:
    result = gray_img.copy()
    result[result <= threshold] = 0
    result[result > threshold] = 255
    return result


def apply_dithering(
    gray_img: np.ndarray,
    dither_method: str = "atkinson",
) -> np.ndarray:
    methods = {
        "atkinson": atkinson_dithering,
        "binary_threshold": binary_thresholding,
    }
    if dither_method not in methods:
        raise ValueError(
            f"不支持的抖动方法: {dither_method}，可选方法: {list(methods.keys())}"
        )
    logger.info(f"应用 {dither_method} 抖动（1-bit）。")
    if dither_method == "binary_threshold":
        return binary_thresholding(gray_img)
    return atkinson_dithering(gray_img)
