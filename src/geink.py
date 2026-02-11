from pathlib import Path

import click
import cv2
from loguru import logger

# Configure loguru to write to stdout for Click CLI testing
logger.remove()
logger.add(lambda msg: print(msg, end=""), format="{message}")

from .config import COLOR_LEVELS, TARGET_HEIGHT, TARGET_WIDTH
from .convert_toolkit import (convert_bin_to_c_array, convert_folder,
                              convert_png_to_bin)
from .dithering_toolkit import apply_dithering
from .preprocess_toolkit import _preprocess_image

# Supported image extensions
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff", ".webp"}


def process_single_image(input_path, output_path, processor_func):
    """Process a single image file."""
    logger.info(f"Processing {input_path} -> {output_path}")
    processed_img = processor_func(input_path)

    if processed_img is not None:
        try:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(output_path, processed_img)
            logger.success(f"Saved: {output_path}")
            return True
        except Exception as e:
            logger.error(f"Error saving {output_path}: {e}")
    else:
        logger.error(f"Failed to process {input_path}")
    return False


def _run_command(
    input_path, output_path, processor_func, make_output_path, skip_patterns=None
):
    """Run a command on a single file or all images in a directory.

    Args:
        input_path: Input file path or directory path
        output_path: Output file path (optional for files, None for directories)
        processor_func: Function that takes input path and returns processed image
        make_output_path: Function that takes input Path and returns output Path
        skip_patterns: List of patterns to skip (e.g., ['_crop', '_dithered'])
    """
    input_obj = Path(input_path)
    skip_patterns = skip_patterns or []

    if input_obj.is_file():
        output = output_path or str(make_output_path(input_obj))
        success = process_single_image(input_path, output, processor_func)
        if not success:
            logger.error("Processing failed.")
    else:
        input_dir = input_obj
        count = 0
        for img_file in input_dir.iterdir():
            if img_file.suffix.lower() not in IMAGE_EXTENSIONS:
                continue
            if any(p in img_file.name for p in skip_patterns):
                continue
            output = str(make_output_path(img_file))
            if process_single_image(str(img_file), output, processor_func):
                count += 1
        logger.success(f"Processed {count} images in {input_dir}")


@click.group()
def cli():
    """
    Geink CLI for e-paper image processing.
    """


@cli.command()
@click.argument("input_path", type=click.Path(exists=True))
@click.argument("output_path", type=click.Path(), required=False)
def preprocess(input_path, output_path):
    """
    Preprocesses an image or all images in a directory.
    """

    def make_output(input_path_obj):
        return input_path_obj.with_name(
            f"{input_path_obj.stem}_crop{input_path_obj.suffix}"
        )

    def processor(img_path):
        return _preprocess_image(img_path, TARGET_WIDTH, TARGET_HEIGHT)

    _run_command(
        input_path,
        output_path,
        processor,
        make_output,
        skip_patterns=["_crop", "_dithered"],
    )


@cli.command()
@click.argument("input_path", type=click.Path(exists=True))
@click.argument("output_path", type=click.Path(), required=False)
@click.option("--width", "-w", type=int, default=TARGET_WIDTH, help="Target width")
@click.option("--height", "-h", type=int, default=TARGET_HEIGHT, help="Target height")
@click.option(
    "--color-levels",
    "-c",
    type=int,
    default=COLOR_LEVELS,
    help="Number of color levels (must be power of 2)",
)
@click.option(
    "--espslider-dir",
    type=click.Path(),
    default="ESPSlider/",
    help="ESPSlider directory for .h output (default: ESPSlider/)",
)
def convert(input_path, output_path, width, height, color_levels, espslider_dir):
    """
    Converts _dithered images to EPD binary format (.bin).

    Accepts a single image file or a directory of _dithered images.
    Output .bin files are saved in the same directory by default.
    C header files are automatically generated in ESPSlider/ directory.
    """
    input_path_obj = Path(input_path)

    if input_path_obj.is_file():
        if output_path is None:
            output_path = str(
                input_path_obj.with_name(
                    input_path_obj.stem.replace("_dithered", "") + ".bin"
                )
            )

        if convert_png_to_bin(input_path, output_path, width, height, color_levels):
            logger.success(f"Successfully converted to {output_path}")
            bin_path = Path(output_path)
            array_name = f"{bin_path.stem}_data"
            header_path = Path(espslider_dir) / f"{bin_path.stem}.h"
            convert_bin_to_c_array(output_path, array_name, str(header_path))
        else:
            logger.error("Conversion failed.")

    else:
        count = convert_folder(
            input_path,
            output_path,
            width,
            height,
            color_levels,
            espslider_dir=espslider_dir,
        )
        if count == 0:
            logger.error("No files converted.")


@cli.command()
@click.argument("input_path", type=click.Path(exists=True))
@click.argument("output_path", type=click.Path(), required=False)
@click.option(
    "--method",
    "-m",
    type=click.Choice(["floyd_steinberg", "jarvis_judice_ninke", "stucki"]),
    default="floyd_steinberg",
    help="Dithering algorithm to use",
)
def dither(input_path, output_path, method):
    """
    Applies dithering to an image or all _crop images in a directory.

    Use --method/-m to choose the dithering algorithm.
    """

    def make_output(input_path_obj):
        return input_path_obj.with_name(
            input_path_obj.stem.replace("_crop", "_dithered") + input_path_obj.suffix
        )

    def processor(img_path):
        img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            logger.error(f"Error: Cannot read image '{img_path}'.")
            return None
        return apply_dithering(img, method, COLOR_LEVELS)

    _run_command(input_path, output_path, processor, make_output)


if __name__ == "__main__":
    cli()
