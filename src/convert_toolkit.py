"""Convert toolkit for transforming dithered images to EPD binary format."""

from pathlib import Path

import cv2
import numpy as np
from loguru import logger


def convert_png_to_bin(
    input_path: str,
    output_path: str,
    width: int,
    height: int,
) -> bool:
    img = cv2.imread(input_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        logger.error(f"Failed to read image: {input_path}")
        return False

    if img.shape[1] != width or img.shape[0] != height:
        logger.warning(
            f"Image size {img.shape[1]}x{img.shape[0]} doesn't match expected {width}x{height}"
        )
        img = cv2.resize(img, (width, height), interpolation=cv2.INTER_NEAREST)

    # 1-bit pack: 8 pixels per byte, MSB first
    binary_data = np.packbits((img >= 128).reshape(-1)).tobytes()

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(binary_data)

    logger.success(f"Converted {input_path} -> {output_path}")
    logger.info(f"Output size: {len(binary_data)} bytes ({len(binary_data) / 1024:.1f} KB)")
    return True


def convert_bin_to_c_array(
    bin_file: str,
    array_name: str,
    output_path: str,
    bytes_per_line: int = 12,
    invert: bool = True,
) -> bool:
    """
    Convert binary EPD file to C header file with array.

    Args:
        bin_file: Path to input .bin file
        array_name: C array name (e.g., "image1_data")
        output_path: Path to output .h file
        bytes_per_line: Number of bytes per line in output
        invert: If True, invert all bytes (~byte) for ESPSlider compatibility

    Returns:
        True if successful, False otherwise
    """
    bin_path = Path(bin_file)
    if not bin_path.exists():
        logger.error(f"Binary file not found: {bin_file}")
        return False

    with open(bin_path, "rb") as f:
        data = f.read()

    data_size = len(data)

    guard_name = f"{array_name.upper().replace('.', '_').replace('-', '_')}_H"

    lines = []
    lines.append(f"#ifndef {guard_name}")
    lines.append(f"#define {guard_name}")
    lines.append("")
    lines.append("#include <stdint.h>")
    lines.append("#include <pgmspace.h>")
    lines.append("")
    lines.append(f"// Size: {data_size} bytes ({data_size / 1024:.1f} KB)")
    lines.append(f"// Source: {bin_path.name}")
    if invert:
        lines.append("// Data pre-inverted (~byte) for ESPSlider 7.5 V2")
    lines.append("// Stored in Flash using PROGMEM")
    lines.append(f"const uint8_t {array_name}[{data_size}] PROGMEM = {{")

    for i in range(0, data_size, bytes_per_line):
        chunk = data[i : i + bytes_per_line]
        hex_values = []
        for byte in chunk:
            value = (~byte) & 0xFF if invert else byte
            hex_values.append(f"0x{value:02X}")
        lines.append(f"    {', '.join(hex_values)},")

    lines.append("};")
    lines.append("")
    lines.append(f"#endif // {guard_name}")

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w") as f:
        f.write("\n".join(lines))

    logger.success(f"Generated {output_path}")
    return True


def generate_images_header(
    espslider_dir: str,
    image_count: int,
    image_size: int,
) -> bool:
    """
    Generate images.h with dynamic image count.

    Args:
        espslider_dir: Path to ESPSlider directory
        image_count: Number of images converted
        image_size: Size of each image in bytes

    Returns:
        True if successful, False otherwise
    """
    espslider_path = Path(espslider_dir)

    lines = []
    lines.append("#ifndef IMAGES_H")
    lines.append("#define IMAGES_H")
    lines.append("")
    lines.append("#include <stdint.h>")
    lines.append("#include <pgmspace.h>")
    lines.append("")
    lines.append(f"// Auto-generated: {image_count} images, {image_size} bytes each")
    lines.append(f"#define IMAGE_COUNT {image_count}")
    lines.append(f"#define IMAGE_SIZE {image_size}")
    lines.append("")

    # Include all individual header files
    for i in range(1, image_count + 1):
        lines.append(f'#include "image{i}.h"')
    lines.append("")

    # Image information structure
    lines.append("// Image information structure")
    lines.append("struct ImageInfo {")
    lines.append("    const uint8_t* data;")
    lines.append("    size_t size;")
    lines.append("};")
    lines.append("")

    # Image array - stored in Flash
    lines.append("// Image array - stored in Flash")
    lines.append("const ImageInfo images[IMAGE_COUNT] PROGMEM = {")
    for i in range(1, image_count + 1):
        lines.append(f"    {{image{i}_data, IMAGE_SIZE}},")
    lines.append("};")
    lines.append("")
    lines.append("#endif // IMAGES_H")

    output_file = espslider_path / "images.h"
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w") as f:
        f.write("\n".join(lines))

    logger.success(f"Generated {output_file}")
    return True


def get_dithered_files(directory: Path) -> list[Path]:
    """Get all _dithered image files in a directory."""
    return [
        f
        for f in directory.iterdir()
        if "_dithered" in f.name
        and f.suffix.lower() in {".png", ".jpg", ".jpeg", ".bmp"}
    ]


def convert_folder(
    input_dir: str,
    output_dir: str | None,
    width: int,
    height: int,
    espslider_dir: str | None = None,
) -> int:
    input_path = Path(input_dir)
    output_path = Path(output_dir) if output_dir else input_path
    espslider_path = Path(espslider_dir) if espslider_dir else None

    dithered_files = get_dithered_files(input_path)
    if not dithered_files:
        logger.warning(f"No _dithered files found in {input_path}")
        return 0

    count = 0
    image_size = 0
    for idx, img_file in enumerate(dithered_files, start=1):
        bin_file = output_path / f"{img_file.stem.replace('_dithered', '')}.bin"
        if convert_png_to_bin(str(img_file), str(bin_file), width, height):
            count += 1
            image_size = bin_file.stat().st_size if bin_file.exists() else 0
            if espslider_path:
                array_name = f"image{idx}_data"
                header_file = espslider_path / f"image{idx}.h"
                convert_bin_to_c_array(str(bin_file), array_name, str(header_file))

    if espslider_path and count > 0:
        generate_images_header(str(espslider_path), count, image_size)

    logger.success(f"Converted {count}/{len(dithered_files)} images in {input_path}")
    if espslider_path:
        logger.success(f"Generated {count} C header files in {espslider_path}")
    return count
