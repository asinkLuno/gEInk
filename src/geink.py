import os

import click
from loguru import logger
from PIL import Image

# Configure loguru to write to stdout for Click CLI testing
logger.remove()
logger.add(lambda msg: print(msg, end=""), format="{message}")

from .config import COLOR_LEVELS, TARGET_HEIGHT, TARGET_WIDTH
from .dithering_toolkit import apply_dithering
from .preprocess_toolkit import _preprocess_image

# Supported image extensions
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff", ".webp"}


def process_single_image(input_path, output_path, processor_func):
    """Process a single image file."""
    logger.info(f"Processing {input_path} -> {output_path}")
    processed_img = processor_func(input_path)

    if processed_img:
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            processed_img.save(output_path)
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
        f
        for f in os.listdir(directory)
        if os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS
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
    if os.path.isfile(input_path):
        # Single file mode
        if output_path is None:
            base, ext = os.path.splitext(input_path)
            output_path = f"{base}_eink{ext}"
        processed_img = _preprocess_image(input_path, TARGET_WIDTH, TARGET_HEIGHT)

        if processed_img:
            try:
                processed_img.save(output_path)
                logger.success(f"Successfully preprocessed and saved to {output_path}")
            except Exception as e:
                logger.error(f"Error saving preprocessed image to {output_path}: {e}")
        else:
            logger.error("Preprocessing failed.")

    else:
        # Directory mode
        input_dir = input_path
        output_dir = output_path or f"{input_path}_eink"
        os.makedirs(output_dir, exist_ok=True)

        image_files = get_image_files(input_dir)

        count = 0
        for img_file in image_files:
            input_file = os.path.join(input_dir, img_file)
            base_name = os.path.splitext(img_file)[0]
            output_file = os.path.join(output_dir, f"{base_name}_eink.png")

            if process_single_image(input_file, output_file, _preprocess_image):
                count += 1

        logger.success(f"Processed {count} images in {input_dir} -> {output_dir}")


@cli.command()
@click.argument("input_path", type=click.Path(exists=True))
@click.argument("output_path", type=click.Path(), required=False)
def dither(input_path, output_path):
    """
    Applies dithering to an image or all _eink images in a directory.
    """

    def dither_processor(img_path):
        try:
            input_img = Image.open(img_path).convert("L")
        except FileNotFoundError:
            logger.error(f"Error: Input image '{img_path}' not found.")
            return None
        except Exception as e:
            logger.error(f"Error opening or converting image '{img_path}': {e}")
            return None
        return apply_dithering(input_img, "floyd_steinberg", COLOR_LEVELS)

    if os.path.isfile(input_path):
        # Single file mode
        if output_path is None:
            base, ext = os.path.splitext(input_path)
            output_path = f"{base}_eink_dither{ext}"
        dithered_img = dither_processor(input_path)

        if dithered_img:
            try:
                dithered_img.save(output_path)
                logger.success(f"Successfully dithered and saved to {output_path}")
            except Exception as e:
                logger.error(f"Error saving dithered image to {output_path}: {e}")
        else:
            logger.error("Dithering failed.")

    else:
        # Directory mode
        input_dir = input_path
        output_dir = output_path or f"{input_path}_eink_dither"
        os.makedirs(output_dir, exist_ok=True)

        eink_files = [f for f in get_image_files(input_dir) if "_eink" in f]

        count = 0
        for img_file in eink_files:
            input_file = os.path.join(input_dir, img_file)
            base_name = os.path.splitext(img_file)[0]
            output_file = os.path.join(output_dir, f"{base_name}_dither.png")

            if process_single_image(input_file, output_file, dither_processor):
                count += 1

        logger.success(f"Dithered {count} images in {input_dir} -> {output_dir}")


if __name__ == "__main__":
    cli()
