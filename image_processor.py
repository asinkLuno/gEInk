#!/usr/bin/env python3
"""
图片预处理工具：
1. 检测物体边缘并裁切
2. Padding到5:3比例
3. Padding颜色以背景色为准
4. Resize到480*800或800*480
"""

import os
from collections import Counter
from pathlib import Path
from typing import Tuple

import click
import cv2
import numpy as np
from loguru import logger

# 支持的图片格式
SUPPORTED_FORMATS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif"}

# 屏幕尺寸常量
SCREEN_SHORT = 480
SCREEN_LONG = 800


def get_image_files(path: str) -> list[str]:
    """获取路径下的所有图片文件"""
    p = Path(path)
    if p.is_file():
        return [str(p)]
    elif p.is_dir():
        return sorted(
            [str(f) for f in p.iterdir() if f.suffix.lower() in SUPPORTED_FORMATS]
        )
    return []


def process_directory(
    input_dir: str,
    output_dir: str | None = None,
    apply_dither: bool = False,
    dither_shades: int = 16,
):
    """处理目录下所有图片"""
    image_files = get_image_files(input_dir)
    total = len(image_files)

    if total == 0:
        logger.warning(f"在 {input_dir} 中未找到图片文件")
        return

    logger.info(f"找到 {total} 张图片，开始处理...\n")

    for idx, input_path_file in enumerate(image_files, 1):
        filename = os.path.basename(input_path_file)
        base, ext = os.path.splitext(filename)

        if output_dir:
            output_folder = Path(output_dir)
            output_folder.mkdir(parents=True, exist_ok=True)
            output_path = output_folder / f"{base}eink{ext}"
        else:
            output_path = Path(input_dir) / f"{base}eink{ext}"

        logger.info(f"[{idx}/{total}] 处理: {filename}")
        process_image(
            input_path_file,
            str(output_path),
            apply_dither=apply_dither,
            dither_shades=dither_shades,
        )
        logger.info("")


def get_background_color(img: np.ndarray) -> Tuple[int, int, int]:
    """
    获取图片的背景色（取四个角的颜色，取众数），输入为OpenCV图片。
    Args:
        img: OpenCV图片 (numpy.ndarray)
    Returns:
        背景色 (B, G, R)
    """
    height, width, _ = img.shape

    corners = [
        tuple(img[0, 0].tolist()),
        tuple(img[0, width - 1].tolist()),
        tuple(img[height - 1, 0].tolist()),
        tuple(img[height - 1, width - 1].tolist()),
    ]
    return Counter(corners).most_common(1)[0][0]


def is_solid_background(img: np.ndarray, tolerance: int = 30) -> bool:
    """
    检查图片背景是否是纯色。
    通过检查图片边缘像素的颜色方差来判断。
    Args:
        img: OpenCV图片 (numpy.ndarray)
        tolerance: 颜色容差，值越大，对“纯色”的定义越宽松
    Returns:
        如果背景是纯色，则返回True，否则返回False
    """
    height, width, _ = img.shape

    # 提取边缘像素
    border_pixels = []
    # 上下边缘
    for x in range(width):
        border_pixels.append(img[0, x])
        border_pixels.append(img[height - 1, x])
    # 左右边缘
    for y in range(height):
        border_pixels.append(img[y, 0])
        border_pixels.append(img[y, width - 1])

    # 将像素列表转换为Numpy数组
    border_pixels = np.array(border_pixels)

    if len(border_pixels) == 0:
        return True  # 没有像素，视为纯色

    # 计算颜色方差
    # 计算每个通道的平均值
    avg_color = np.mean(border_pixels, axis=0)

    # 计算每个通道与平均值的差的平方，然后求和，再求平均值
    # 这实际上是计算每个通道的方差，然后将这些方差相加
    color_variance = np.mean(np.sum((border_pixels - avg_color) ** 2, axis=1))

    # 判断是否为纯色
    # 如果颜色方差小于容差，则认为是纯色背景
    return color_variance < tolerance


def detect_object_bounds(
    img: np.ndarray, threshold: int = 240
) -> Tuple[int, int, int, int]:
    """
    检测物体边界，输入为OpenCV图片。
    Args:
        img: OpenCV图片 (numpy.ndarray)
        threshold: 阈值，用于判断像素是否为背景
    Returns:
        物体的边界 (left, right, top, bottom)
    """
    height, width, _ = img.shape
    bg_color = get_background_color(img)

    left, right, top, bottom = width, 0, height, 0

    for y in range(height):
        for x in range(width):
            pixel = img[y, x]  # BGR
            # Calculate Euclidean distance in BGR space
            distance = np.sqrt(np.sum((pixel - np.array(bg_color)) ** 2))

            if distance >= (
                255 - threshold
            ):  # Using 255 - threshold to maintain original logic's sensitivity
                left = min(left, x)
                right = max(right, x)
                top = min(top, y)
                bottom = max(bottom, y)

    if left == width:  # No object detected, return full image bounds
        return 0, width, 0, height

    padding = 5
    return (
        max(0, left - padding),
        min(width, right + 1 + padding),  # right is exclusive, so +1
        max(0, top - padding),
        min(height, bottom + 1 + padding),  # bottom is exclusive, so +1
    )


def crop_to_target_ratio(img: np.ndarray, target_ratio: float) -> np.ndarray:
    """
    将图片裁剪到目标比例，尽量保持中心内容，输入为OpenCV图片。
    Args:
        img: OpenCV图片 (numpy.ndarray)
        target_ratio: 目标宽高比 (e.g., 5/3 或 3/5)
    Returns:
        裁剪后的OpenCV图片 (numpy.ndarray)
    """
    height, width, _ = img.shape
    current_ratio = width / height

    if abs(current_ratio - target_ratio) < 0.01:  # 已经接近目标比例
        return img

    if current_ratio > target_ratio:  # 当前图像太宽，需要减小宽度
        new_width = int(height * target_ratio)
        left = (width - new_width) // 2
        right = left + new_width
        top = 0
        bottom = height
    else:  # 当前图像太高，需要减小高度
        new_height = int(width / target_ratio)
        top = (height - new_height) // 2
        bottom = top + new_height
        left = 0
        right = width

    return img[top:bottom, left:right]


def pad_to_ratio(img: np.ndarray) -> np.ndarray:
    """
    Padding图片到指定比例，输入为OpenCV图片。
    Args:
        img: OpenCV图片 (numpy.ndarray)
    Returns:
        Padding后的OpenCV图片 (numpy.ndarray)
    """
    height, width, _ = img.shape
    ratio = 5 / 3 if width >= height else 3 / 5
    current_ratio = width / height

    if abs(current_ratio - ratio) < 0.01:
        return img

    bg_color = get_background_color(img)
    pad_top, pad_bottom, pad_left, pad_right = 0, 0, 0, 0

    if current_ratio > ratio:
        new_height = int(width / ratio)
        pad_top = (new_height - height) // 2
        pad_bottom = new_height - height - pad_top
    else:
        new_width = int(height * ratio)
        pad_left = (new_width - width) // 2
        pad_right = new_width - width - pad_left

    padded_img = cv2.copyMakeBorder(
        img,
        pad_top,
        pad_bottom,
        pad_left,
        pad_right,
        cv2.BORDER_CONSTANT,
        value=bg_color,
    )
    return padded_img


def resize_to_target(img: np.ndarray) -> np.ndarray:
    """
    Resize图片到目标尺寸，输入为OpenCV图片。
    Args:
        img: OpenCV图片 (numpy.ndarray)
    Returns:
        Resize后的OpenCV图片 (numpy.ndarray)
    """
    height, width, _ = img.shape
    if width > height:
        return cv2.resize(
            img, (SCREEN_LONG, SCREEN_SHORT), interpolation=cv2.INTER_LANCZOS4
        )
    return cv2.resize(
        img, (SCREEN_SHORT, SCREEN_LONG), interpolation=cv2.INTER_LANCZOS4
    )


def apply_floyd_steinberg_dithering(img: np.ndarray, shades: int = 16) -> np.ndarray:
    """
    对图片应用Floyd-Steinberg抖动算法，将其转换为指定色阶的灰度图像。
    Args:
        img: OpenCV图片 (BGR, numpy.ndarray)
        shades: 目标灰度色阶数量 (例如，16代表4位深度)
    Returns:
        抖动后的指定色阶灰度OpenCV图片 (numpy.ndarray)
    """
    if shades < 2:
        logger.warning(f"色阶数量必须至少为2，已自动调整为2。")
        shades = 2
    logger.info(f"应用Floyd-Steinberg抖动到 {shades} 级灰度。")

    # 转换为灰度图
    gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 复制一份图像用于修改，避免修改原始图像
    dithered_img = gray_img.copy().astype(np.float32)

    height, width = dithered_img.shape

    # 计算色阶值
    # 例如，对于16个色阶，值范围是 0, 17, 34, ..., 255
    levels = np.linspace(0, 255, shades)

    for y in range(height):
        for x in range(width):
            old_pixel = dithered_img[y, x]

            # 量化到最近的色阶值
            # 找到levels中最接近old_pixel的值
            new_pixel = levels[np.argmin(np.abs(levels - old_pixel))]
            dithered_img[y, x] = new_pixel

            # 计算量化误差
            quant_error = old_pixel - new_pixel

            # 将误差传播到周围像素 (Floyd-Steinberg权重)
            #       X   7/16
            # 3/16 5/16 1/16
            if x + 1 < width:
                dithered_img[y, x + 1] += quant_error * 7 / 16
            if y + 1 < height:
                if x - 1 >= 0:
                    dithered_img[y + 1, x - 1] += quant_error * 3 / 16
                dithered_img[y + 1, x] += quant_error * 5 / 16
                if x + 1 < width:
                    dithered_img[y + 1, x + 1] += quant_error * 1 / 16

    # 将结果裁剪到0-255范围并转换回uint8类型
    return np.clip(dithered_img, 0, 255).astype(np.uint8)


def process_image(
    input_path: str,
    output_path: str,
    apply_dither: bool = False,
    dither_shades: int = 16,
):
    """
    完整的图片处理流程，全程使用OpenCV。
    Args:
        input_path: 输入图片路径
        output_path: 输出图片路径
        apply_dither: 是否应用Floyd-Steinberg抖动
        dither_shades: 抖动后的灰度色阶数量 (例如，16代表4位深度)
    """
    img = cv2.imread(input_path)
    if img is None:
        logger.error(f"错误: 无法读取图片 {input_path}")
        return

    logger.info(f"原始尺寸: {img.shape[1]}x{img.shape[0]}")  # width x height

    # 1. 检测并裁切物体
    left, right, top, bottom = detect_object_bounds(img)
    cropped = img[top:bottom, left:right]
    logger.info(f"裁切后尺寸: {cropped.shape[1]}x{cropped.shape[0]}")  # width x height

    # 2. 根据背景类型决定Padding或按比例裁剪
    if is_solid_background(cropped):
        logger.info("背景为纯色，进行Padding到指定比例...")
        padded = pad_to_ratio(cropped)
    else:
        logger.info("背景不为纯色，尽量裁剪到5:3/3:5比例...")
        height, width, _ = cropped.shape
        target_ratio = 5 / 3 if width >= height else 3 / 5
        padded = crop_to_target_ratio(cropped, target_ratio)

    logger.info(f"处理后尺寸: {padded.shape[1]}x{padded.shape[0]}")  # width x height

    # 3. Resize到目标尺寸
    final = resize_to_target(padded)
    logger.info(f"最终尺寸: {final.shape[1]}x{final.shape[0]}")  # width x height

    # 4. 应用抖动 (如果启用)
    if apply_dither:
        final = apply_floyd_steinberg_dithering(final, shades=dither_shades)
    # 保存结果
    cv2.imwrite(output_path, final)
    logger.info(f"已保存到: {output_path}")

    return final


@click.command(help="一个图片预处理工具，用于电子墨水屏设备。")
@click.argument("input_path", type=click.Path(exists=True), required=True)
@click.option(
    "--output_dir",
    type=click.Path(file_okay=False, writable=True),
    default=None,
    help="指定输出目录。如果未指定，图片将保存到输入目录。",
)
@click.option(
    "--dither/--no-dither",
    default=False,
    help="是否应用Floyd-Steinberg抖动算法。",
)
@click.option(
    "--shades",
    type=click.IntRange(2, 256),  # Shades must be at least 2 (B&W)
    default=4,  # Default for 2-bit depth (4 shades)
    help="抖动后的灰度色阶数量 (例如，4代表2位深度)。仅在启用抖动时有效。",
)
def eink_process(input_path: str, output_dir: str | None, dither: bool, shades: int):
    """
    图片预处理工具的主入口点。
    """
    logger.info(f"开始处理: {input_path}")
    input_path_obj = Path(input_path)

    if input_path_obj.is_file():
        # 如果是文件，确定输出路径
        if output_dir:
            output_folder = Path(output_dir)
            output_folder.mkdir(parents=True, exist_ok=True)
        else:
            output_folder = input_path_obj.parent

        filename = input_path_obj.name
        base, ext = os.path.splitext(filename)
        output_file = output_folder / f"{base}eink{ext}"
        process_image(
            str(input_path_obj),
            str(output_file),
            apply_dither=dither,
            dither_shades=shades,
        )

    elif input_path_obj.is_dir():
        process_directory(
            input_path, output_dir, apply_dither=dither, dither_shades=shades
        )
    else:
        logger.error(f"无效的输入路径: {input_path}")


if __name__ == "__main__":
    eink_process()
