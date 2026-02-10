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
        except Exception as e:
            logger.error(f"Error saving {output_path}: {e}")
        return True
    else:
        logger.error(f"Failed to process {input_path}")
        return False


def get_image_files(directory):
    """Get all image files in a directory."""
    return [
        f for f in Path(directory).iterdir() if f.suffix.lower() in IMAGE_EXTENSIONS
    ]


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
    input_path_obj = Path(input_path)
    if input_path_obj.is_file():
        output_path = output_path or str(
            input_path_obj.with_name(
                f"{input_path_obj.stem}_crop{input_path_obj.suffix}"
            )
        )
        processed_img = _preprocess_image(input_path, TARGET_WIDTH, TARGET_HEIGHT)

        if processed_img is not None:
            try:
                cv2.imwrite(output_path, processed_img)
                logger.success(f"Successfully preprocessed and saved to {output_path}")
            except Exception as e:
                logger.error(f"Error saving preprocessed image to {output_path}: {e}")
        else:
            logger.error("Preprocessing failed.")

    else:
        input_dir = Path(input_path)

        image_files = [
            f
            for f in get_image_files(input_dir)
            if "_crop" not in f.name and "_dithered" not in f.name
        ]

        count = 0
        for img_file in image_files:
            output_file = img_file.with_name(f"{img_file.stem}_crop{img_file.suffix}")

            if process_single_image(str(img_file), str(output_file), _preprocess_image):
                count += 1

        logger.success(f"Processed {count} images in {input_dir}")


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
    type=click.Choice(["floyd_steinberg", "jarvis_judice_ninke"]),
    default="floyd_steinberg",
    help="Dithering algorithm to use",
)
def dither(input_path, output_path, method):
    """
    Applies dithering to an image or all _crop images in a directory.

    Use --method/-m to choose the dithering algorithm.
    """

    def dither_processor(img_path):
        img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            logger.error(f"Error: Cannot read image '{img_path}'.")
            return None
        return apply_dithering(img, method, COLOR_LEVELS)

    input_path_obj = Path(input_path)
    if input_path_obj.is_file():
        if output_path is None:
            output_path = str(
                input_path_obj.with_name(
                    input_path_obj.stem.replace("_crop", "_dithered")
                    + input_path_obj.suffix
                )
            )
        dithered_img = dither_processor(input_path)

        if dithered_img is not None:
            try:
                cv2.imwrite(output_path, dithered_img)
                logger.success(f"Successfully dithered and saved to {output_path}")
            except Exception as e:
                logger.error(f"Error saving dithered image to {output_path}: {e}")
        else:
            logger.error("Dithering failed.")

    else:
        input_dir = Path(input_path)

        crop_files = [f for f in input_dir.iterdir() if "_crop" in f.name]

        count = 0
        for img_file in crop_files:
            output_file = img_file.with_name(
                img_file.stem.replace("_crop", "_dithered") + img_file.suffix
            )

            if process_single_image(str(img_file), str(output_file), dither_processor):
                count += 1

        logger.success(f"Dithered {count} images in {input_dir}")


if __name__ == "__main__":
    cli()
