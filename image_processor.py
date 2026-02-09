#!/usr/bin/env python3
"""
图片预处理工具：
1. 检测物体边缘并裁切
2. Padding到5:3比例
3. Padding颜色以背景色为准
4. Resize到480*800或800*480
"""

import sys

from PIL import Image


def get_background_color(img):
    """获取图片的背景色（取四个角的颜色，取众数）"""
    # 确保是RGB模式
    if img.mode != "RGB":
        img = img.convert("RGB")

    corners = []
    width, height = img.size

    # 采样四个角
    corners.append(img.getpixel((0, 0)))
    corners.append(img.getpixel((width - 1, 0)))
    corners.append(img.getpixel((0, height - 1)))
    corners.append(img.getpixel((width - 1, height - 1)))

    # 统计颜色出现次数
    from collections import Counter

    color_counts = Counter(corners)
    return color_counts.most_common(1)[0][0]


def detect_object_bounds(img, threshold=240):
    """
    检测物体边界
    通过检测非背景色的像素来确定物体边界
    """
    width, height = img.size
    bg_color = get_background_color(img)

    # 转换为RGB
    if img.mode != "RGB":
        img = img.convert("RGB")

    left, right, top, bottom = width, 0, height, 0

    # 扫描每一行和每一列
    for y in range(height):
        for x in range(width):
            pixel = img.getpixel((x, y))
            # 判断是否为背景色（使用欧几里得距离）
            if not is_similar_color(pixel, bg_color, threshold):
                if x < left:
                    left = x
                if x > right:
                    right = x
                if y < top:
                    top = y
                if y > bottom:
                    bottom = y

    # 如果没有检测到物体，返回原图边界
    if left == width and right == 0:
        return 0, width, 0, height

    # 添加一些边距
    padding = 5
    left = max(0, left - padding)
    right = min(width, right + padding)
    top = max(0, top - padding)
    bottom = min(height, bottom + padding)

    return left, right, top, bottom


def is_similar_color(pixel, bg_color, threshold):
    """判断两个颜色是否相似"""
    if len(pixel) >= 3:
        r1, g1, b1 = pixel[:3]
    else:
        r1, g1, b1 = pixel[0], pixel[0], pixel[0]

    if len(bg_color) >= 3:
        r2, g2, b2 = bg_color[:3]
    else:
        r2, g2, b2 = bg_color[0], bg_color[0], bg_color[0]

    # 计算欧几里得距离
    distance = ((r1 - r2) ** 2 + (g1 - g2) ** 2 + (b1 - b2) ** 2) ** 0.5
    return distance < (255 - threshold)


def crop_to_object(img, bounds):
    """裁切到物体边界"""
    left, right, top, bottom = bounds
    return img.crop((left, top, right, bottom))


def calculate_padding_size(crop_width, crop_height, target_ratio=5 / 3):
    """
    计算Padding尺寸，使图片达到5:3比例
    返回 (new_width, new_height, pad_left, pad_top)
    """
    current_ratio = crop_width / crop_height

    if abs(current_ratio - target_ratio) < 0.01:
        # 已经是5:3比例
        return crop_width, crop_height, 0, 0

    if current_ratio > target_ratio:
        # 图片比目标比例更宽，需要增加高度
        new_height = int(crop_width / target_ratio)
        pad_top = (new_height - crop_height) // 2
        pad_left = 0
        return crop_width, new_height, pad_left, pad_top
    else:
        # 图片比目标比例更窄，需要增加宽度
        new_width = int(crop_height * target_ratio)
        pad_left = (new_width - crop_width) // 2
        pad_top = 0
        return new_width, crop_height, pad_left, pad_top


def pad_to_ratio(img):
    """Padding图片到指定比例"""
    width, height = img.size

    # 根据图片方向决定目标比例
    if width >= height:
        # 横图，目标比例 5:3
        target_ratio = 5 / 3
    else:
        # 竖图，目标比例 3:5
        target_ratio = 3 / 5

    new_width, new_height, pad_left, pad_top = calculate_padding_size(
        width, height, target_ratio
    )

    if pad_left == 0 and pad_top == 0:
        return img

    # 获取背景色
    bg_color = get_background_color(img)

    # 创建新图片
    new_img = Image.new("RGB", (new_width, new_height), bg_color)
    new_img.paste(img, (pad_left, pad_top))

    return new_img


def resize_to_target(img, target_width=480, target_height=800):
    """Resize图片到目标尺寸"""
    width, height = img.size

    # 根据方向决定目标尺寸
    if width > height:
        # 横图，resize到800*480
        target_width, target_height = 800, 480
    else:
        # 竖图，resize到480*800
        target_width, target_height = 480, 800

    return img.resize((target_width, target_height), Image.Resampling.LANCZOS)


def process_image(input_path, output_path):
    """完整的图片处理流程"""
    # 打开图片
    img = Image.open(input_path)

    print(f"原始尺寸: {img.size}")

    # 1. 检测并裁切物体
    bounds = detect_object_bounds(img)
    cropped = crop_to_object(img, bounds)
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
    input_file = (
        sys.argv[1] if len(sys.argv) > 1 else "/home/guozr/CODE/gEInk/test_input.webp"
    )

    # 默认输出为输入文件加eink后缀
    if len(sys.argv) > 2:
        output_file = sys.argv[2]
    else:
        import os

        base, ext = os.path.splitext(input_file)
        output_file = f"{base}eink{ext}"

    process_image(input_file, output_file)
