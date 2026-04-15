from pathlib import Path

import click
import cv2
import numpy as np
from loguru import logger

from .config import IMAGE_EXTENSIONS


def extract_elements(img_path: str, min_area: int = 100) -> bool:
    """
    使用边缘检测/Alpha通道提取独立元素并保存。
    """
    img = cv2.imread(img_path, cv2.IMREAD_UNCHANGED)
    if img is None:
        logger.error(f"无法读取图片: {img_path}")
        return False

    # 如果有Alpha通道，直接用Alpha作为Mask
    if img.shape[2] == 4:
        alpha = img[:, :, 3]
        _, mask = cv2.threshold(alpha, 127, 255, cv2.THRESH_BINARY)
    else:
        # 如果没有Alpha，转灰度并用Canny/Otsu
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, mask = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY_INV)

    # 寻找轮廓
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    input_path = Path(img_path)
    output_dir = input_path.parent / f"{input_path.stem}_elements"
    output_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for i, cnt in enumerate(contours):
        area = cv2.contourArea(cnt)
        if area < min_area:
            continue

        x, y, w, h = cv2.boundingRect(cnt)
        # 提取元素
        element = img[y : y + h, x : x + w]

        # 保存
        out_file = output_dir / f"element_{count:03d}.png"
        _ = cv2.imwrite(str(out_file), element)
        count += 1

    logger.success(f"提取完成: {img_path} -> {count} 个元素 -> {output_dir}")
    return True


@click.command("edge-cut")
@click.argument("input_path", type=click.Path(exists=True))
@click.option(
    "--min-area", type=int, default=100, help="Minimum area to consider as an element"
)
def edge_cut_cmd(input_path: str, min_area: int) -> None:
    """
    Extract independent elements from an image using edge/alpha detection.
    """
    input_obj = Path(input_path)

    if input_obj.is_file():
        if not extract_elements(input_path, min_area):
            logger.error("Edge cut failed.")
    else:
        count = 0
        for img_file in sorted(input_obj.iterdir()):
            if img_file.suffix.lower() not in IMAGE_EXTENSIONS:
                continue
            if extract_elements(str(img_file), min_area):
                count += 1
        logger.success(f"Edge cut {count} images in {input_obj}")
