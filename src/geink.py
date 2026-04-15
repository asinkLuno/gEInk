from pathlib import Path

import click
import cv2
import numpy as np
import requests
from loguru import logger

from .ascii_art_toolkit import render_ascii_art
from .config import IMAGE_EXTENSIONS, TARGET_HEIGHT, TARGET_WIDTH
from .dithering_toolkit import apply_dithering
from .edge_cutter import edge_cut_cmd
from .grid_cutter import grid_cut_image
from .pointillism_toolkit import (
    DEFAULT_PALETTE,
    color_atkinson_dithering,
    create_color_blocks,
    load_brush_textures,
    render_color_pointillism,
)
from .preprocess_toolkit import preprocess_image

# Configure loguru to write to stdout for Click CLI testing
logger.remove()
_ = logger.add(lambda msg: print(msg, end=""), format="{message}")


def _process_image(
    img_path: str,
    bin_path: str | Path,
    preview_path: str | Path,
    width: int,
    height: int,
    method: str,
) -> bool:
    """Preprocess → grayscale → dither → save preview + .bin"""
    bgr = preprocess_image(img_path, width, height)
    if bgr is None:
        return False

    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    dithered = apply_dithering(gray, method)

    Path(bin_path).parent.mkdir(parents=True, exist_ok=True)
    _ = cv2.imwrite(str(preview_path), dithered)
    _ = Path(bin_path).write_bytes(np.packbits((dithered >= 128).reshape(-1)).tobytes())

    logger.success(f"bin: {bin_path}")
    logger.success(f"preview: {preview_path}")
    return True


@click.group()
def cli() -> None:
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
def process(
    input_path: str,
    output_path: str | None,
    width: int,
    height: int,
    method: str,
) -> None:
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
            if _process_image(
                str(img_file), bin_out, preview_out, width, height, method
            ):
                count += 1
        logger.success(f"Processed {count} images in {input_obj}")


@cli.command()
@click.argument("input_path", type=click.Path(exists=True))
@click.option("--rows", "-r", type=int, required=True, help="Number of rows")
@click.option("--cols", "-c", type=int, required=True, help="Number of columns")
def gridcut(input_path: str, rows: int, cols: int) -> None:
    """
    Cut an image or directory of images into a grid.

    Output tiles are saved in a subdirectory named after the image.
    Example: input.jpg -> input/r0_c0.png, input/r0_c1.png, ...
    """
    input_obj = Path(input_path)

    if input_obj.is_file():
        if not grid_cut_image(input_path, rows, cols):
            logger.error("Grid cut failed.")
    else:
        count = 0
        for img_file in input_obj.iterdir():
            if img_file.suffix.lower() not in IMAGE_EXTENSIONS:
                continue
            if grid_cut_image(str(img_file), rows, cols):
                count += 1
        logger.success(f"Grid cut {count} images")


@cli.command()
@click.argument("input_path", type=click.Path(exists=True))
@click.argument("output_path", type=click.Path(), required=False)
@click.option(
    "--spatial-rad",
    type=int,
    default=15,
    help="Mean-shift spatial radius for color blocking",
)
@click.option(
    "--color-rad",
    type=int,
    default=40,
    help="Mean-shift color radius for color blocking",
)
@click.option(
    "--scale", "-s", type=int, default=5, help="Canvas upscale factor (grid spacing)"
)
@click.option(
    "--dot-radius", "-r", type=int, default=4, help="Base dot radius in pixels"
)
@click.option(
    "--jitter", "-j", type=int, default=2, help="Max random offset per dot in pixels"
)
@click.option(
    "--max-dim", type=int, default=600, help="Resize input so longest side ≤ this value"
)
@click.option(
    "--alpha",
    "-a",
    "pipeline_alpha",
    type=float,
    default=0.5,
    help="Watercolor dot opacity (0=transparent, 1=opaque)",
)
def pointillize(
    input_path: str,
    output_path: str | None,
    spatial_rad: int,
    color_rad: int,
    scale: int,
    dot_radius: int,
    jitter: int,
    max_dim: int,
    pipeline_alpha: float,
) -> None:
    """
    Convert image(s) to color pointillism art.

    Pipeline: mean-shift color blocking → 7-color Atkinson dithering → overlapping dot rendering.

    Examples:
        geink pointillize photo.jpg
        geink pointillize photo.jpg out.png --scale 6 --dot-radius 5
    """
    input_obj = Path(input_path)

    # 在此处加载纹理，避免在循环中重复加载
    brush_textures = load_brush_textures("oil_paint_texture")

    def process_one(img_file: Path, out_file: Path) -> bool:
        img = cv2.imread(str(img_file))
        if img is None:
            logger.error(f"Cannot read {img_file}")
            return False

        h, w = img.shape[:2]
        if max(h, w) > max_dim:
            factor = float(max_dim / max(h, w))
            img = cv2.resize(
                img,
                (int(w * factor), int(h * factor)),
                interpolation=cv2.INTER_AREA,
            )

        # 创建同名目录保存中间步骤和成品
        out_dir = img_file.parent / img_file.stem
        out_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(
            f"Pointillizing {img_file.name} {img.shape[1]}x{img.shape[0]} → ×{scale}..."
        )
        
        # 步骤 1：色块化
        blocked = create_color_blocks(img, spatial_rad=spatial_rad, color_rad=color_rad)
        cv2.imwrite(str(out_dir / f"{img_file.stem}_blocked.png"), blocked)
        
        # 步骤 2：抖动
        dithered = color_atkinson_dithering(blocked, DEFAULT_PALETTE)
        cv2.imwrite(str(out_dir / f"{img_file.stem}_dithered.png"), dithered)
        
        # 步骤 3：点彩渲染
        art = render_color_pointillism(
            dithered,
            scale=scale,
            base_radius=dot_radius,
            jitter=jitter,
            alpha=pipeline_alpha,
            brush_textures=brush_textures,
        )

        # 最终输出也保存在同名目录中
        final_out = out_dir / f"{img_file.stem}_pointillism.png"
        _ = cv2.imwrite(str(final_out), art)
        
        logger.success(f"Intermediate steps saved to: {out_dir}/")
        logger.success(f"Final art saved to: {final_out}")
        return True

    if input_obj.is_file():
        out = (
            Path(output_path)
            if output_path
            else input_obj.with_name(input_obj.stem + "_pointillism.png")
        )
        _ = process_one(input_obj, out)
    else:
        count = 0
        for img_file in sorted(input_obj.iterdir()):
            if img_file.suffix.lower() not in IMAGE_EXTENSIONS:
                continue
            if "_pointillism" in img_file.name:
                continue
            out = img_file.with_name(img_file.stem + "_pointillism.png")
            if process_one(img_file, out):
                count += 1
        logger.success(f"Generated {count} art pieces in {input_obj}")


@cli.command("ascii-art")
@click.argument("input_path", type=click.Path(exists=True))
@click.argument("output_path", type=click.Path(), required=False)
@click.option(
    "--cell-height", "-c", type=int, default=12, help="Font cell height in pixels"
)
@click.option(
    "--input-height",
    "-i",
    type=int,
    default=400,
    help="Downscale input to this height before processing",
)
@click.option(
    "--grabcut",
    is_flag=True,
    default=False,
    help="GrabCut foreground extraction before edge detection",
)
def ascii_art(
    input_path: str,
    output_path: str | None,
    cell_height: int,
    input_height: int,
    grabcut: bool,
) -> None:
    """
    Convert image to ASCII art using Sarasa Gothic font.

    Edges are drawn with - | / \\ _ characters based on gradient direction.
    Use --grabcut to strip background before edge detection.

    Examples:
        geink ascii-art photo.jpg
        geink ascii-art photo.jpg out.png --grabcut
    """
    img = cv2.imread(input_path)
    if img is None:
        logger.error(f"Cannot read {input_path}")
        return

    logger.info(
        f"Rendering ASCII art for {Path(input_path).name} (cell_height={cell_height}, grabcut={grabcut})..."
    )
    result = render_ascii_art(
        img, cell_height=cell_height, input_height=input_height, grabcut=grabcut
    )

    out = (
        Path(output_path)
        if output_path
        else Path(input_path).with_name(Path(input_path).stem + "_ascii.png")
    )
    _ = cv2.imwrite(str(out), result)
    logger.success(f"ASCII art saved to: {out}")


@cli.command()
@click.argument("bin_path", type=click.Path(exists=True))
@click.option("--host", "-H", required=True, help="ESPSlider IP address")
def upload(bin_path: str, host: str) -> None:
    """
    Upload a .bin file to ESPSlider over WiFi.

    Example:
        geink upload image.bin --host 192.168.1.100
    """
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
            logger.error(
                f"Upload failed: {response.status_code} {response.text.strip()}"
            )
    except Exception as e:
        logger.error(f"Network error: {e}")


# Register commands from sub-modules
cli.add_command(edge_cut_cmd)


if __name__ == "__main__":
    cli()
