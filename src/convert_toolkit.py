"""Convert toolkit for transforming dithered images to EPD binary format."""

import math
from pathlib import Path

import cv2
from loguru import logger


def convert_png_to_bin(
    input_path: str,
    output_path: str,
    width: int,
    height: int,
    color_levels: int = 4,
) -> bool:
    """
    Convert a dithered PNG image to EPD binary format.

    Args:
        input_path: Path to input PNG file (grayscale, dithered)
        output_path: Path to output .bin file
        width: Target width in pixels
        height: Target height in pixels
        color_levels: Number of color levels (must be power of 2)

    Returns:
        True if successful, False otherwise
    """
    # Validate color_levels
    if color_levels & (color_levels - 1) != 0:
        logger.error(f"color_levels must be power of 2, got {color_levels}")
        return False

    bits_per_pixel = int(math.log2(color_levels))

    # Read image as grayscale
    img = cv2.imread(input_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        logger.error(f"Failed to read image: {input_path}")
        return False

    # Check dimensions
    if img.shape[1] != width or img.shape[0] != height:
        logger.warning(
            f"Image size {img.shape[1]}x{img.shape[0]} doesn't match expected {width}x{height}"
        )

    # Resize if needed
    if img.shape[1] != width or img.shape[0] != height:
        img = cv2.resize(img, (width, height), interpolation=cv2.INTER_NEAREST)
        logger.info(f"Resized to {width}x{height}")

    # Pack pixels into bytes
    # For 2-bit (4 levels): 4 pixels per byte
    # For 1-bit (2 levels): 8 pixels per byte
    pixels_per_byte = 8 // bits_per_pixel

    # Calculate expected file size
    total_pixels = width * height
    total_bytes = (total_pixels + pixels_per_byte - 1) // pixels_per_byte

    logger.info(f"Packing {total_pixels} pixels into {total_bytes} bytes")
    logger.info(f"Format: {bits_per_pixel}-bit, {color_levels} levels, {pixels_per_byte} pixels/byte")

    # Convert to binary
    binary_data = bytearray()
    pixel_count = 0

    for y in range(height):
        for x in range(width):
            pixel_value = int(img[y, x])

            # Normalize to color_levels range (0 to color_levels-1)
            # Input is 0-255, need to map to 0-(color_levels-1)
            normalized = (pixel_value * color_levels) // 256

            if pixel_count % pixels_per_byte == 0:
                # Start new byte
                byte_value = normalized
            else:
                # Pack into current byte
                byte_value = (byte_value << bits_per_pixel) | normalized

            pixel_count += 1

            # When byte is full, append to data
            if pixel_count % pixels_per_byte == 0:
                binary_data.append(byte_value)

    # Handle last partial byte if any
    if pixel_count % pixels_per_byte != 0:
        # Shift remaining bits to leftmost position
        remaining_bits = pixel_count % pixels_per_byte
        byte_value = byte_value << (bits_per_pixel * (pixels_per_byte - remaining_bits))
        binary_data.append(byte_value)

    # Write to file
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "wb") as f:
        f.write(binary_data)

    logger.success(f"Converted {input_path} -> {output_path}")
    logger.info(f"Output size: {len(binary_data)} bytes ({len(binary_data) / 1024:.1f} KB)")

    return True
