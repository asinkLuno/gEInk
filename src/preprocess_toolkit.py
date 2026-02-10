import cv2
import numpy as np
from loguru import logger
from PIL import Image

from .config import TARGET_HEIGHT, TARGET_WIDTH


def get_background_color(img: np.ndarray):
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
    from collections import Counter

    return Counter(corners).most_common(1)[0][0]


def is_solid_background(img: np.ndarray, tolerance: int = 30):
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
    avg_color = np.mean(border_pixels, axis=0)
    color_variance = np.mean(np.sum((border_pixels - avg_color) ** 2, axis=1))

    # 判断是否为纯色
    return color_variance < tolerance


def detect_object_bounds(img: np.ndarray, threshold: int = 240):
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

            if distance >= (255 - threshold):
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


def crop_to_target_ratio(img: np.ndarray, target_ratio: float):
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


def pad_to_ratio(img: np.ndarray, target_width, target_height):
    """
    Padding图片到指定比例，输入为OpenCV图片。
    根据图像方向决定使用5:3还是3:5比例。
    Args:
        img: OpenCV图片 (numpy.ndarray)
        target_width: 目标宽度
        target_height: 目标高度
    Returns:
        Padding后的OpenCV图片 (numpy.ndarray)
    """
    height, width, _ = img.shape

    # 根据图像方向决定目标比例
    # 横向图像使用 target_width/target_height (5:3)
    # 纵向图像使用 target_height/target_width (3:5)
    target_ratio = (
        target_width / target_height
        if width >= height
        else target_height / target_width
    )

    current_ratio = width / height

    if abs(current_ratio - target_ratio) < 0.01:
        return img

    bg_color = get_background_color(img)
    pad_top, pad_bottom, pad_left, pad_right = 0, 0, 0, 0

    if current_ratio > target_ratio:
        new_height = int(width / target_ratio)
        pad_top = (new_height - height) // 2
        pad_bottom = new_height - height - pad_top
    else:
        new_width = int(height * target_ratio)
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


def resize_to_target(img: np.ndarray, target_width, target_height):
    """
    Resize图片到目标尺寸，输入为OpenCV图片。
    Args:
        img: OpenCV图片 (numpy.ndarray)
        target_width: 目标宽度
        target_height: 目标高度
    Returns:
        Resize后的OpenCV图片 (numpy.ndarray)
    """
    height, width, _ = img.shape
    # 根据图像方向决定目标尺寸
    # 与pad_to_ratio保持一致：width >= height 时视为横向
    if width >= height:
        # 横向图像，使用目标尺寸
        return cv2.resize(
            img, (target_width, target_height), interpolation=cv2.INTER_LANCZOS4
        )
    else:
        # 纵向图像，交换目标尺寸
        return cv2.resize(
            img, (target_height, target_width), interpolation=cv2.INTER_LANCZOS4
        )


def _preprocess_image(
    input_image_path, target_width=TARGET_WIDTH, target_height=TARGET_HEIGHT
):
    """
    基于旧版本 image_processor.py 的预处理函数。
    处理流程：
    1. 读取彩色图像 (OpenCV BGR)
    2. 检测物体边界并裁剪
    3. 根据背景类型决定Padding或按比例裁剪
    4. 调整尺寸到目标分辨率
    5. 返回 PIL 图像 (RGB)
    """
    # 读取图像
    img = cv2.imread(input_image_path)
    if img is None:
        logger.error(f"错误: 无法读取图片 {input_image_path}")
        return None

    logger.info(f"原始尺寸: {img.shape[1]}x{img.shape[0]}")

    # 1. 检测并裁切物体
    left, right, top, bottom = detect_object_bounds(img)
    cropped = img[top:bottom, left:right]
    logger.info(f"裁切后尺寸: {cropped.shape[1]}x{cropped.shape[0]}")

    # 2. 根据背景类型决定Padding或按比例裁剪
    if is_solid_background(cropped):
        logger.info("背景为纯色，进行Padding到指定比例...")
        padded = pad_to_ratio(cropped, target_width, target_height)
    else:
        logger.info("背景不为纯色，尽量裁剪到目标比例...")
        height, width, _ = cropped.shape
        target_ratio = (
            target_width / target_height
            if width >= height
            else target_height / target_width
        )
        padded = crop_to_target_ratio(cropped, target_ratio)

    logger.info(f"处理后尺寸: {padded.shape[1]}x{padded.shape[0]}")

    # 3. Resize到目标尺寸
    final = resize_to_target(padded, target_width, target_height)
    logger.info(f"最终尺寸: {final.shape[1]}x{final.shape[0]}")

    # 转换为 PIL 图像 (BGR -> RGB)
    final_rgb = cv2.cvtColor(final, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(final_rgb)
    return pil_img
