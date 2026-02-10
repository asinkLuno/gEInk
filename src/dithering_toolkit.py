import cv2
import numpy as np
from loguru import logger
from PIL import Image

from .config import COLOR_LEVELS


def _pil_to_cv2(pil_img: Image.Image) -> np.ndarray:
    """
    Convert PIL Image to OpenCV BGR format.
    Handles RGB, RGBA, and L modes.
    """
    if pil_img.mode == "RGB":
        # PIL RGB -> OpenCV BGR
        cv2_img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    elif pil_img.mode == "RGBA":
        # PIL RGBA -> OpenCV BGRA -> BGR
        cv2_img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGBA2BGRA)
        cv2_img = cv2.cvtColor(cv2_img, cv2.COLOR_BGRA2BGR)
    elif pil_img.mode == "L":
        # Grayscale -> BGR (3 identical channels)
        gray = np.array(pil_img)
        cv2_img = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    else:
        # Convert to RGB first
        rgb_img = pil_img.convert("RGB")
        cv2_img = cv2.cvtColor(np.array(rgb_img), cv2.COLOR_RGB2BGR)
    return cv2_img


def _cv2_to_pil(cv2_img: np.ndarray) -> Image.Image:
    """
    Convert OpenCV BGR image to PIL RGB Image.
    """
    rgb_img = cv2.cvtColor(cv2_img, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb_img)


def floyd_steinberg_dithering(
    image_pil: Image.Image, color_levels: int = COLOR_LEVELS
) -> Image.Image:
    """
    对图片应用Floyd-Steinberg抖动算法，将其转换为指定色阶的灰度图像。
    基于旧版本 image_processor.py 的实现。
    Args:
        image_pil: PIL图片
        color_levels: 目标灰度色阶数量 (例如，16代表4位深度)
    Returns:
        抖动后的指定色阶灰度PIL图片 (L模式)
    """
    if color_levels < 2:
        logger.warning(f"色阶数量必须至少为2，已自动调整为2。")
        color_levels = 2
    logger.info(f"应用Floyd-Steinberg抖动到 {color_levels} 级灰度。")

    # Convert PIL to OpenCV BGR
    img_bgr = _pil_to_cv2(image_pil)

    # 转换为灰度图
    gray_img = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

    # 复制一份图像用于修改，避免修改原始图像
    dithered_img = gray_img.copy().astype(np.float32)

    height, width = dithered_img.shape

    # 计算色阶值（移到循环外，避免重复计算）
    # 例如，对于16个色阶，值范围是 0, 17, 34, ..., 255
    levels = np.linspace(0, 255, color_levels)

    for y in range(height):
        for x in range(width):
            old_pixel = dithered_img[y, x]

            # 量化到最近的色阶值
            # 找到levels中最接近old_pixel的值
            new_pixel = levels[np.argmin(np.abs(levels - old_pixel))]
            dithered_img[y, x] = new_pixel

            # 计算量化误差
            quant_error = old_pixel - new_pixel

            # 将误差传播到周围像素 (Floyd-Steinberg权重)
            #       X   7/16
            # 3/16 5/16 1/16
            if x + 1 < width:
                dithered_img[y, x + 1] += quant_error * 7 / 16
            if y + 1 < height:
                if x - 1 >= 0:
                    dithered_img[y + 1, x - 1] += quant_error * 3 / 16
                dithered_img[y + 1, x] += quant_error * 5 / 16
                if x + 1 < width:
                    dithered_img[y + 1, x + 1] += quant_error * 1 / 16

    # 将结果裁剪到0-255范围并转换回uint8类型
    dithered_result = np.clip(dithered_img, 0, 255).astype(np.uint8)

    # Convert back to PIL (grayscale)
    return Image.fromarray(dithered_result).convert("L")


def apply_dithering(
    image_pil: Image.Image,
    dither_method: str = "floyd_steinberg",
    color_levels: int = COLOR_LEVELS,
) -> Image.Image:
    """
    Applies the specified dithering algorithm to a PIL image.
    Currently only supports "floyd_steinberg".
    """
    if dither_method == "floyd_steinberg":
        return floyd_steinberg_dithering(image_pil, color_levels)
    else:
        raise ValueError(f"Unsupported dithering method: {dither_method}")


import math  # Added for log2 in convert_to_epd_format


def convert_to_epd_format(
    image_multi_bit_pil: Image.Image,
    output_bin_path: str,
    target_width: int,
    target_height: int,
    color_levels: int = COLOR_LEVELS,
) -> bool:
    """
    Converts a multi-bit PIL Image (L mode) to EPD raw binary format,
    packing pixels according to BITS_PER_PIXEL derived from color_levels.
    """
    if image_multi_bit_pil.mode != "L":
        raise ValueError(
            "Input image for EPD conversion must be in 'L' (grayscale) mode."
        )

    if color_levels <= 1 or not (color_levels & (color_levels - 1) == 0):
        raise ValueError("color_levels must be a power of 2 greater than 1.")

    pixels_array = np.array(image_multi_bit_pil, dtype=np.uint8)

    # Normalize pixel values to 0- (color_levels - 1) range for bit packing
    # Current pixels are 0, (255/(color_levels-1)), ..., 255
    # We want 0, 1, ..., (color_levels-1)
    normalized_pixels = (pixels_array * (color_levels - 1) // 255).astype(
        np.uint8
    )  # Use integer division for pixel normalization

    byte_array = bytearray()

    # Calculate bits_per_pixel from color_levels
    bits_per_pixel = int(math.log2(color_levels))

    if (
        bits_per_pixel == 0
    ):  # Handle 1 color level case (should be caught by validation)
        raise ValueError("color_levels must be greater than 1")

    pixels_per_byte = 8 // bits_per_pixel

    for r in range(target_height):
        for c_byte_group in range(0, target_width, pixels_per_byte):
            byte_value = 0
            for bit_offset_in_byte in range(pixels_per_byte):
                c = c_byte_group + bit_offset_in_byte
                if c < target_width:  # Boundary check
                    pixel_value = normalized_pixels[r, c]
                    # Shift value to its position in the byte (MSB first)
                    byte_value |= pixel_value << (
                        (pixels_per_byte - 1 - bit_offset_in_byte) * bits_per_pixel
                    )
            byte_array.append(byte_value)

    # Save the raw binary data
    try:
        with open(output_bin_path, "wb") as f:
            f.write(byte_array)
        print(f"Successfully saved to '{output_bin_path}'.")
        return True
    except Exception as e:
        print(f"Error saving binary file '{output_bin_path}': {e}")
        return False
