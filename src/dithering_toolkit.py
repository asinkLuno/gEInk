from typing import Callable

import numpy as np
from loguru import logger

# Atkinson: 6/8 error propagation — crisp for graphics/e-ink, loses photo mid-tones
ATKINSON_KERNEL: list[tuple[int, int, float]] = [
    (0, 1, 1 / 8),
    (0, 2, 1 / 8),
    (1, -1, 1 / 8),
    (1, 0, 1 / 8),
    (1, 1, 1 / 8),
    (2, 0, 1 / 8),
]

# Floyd-Steinberg: full 16/16 error, 4 neighbors — best general-purpose for photos
FLOYD_STEINBERG_KERNEL: list[tuple[int, int, float]] = [
    (0, 1, 7 / 16),
    (1, -1, 3 / 16),
    (1, 0, 5 / 16),
    (1, 1, 1 / 16),
]

# Stucki: full error over 12 neighbors — smoothest gradients for high-res photos
STUCKI_KERNEL: list[tuple[int, int, float]] = [
    (0, 1, 8 / 42),
    (0, 2, 4 / 42),
    (1, -2, 2 / 42),
    (1, -1, 4 / 42),
    (1, 0, 8 / 42),
    (1, 1, 4 / 42),
    (1, 2, 2 / 42),
    (2, -2, 1 / 42),
    (2, -1, 2 / 42),
    (2, 0, 4 / 42),
    (2, 1, 2 / 42),
    (2, 2, 1 / 42),
]

DITHER_KERNELS: dict[str, list[tuple[int, int, float]]] = {
    "atkinson": ATKINSON_KERNEL,
    "floyd_steinberg": FLOYD_STEINBERG_KERNEL,
    "stucki": STUCKI_KERNEL,
}


def error_diffusion(
    img: np.ndarray,
    quantize_fn: Callable[[np.ndarray], np.ndarray],
    kernel: list[tuple[int, int, float]],
) -> np.ndarray:
    """Generic error-diffusion dithering. Works for both grayscale and color images."""
    dithered = img.astype(np.float32)
    h, w = dithered.shape[:2]
    for y in range(h):
        for x in range(w):
            old = dithered[y, x].copy()
            new = quantize_fn(old)
            dithered[y, x] = new
            error = old - new
            if np.all(error == 0):
                continue
            for dy, dx, weight in kernel:
                ny, nx = y + dy, x + dx
                if 0 <= ny < h and 0 <= nx < w:
                    dithered[ny, nx] += error * weight
    return np.clip(dithered, 0, 255).astype(np.uint8)


def _threshold(pixel: np.ndarray) -> np.ndarray:
    return np.where(pixel >= 128.0, 255.0, 0.0)


def binary_thresholding(gray_img: np.ndarray, threshold: int = 128) -> np.ndarray:
    result = gray_img.copy()
    result[result <= threshold] = 0
    result[result > threshold] = 255
    return result.astype(np.uint8)


def apply_dithering(
    gray_img: np.ndarray,
    dither_method: str = "atkinson",
) -> np.ndarray:
    if dither_method == "binary_threshold":
        logger.info("应用 binary_threshold 抖动（1-bit）。")
        return binary_thresholding(gray_img)
    kernel = DITHER_KERNELS.get(dither_method)
    if kernel is None:
        raise ValueError(
            f"不支持的抖动方法: {dither_method}，可选: {list(DITHER_KERNELS) + ['binary_threshold']}"
        )
    logger.info(f"应用 {dither_method} 抖动（1-bit）。")
    return error_diffusion(gray_img, _threshold, kernel)
