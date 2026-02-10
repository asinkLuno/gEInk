import numpy as np
from PIL import Image


def jarvis_judice_ninke_dithering(image_pil: Image.Image) -> Image.Image:
    """
    Applies Jarvis, Judice, and Ninke error diffusion dithering to a PIL image.
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
            new_pixel = 255 if old_pixel >= 128 else 0
            pixels[y, x] = new_pixel
            error = old_pixel - new_pixel

            for dx, dy, weight in jjn_kernel:
                nx, ny = x + dx, y + dy
                if 0 <= nx < width and 0 <= ny < height:
                    pixels[ny, nx] += error * weight

    # Convert back to a 1-bit PIL Image
    # np.where(pixels > 128, 255, 0) ensures values are 0 or 255
    # Then Image.fromarray().convert('1') will handle the final binarization and format
    return Image.fromarray(pixels.astype(np.uint8)).convert("1")


def dither_and_convert_to_epd_format(
    image_pil: Image.Image,
    output_bin_path: str,
    target_width: int,
    target_height: int,
    dither_method: str = "floyd_steinberg",
) -> bool:
    """
    Applies the specified dithering algorithm and converts the image to EPD raw binary format.
    """
    # --- Step 4: Binarization (1-bit Black and White) ---
    img_1bit: Image.Image

    if dither_method == "floyd_steinberg":
        img_1bit = image_pil.convert("1", dither=Image.FLOYDSTEINBERG)
    elif dither_method == "jarvis_judice_ninke":
        img_1bit = jarvis_judice_ninke_dithering(image_pil)
    else:
        raise ValueError(f"Unsupported dithering method: {dither_method}")

    pixels_raw = np.array(
        img_1bit
    )  # Gives boolean array where True is black (0), False is white (255)

    # Map PIL's 0 (black) to 1 (black for EPD), and PIL's 255 (white) to 0 (white for EPD)
    pixels_epd_format = np.where(pixels_raw == 0, 1, 0).astype(np.uint8)

    # --- Step 5: Convert to EPD Raw Format (.bin) ---
    byte_array = bytearray()
    for r in range(target_height):
        for c_byte in range(target_width // 8):
            byte_value = 0
            for bit_offset in range(8):
                # Get pixel value from epd_format, which is already 0 (white) or 1 (black)
                pixel_value = pixels_epd_format[r, c_byte * 8 + bit_offset]
                if pixel_value == 1:  # If black pixel
                    byte_value |= 1 << (
                        7 - bit_offset
                    )  # Set corresponding bit (MSB first)
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
