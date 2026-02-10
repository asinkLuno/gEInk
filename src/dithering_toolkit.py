import numpy as np
from PIL import Image

from .config import COLOR_LEVELS


def _quantize_pixel(value: float, color_levels: int) -> int:
    """
    Quantizes a float pixel value (0-255) to one of the specified color_levels.
    """
    if color_levels <= 1:
        raise ValueError("color_levels must be greater than 1")

    # Calculate the step size for quantization
    # For color_levels=2, step_size = 255 / 1 = 255 (0 or 255)
    # For color_levels=4, step_size = 255 / 3 = 85 (0, 85, 170, 255)
    step_size = 255 / (color_levels - 1)

    # Quantize the value
    quantized_value = round(value / step_size) * step_size

    # Clamp to 0-255 range
    return int(max(0, min(255, quantized_value)))


def jarvis_judice_ninke_dithering(
    image_pil: Image.Image, color_levels: int = COLOR_LEVELS
) -> Image.Image:
    """
    Applies Jarvis, Judice, and Ninke error diffusion dithering to a PIL image,
    quantizing to the specified number of color_levels.
    """
    img_gray = image_pil.convert("L")  # Convert to grayscale
    pixels = np.array(img_gray, dtype=float)  # Convert to float for error diffusion
    width, height = img_gray.size

    # Jarvis, Judice, Ninke kernel
    # Sum of weights: (7+5)*1 + (3+5+7+5+3)*1 + (1+3+5+3+1)*1 = 12 + 23 + 13 = 48
    jjn_kernel = [
        # (dx, dy, weight) relative to current pixel (x,y)
        (1, 0, 7 / 48),
        (2, 0, 5 / 48),  # Current row
        (-2, 1, 3 / 48),
        (-1, 1, 5 / 48),
        (0, 1, 7 / 48),
        (1, 1, 5 / 48),
        (2, 1, 3 / 48),  # Next row
        (-2, 2, 1 / 48),
        (-1, 2, 3 / 48),
        (0, 2, 5 / 48),
        (1, 2, 3 / 48),
        (2, 2, 1 / 48),  # Row after next
    ]

    for y in range(height):
        for x in range(width):
            old_pixel = pixels[y, x]
            new_pixel = _quantize_pixel(old_pixel, color_levels)
            pixels[y, x] = new_pixel
            error = old_pixel - new_pixel

            for dx, dy, weight in jjn_kernel:
                nx, ny = x + dx, y + dy
                if 0 <= nx < width and 0 <= ny < height:
                    pixels[ny, nx] += error * weight

    # Convert back to a PIL Image in 'L' mode with the quantized colors
    return Image.fromarray(pixels.astype(np.uint8)).convert("L")


def floyd_steinberg_dithering(
    image_pil: Image.Image, color_levels: int = COLOR_LEVELS
) -> Image.Image:
    """
    Applies Floyd-Steinberg error diffusion dithering to a PIL image,
    quantizing to the specified number of color_levels.
    """
    img_gray = image_pil.convert("L")  # Convert to grayscale
    pixels = np.array(img_gray, dtype=float)  # Convert to float for error diffusion
    width, height = img_gray.size

    # Floyd-Steinberg kernel
    # Sum of weights: 7/16 + 3/16 + 5/16 + 1/16 = 16/16 = 1
    fs_kernel = [
        (1, 0, 7 / 16),  # Current row, next pixel
        (-1, 1, 3 / 16),  # Next row, previous pixel
        (0, 1, 5 / 16),  # Next row, current pixel
        (1, 1, 1 / 16),  # Next row, next pixel
    ]

    for y in range(height):
        for x in range(width):
            old_pixel = pixels[y, x]
            new_pixel = _quantize_pixel(old_pixel, color_levels)
            pixels[y, x] = new_pixel
            error = old_pixel - new_pixel

            for dx, dy, weight in fs_kernel:
                nx, ny = x + dx, y + dy
                if 0 <= nx < width and 0 <= ny < height:
                    pixels[ny, nx] += error * weight

    return Image.fromarray(pixels.astype(np.uint8)).convert("L")


def apply_dithering(
    image_pil: Image.Image,
    dither_method: str = "floyd_steinberg",
    color_levels: int = COLOR_LEVELS,
) -> Image.Image:
    """
    Applies the specified dithering algorithm to a PIL image.
    """
    if dither_method == "floyd_steinberg":
        return floyd_steinberg_dithering(image_pil, color_levels)
    elif dither_method == "jarvis_judice_ninke":
        return jarvis_judice_ninke_dithering(image_pil, color_levels)
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
