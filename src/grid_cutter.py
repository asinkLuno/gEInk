from pathlib import Path

import cv2
import numpy as np
from loguru import logger


def grid_cut(image: np.ndarray | str | Path, rows: int, cols: int) -> list[np.ndarray]:
    """
    将图片切割成 rows × cols 的网格。

    Args:
        image: numpy array 或图片路径
        rows: 行数
        cols: 列数

    Returns:
        list[numpy.ndarray]: 切割后的子图片，按行优先顺序排列

    Raises:
        ValueError: 如果 rows 或 cols 小于 1
        cv2.error: 如果图片读取失败（由 OpenCV 抛出）
    """
    if rows < 1 or cols < 1:
        raise ValueError("rows and cols must be >= 1")

    if isinstance(image, (str, Path)):
        img = cv2.imread(str(image))
        if img is None:
            raise cv2.error(f"Failed to read image: {image}")
    else:
        img = image

    h, w = img.shape[:2]
    tile_h: int = h // rows
    tile_w: int = w // cols

    tiles: list[np.ndarray] = []
    for r in range(rows):
        for c in range(cols):
            y_start = r * tile_h
            y_end = (r + 1) * tile_h if r < (rows - 1) else h
            x_start = c * tile_w
            x_end = (c + 1) * tile_w if c < (cols - 1) else w

            tile = img[int(y_start) : int(y_end), int(x_start) : int(x_end)]
            tiles.append(tile)

    return tiles


def grid_cut_image(img_path: str, rows: int, cols: int) -> bool:
    """
    切割单张图片并保存到源目录下无扩展名的子文件夹。

    Args:
        img_path: 图片路径
        rows: 行数
        cols: 列数

    Returns:
        bool: 成功返回 True
    """
    img = cv2.imread(img_path)
    if img is None:
        logger.error(f"无法读取图片: {img_path}")
        return False

    tiles = grid_cut(img, rows, cols)
    input_path = Path(img_path)

    output_dir = input_path.parent / input_path.stem
    output_dir.mkdir(parents=True, exist_ok=True)

    suffix = input_path.suffix

    for idx, tile in enumerate(tiles):
        row = idx // cols
        col = idx % cols
        output_file = output_dir / f"r{row}_c{col}{suffix}"
        _ = cv2.imwrite(str(output_file), tile)

    logger.success(f"切割完成: {img_path} -> {len(tiles)} 个子图 -> {output_dir}")
    return True
