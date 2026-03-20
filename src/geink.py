from pathlib import Path

import click
import cv2
import numpy as np
from loguru import logger

from .config import TARGET_HEIGHT, TARGET_WIDTH
from .dithering_toolkit import apply_dithering
from .grid_cutter import _grid_cut_image
from .preprocess_toolkit import _preprocess_image

# Configure loguru to write to stdout for Click CLI testing
logger.remove()
logger.add(lambda msg: print(msg, end=""), format="{message}")

# Try to import requests, but handle gracefully if not installed
try:
    import requests

    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

# Supported image extensions
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff", ".webp"}


def _process_image(img_path, bin_path, preview_path, width, height, method):
    """Preprocess → grayscale → dither → save preview + .bin"""
    bgr = _preprocess_image(img_path, width, height)
    if bgr is None:
        return False

    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    dithered = apply_dithering(gray, method)

    Path(bin_path).parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(preview_path), dithered)
    Path(bin_path).write_bytes(np.packbits((dithered >= 128).reshape(-1)).tobytes())

    logger.success(f"bin: {bin_path}")
    logger.success(f"preview: {preview_path}")
    return True


@click.group()
def cli():
    """Geink CLI for e-paper image processing."""


@cli.command()
@click.argument("input_path", type=click.Path(exists=True))
@click.argument("output_path", type=click.Path(), required=False)
@click.option("--width", "-w", type=int, default=TARGET_WIDTH, help="Target width")
@click.option("--height", "-h", type=int, default=TARGET_HEIGHT, help="Target height")
@click.option(
    "--method",
    "-m",
    type=click.Choice(["atkinson", "binary_threshold"]),
    default="atkinson",
    help="Dithering algorithm",
)
def process(input_path, output_path, width, height, method):
    """
    Process image(s) to EPD binary format.

    Outputs a .bin file and a _preview.png alongside it.

    Examples:
        geink process photo.jpg
        geink process photo.jpg output.bin
        geink process ./photos/
    """
    input_obj = Path(input_path)

    if input_obj.is_file():
        bin_out = Path(output_path) if output_path else input_obj.with_suffix(".bin")
        preview_out = bin_out.with_name(bin_out.stem + "_preview.png")
        if not _process_image(input_path, bin_out, preview_out, width, height, method):
            logger.error("Processing failed.")
    else:
        count = 0
        for img_file in sorted(input_obj.iterdir()):
            if img_file.suffix.lower() not in IMAGE_EXTENSIONS:
                continue
            if "_preview" in img_file.name:
                continue
            bin_out = img_file.with_suffix(".bin")
            preview_out = img_file.with_name(img_file.stem + "_preview.png")
            if _process_image(str(img_file), bin_out, preview_out, width, height, method):
                count += 1
        logger.success(f"Processed {count} images in {input_obj}")


@cli.command()
@click.argument("input_path", type=click.Path(exists=True))
@click.option("--rows", "-r", type=int, required=True, help="Number of rows")
@click.option("--cols", "-c", type=int, required=True, help="Number of columns")
def gridcut(input_path, rows, cols):
    """
    Cut an image or directory of images into a grid.

    Output tiles are saved in a subdirectory named after the image.
    Example: input.jpg -> input/r0_c0.png, input/r0_c1.png, ...
    """
    input_obj = Path(input_path)

    if input_obj.is_file():
        if not _grid_cut_image(input_path, rows, cols):
            logger.error("Grid cut failed.")
    else:
        count = 0
        for img_file in input_obj.iterdir():
            if img_file.suffix.lower() not in IMAGE_EXTENSIONS:
                continue
            if _grid_cut_image(str(img_file), rows, cols):
                count += 1
        logger.success(f"Grid cut {count} images")


@cli.command()
@click.argument("bin_path", type=click.Path(exists=True))
@click.option("--host", "-H", required=True, help="ESPSlider IP address")
def upload(bin_path, host):
    """
    Upload a .bin file to ESPSlider over WiFi.

    Example:
        geink upload image.bin --host 192.168.1.100
    """
    if not REQUESTS_AVAILABLE:
        logger.error("requests not installed: pip install requests")
        return

    bin_file = Path(bin_path)
    data = bin_file.read_bytes()
    logger.info(f"Uploading {bin_file.name} ({len(data)} bytes) to {host}...")

    try:
        response = requests.post(
            f"http://{host}/upload",
            files={"file": (bin_file.name, data, "application/octet-stream")},
            timeout=30,
        )
        if response.status_code == 200:
            logger.success(f"Uploaded {bin_file.name}")
        else:
            logger.error(f"Upload failed: {response.status_code} {response.text.strip()}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error: {e}")


if __name__ == "__main__":
    cli()
