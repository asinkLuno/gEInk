import click
from loguru import logger
from PIL import Image

# Configure loguru to write to stdout for Click CLI testing
logger.remove()
logger.add(lambda msg: print(msg, end=""), format="{message}")

from .config import COLOR_LEVELS, TARGET_HEIGHT, TARGET_WIDTH
from .dithering_toolkit import apply_dithering
from .preprocess_toolkit import _preprocess_image


@click.group()
def cli():
    """
    Geink CLI for e-paper image processing.
    """


@cli.command()
@click.argument("input_path", type=click.Path(exists=True, dir_okay=False))
@click.argument("output_path", type=click.Path(dir_okay=False))
def preprocess(input_path, output_path):
    """
    Preprocesses an image (grayscale, rotation, padding, resizing) and saves it.
    """
    logger.info(f"Starting preprocessing for {input_path} to {output_path}")
    processed_img = _preprocess_image(input_path, TARGET_WIDTH, TARGET_HEIGHT)

    if processed_img:
        try:
            processed_img.save(output_path)
            logger.success(f"Successfully preprocessed and saved to {output_path}")
        except Exception as e:
            logger.error(f"Error saving preprocessed image to {output_path}: {e}")
    else:
        logger.error("Preprocessing failed.")


@cli.command()
@click.argument("input_path", type=click.Path(exists=True, dir_okay=False))
@click.argument("output_path", type=click.Path(dir_okay=False))
def dither(input_path, output_path):
    """
    Applies dithering to a grayscale image and saves the multi-level output.
    """
    logger.info(f"Starting dithering for {input_path} to {output_path}")
    try:
        input_img = Image.open(input_path).convert("L")  # Ensure input is grayscale
    except FileNotFoundError:
        logger.error(f"Error: Input image '{input_path}' not found.")
        return
    except Exception as e:
        logger.error(f"Error opening or converting image '{input_path}': {e}")
        return

    dithered_img = apply_dithering(input_img, "floyd_steinberg", COLOR_LEVELS)

    if dithered_img:
        try:
            dithered_img.save(output_path)
            logger.success(f"Successfully dithered and saved to {output_path}")
        except Exception as e:
            logger.error(f"Error saving dithered image to {output_path}: {e}")
    else:
        logger.error("Dithering failed.")


if __name__ == "__main__":
    cli()
