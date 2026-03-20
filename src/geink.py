from pathlib import Path

import click
import cv2
from loguru import logger

from .config import COLOR_LEVELS, TARGET_HEIGHT, TARGET_WIDTH
from .convert_toolkit import convert_bin_to_c_array, convert_folder, convert_png_to_bin
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
    input_path,
    output_path,
    processor_func,
    make_output_path,
    skip_patterns=None,
    require_patterns=None,
):
    """Run a command on a single file or all images in a directory.

    Args:
        input_path: Input file path or directory path
        output_path: Output file path (optional for files, None for directories)
        processor_func: Function that takes input path and returns processed image
        make_output_path: Function that takes input Path and returns output Path
        skip_patterns: List of patterns to skip (e.g., ['_crop', '_dithered'])
        require_patterns: List of patterns that files must match (e.g., ['_crop'])
    """
    input_obj = Path(input_path)
    skip_patterns = skip_patterns or []
    require_patterns = require_patterns or []

    if input_obj.is_file():
        if require_patterns and not any(p in input_obj.name for p in require_patterns):
            logger.warning(
                f"Skipping {input_obj.name}: does not match required patterns {require_patterns}"
            )
            return
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
            if require_patterns and not any(
                p in img_file.name for p in require_patterns
            ):
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
    type=click.Choice(
        ["floyd_steinberg", "jarvis_judice_ninke", "stucki", "binary_threshold"]
    ),
    default="jarvis_judice_ninke",
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

    _run_command(
        input_path, output_path, processor, make_output, require_patterns=["_crop"]
    )


@cli.command()
@click.argument("input_path", type=click.Path(exists=True))
@click.option("--rows", "-r", type=int, required=True, help="Number of rows")
@click.option("--cols", "-c", type=int, required=True, help="Number of columns")
def gridcut(input_path, rows, cols):
    """
    Cuts an image or all images in a directory into a grid.

    Each image is split into rows × cols tiles.
    Output files are saved in a subdirectory named after the image (without extension).
    Example: input.jpg -> input/r0_c0.png, input/r0_c1.png, etc.
    """
    input_obj = Path(input_path)

    if input_obj.is_file():
        success = _grid_cut_image(input_path, rows, cols)
        if not success:
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
@click.option(
    "--host",
    "-H",
    required=True,
    help="ESP8266 IP address (e.g., 192.168.10.211)",
)
@click.option(
    "--chunk-size",
    "-c",
    type=int,
    default=1400,
    help="Maximum chunk size in characters (default: 1400)",
)
def upload(bin_path, host, chunk_size):
    """
    Upload a .bin file to ESP8266 e-paper display.

    BIN_PATH: Path to the .bin file (800x480 monochrome, 1-bit per pixel)

    Example:
        geink upload image.bin --host 192.168.10.211
        geink upload image.bin -H 192.168.10.211
    """
    if not REQUESTS_AVAILABLE:
        logger.error(
            "requests library not installed. Install with: pip install requests"
        )
        return

    if not host:
        logger.error("Host is required. Use --host/-H option.")
        return

    from .config import TARGET_HEIGHT, TARGET_WIDTH

    TOTAL_BYTES = TARGET_WIDTH * TARGET_HEIGHT // 8  # 48000 bytes for 800x480

    def encode_byte(b: int) -> str:
        """Encode a single byte (0-255) into two characters 'a' to 'p' (0-15)."""
        low = b & 0x0F
        high = (b >> 4) & 0x0F
        return chr(ord("a") + low) + chr(ord("a") + high)

    def encode_data(data: bytes) -> str:
        """Encode binary data into string format expected by ESP8266."""
        return "".join(encode_byte(b) for b in data)

    def upload_chunk(chunk_host: str, chunk: str) -> bool:
        """Upload a single chunk of encoded data to the ESP8266."""
        url = f"http://{chunk_host}/upload"
        try:
            response = requests.post(url, data={"data": chunk}, timeout=30)
            if response.status_code == 200:
                logger.info(f"Uploaded chunk: {response.text.strip()}")
                return True
            else:
                logger.error(f"Error {response.status_code}: {response.text.strip()}")
                return False
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error: {e}")
            return False

    # Read binary file
    bin_file = Path(bin_path)
    with open(bin_file, "rb") as f:
        data = f.read()

    # Verify file size
    if len(data) != TOTAL_BYTES:
        logger.warning(f"Expected {TOTAL_BYTES} bytes, got {len(data)} bytes")
        logger.warning("Make sure the image is 800x480 monochrome (1-bit per pixel)")

    logger.info(f"Loaded {len(data)} bytes from {bin_file.name}")

    # Encode entire data
    logger.info("Encoding data...")
    encoded = encode_data(data)
    total_chars = len(encoded)
    logger.info(f"Encoded to {total_chars} characters")

    # Initialize display
    init_url = f"http://{host}/init"
    try:
        logger.info("Initializing display...")
        response = requests.get(init_url, timeout=10)
        if response.status_code == 200:
            logger.success(f"Init: {response.text.strip()}")
        else:
            logger.error(f"Init failed: {response.status_code}")
            return
    except requests.exceptions.RequestException as e:
        logger.error(f"Init error: {e}")
        return

    # Split into chunks
    chunk_chars = (chunk_size // 2) * 2  # ensure even number
    if chunk_chars <= 8:
        logger.error(f"Chunk size too small: {chunk_chars}")
        return

    chunks = []
    pos = 0
    while pos < total_chars:
        remaining = total_chars - pos
        chunk_size_actual = min(chunk_chars - 8, remaining)
        if chunk_size_actual <= 0:
            chunk_size_actual = remaining
        if chunk_size_actual % 2 != 0:
            chunk_size_actual -= 1
            if chunk_size_actual <= 0:
                break
        chunk = encoded[pos : pos + chunk_size_actual]
        chunks.append(chunk)
        pos += chunk_size_actual

    logger.info(f"Splitting into {len(chunks)} chunks...")

    # Upload each chunk
    success_count = 0
    for i, chunk in enumerate(chunks, 1):
        length_chars = len(chunk)
        len_chars = (
            chr(ord("a") + (length_chars & 0x0F))
            + chr(ord("a") + ((length_chars >> 4) & 0x0F))
            + chr(ord("a") + ((length_chars >> 8) & 0x0F))
            + chr(ord("a") + ((length_chars >> 12) & 0x0F))
        )
        full_chunk = chunk + len_chars + "LOAD"

        logger.info(f"Uploading chunk {i}/{len(chunks)}...")
        if upload_chunk(host, full_chunk):
            success_count += 1
        else:
            logger.error("Upload failed. Stopping.")
            return

    if success_count == len(chunks):
        # Trigger display refresh
        show_url = f"http://{host}/show"
        try:
            logger.info("Refreshing display...")
            response = requests.get(show_url, timeout=30)
            if response.status_code == 200:
                logger.success(f"Display refreshed: {response.text.strip()}")
                logger.success("Done!")
            else:
                logger.error(f"Show failed: {response.status_code}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Show error: {e}")
    else:
        logger.error(f"Only {success_count}/{len(chunks)} chunks succeeded")


if __name__ == "__main__":
    cli()
