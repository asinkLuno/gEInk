#!/usr/bin/env python3
"""
图片预处理工具：
1. 检测物体边缘并裁切
2. Padding到5:3比例
3. Padding颜色以背景色为准
4. Resize到480*800或800*480
"""

import os
import sys
from collections import Counter
from typing import Tuple

from PIL import Image

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


def process_directory(input_dir: str):
    """处理目录下所有图片"""
    image_files = get_image_files(input_dir)
    total = len(image_files)

    if total == 0:
        print(f"在 {input_dir} 中未找到图片文件")
        return

    print(f"找到 {total} 张图片，开始处理...\n")

    for idx, input_path in enumerate(image_files, 1):
        filename = os.path.basename(input_path)
        base, ext = os.path.splitext(filename)
        output_path = os.path.join(input_dir, f"{base}eink{ext}")

        print(f"[{idx}/{total}] 处理: {filename}")
        process_image(input_path, output_path)
        print()


def get_background_color(img):
    """获取图片的背景色（取四个角的颜色，取众数）"""
    if img.mode != "RGB":
        img = img.convert("RGB")
    width, height = img.size

    corners = [
        img.getpixel((0, 0)),
        img.getpixel((width - 1, 0)),
        img.getpixel((0, height - 1)),
        img.getpixel((width - 1, height - 1)),
    ]
    return Counter(corners).most_common(1)[0][0]


def detect_object_bounds(img, threshold=240) -> Tuple[int, int, int, int]:
    """检测物体边界"""
    width, height = img.size
    bg_color = get_background_color(img)

    left, right, top, bottom = width, 0, height, 0

    for y in range(height):
        for x in range(width):
            pixel = img.getpixel((x, y))
            r1, g1, b1 = pixel[:3] if len(pixel) >= 3 else (pixel[0],) * 3
            r2, g2, b2 = bg_color[:3]
            distance = ((r1 - r2) ** 2 + (g1 - g2) ** 2 + (b1 - b2) ** 2) ** 0.5

            if distance >= (255 - threshold):
                left = min(left, x)
                right = max(right, x)
                top = min(top, y)
                bottom = max(bottom, y)

    if left == width:
        return 0, width, 0, height

    padding = 5
    return (
        max(0, left - padding),
        min(width, right + padding),
        max(0, top - padding),
        min(height, bottom + padding),
    )


def pad_to_ratio(img):
    """Padding图片到指定比例"""
    width, height = img.size
    ratio = 5 / 3 if width >= height else 3 / 5
    current_ratio = width / height

    if abs(current_ratio - ratio) < 0.01:
        return img

    if current_ratio > ratio:
        new_height = int(width / ratio)
        pad_top = (new_height - height) // 2
        new_img = Image.new("RGB", (width, new_height), get_background_color(img))
        new_img.paste(img, (0, pad_top))
    else:
        new_width = int(height * ratio)
        pad_left = (new_width - width) // 2
        new_img = Image.new("RGB", (new_width, height), get_background_color(img))
        new_img.paste(img, (pad_left, 0))

    return new_img


def resize_to_target(img):
    """Resize图片到目标尺寸"""
    width, height = img.size
    if width > height:
        return img.resize((SCREEN_LONG, SCREEN_SHORT), Image.Resampling.LANCZOS)
    return img.resize((SCREEN_SHORT, SCREEN_LONG), Image.Resampling.LANCZOS)


def process_image(input_path, output_path):
    """完整的图片处理流程"""
    img = Image.open(input_path)
    print(f"原始尺寸: {img.size}")

    # 1. 检测并裁切物体
    left, right, top, bottom = detect_object_bounds(img)
    cropped = img.crop((left, top, right, bottom))
    print(f"裁切后尺寸: {cropped.size}")

    # 2. Padding到5:3或3:5比例
    padded = pad_to_ratio(cropped)
    print(f"Padding后尺寸: {padded.size}")

    # 3. Resize到目标尺寸
    final = resize_to_target(padded)
    print(f"最终尺寸: {final.size}")

    # 保存结果
    final.save(output_path)
    print(f"已保存到: {output_path}")

    return final


if __name__ == "__main__":
    input_path = (
        sys.argv[1] if len(sys.argv) > 1 else "/home/guozr/CODE/gEInk/test_input.webp"
    )

    # 判断是文件还是目录
    if os.path.isdir(input_path):
        process_directory(input_path)
    else:
        base, ext = os.path.splitext(input_path)
        output_file = f"{base}eink{ext}"
        process_image(input_path, output_file)
