import cv2
import numpy as np
from loguru import logger

from .config import TARGET_HEIGHT, TARGET_WIDTH


def get_background_color(img: np.ndarray) -> np.ndarray:
    from collections import Counter

    h, w = img.shape[:2]
    corners = [img[0, 0], img[0, w - 1], img[h - 1, 0], img[h - 1, w - 1]]
    color = Counter(tuple(c.tolist()) for c in corners).most_common(1)[0][0]
    return np.array(color)


def is_solid_background(img: np.ndarray, tolerance: int = 60) -> bool:
    h, w = img.shape[:2]
    if h < 2 or w < 2:
        return True
    corners = np.array([img[0, 0], img[0, w - 1], img[h - 1, 0], img[h - 1, w - 1]])
    variance = np.mean(np.sum((corners - corners.mean(axis=0)) ** 2, axis=1))
    return bool(variance < tolerance)


def detect_object_bounds(img: np.ndarray, bg_color: np.ndarray, threshold: int = 15):
    diff = img.astype(np.int32) - bg_color
    mask = np.sum(diff**2, axis=2) >= threshold**2
    rows = np.any(mask, axis=1)
    cols = np.any(mask, axis=0)

    if not rows.any():
        return 0, img.shape[1], 0, img.shape[0]

    row_idx = np.where(rows)[0]
    col_idx = np.where(cols)[0]
    top, bottom = int(row_idx[0]), int(row_idx[-1])
    left, right = int(col_idx[0]), int(col_idx[-1])

    pad = 5
    h, w = img.shape[:2]
    return max(0, left - pad), min(w, right + 1 + pad), max(0, top - pad), min(h, bottom + 1 + pad)


def crop_to_target_ratio(img: np.ndarray, target_ratio: float) -> np.ndarray:
    h, w = img.shape[:2]
    if abs(w / h - target_ratio) < 0.01:
        return img
    if w / h > target_ratio:
        new_w = int(h * target_ratio)
        left = (w - new_w) // 2
        return img[:, left : left + new_w]
    else:
        new_h = int(w / target_ratio)
        top = (h - new_h) // 2
        return img[top : top + new_h, :]


def pad_to_ratio(img: np.ndarray, target_ratio: float) -> np.ndarray:
    h, w = img.shape[:2]
    if abs(w / h - target_ratio) < 0.01:
        return img
    bg_color = get_background_color(img)
    if w / h > target_ratio:
        new_h = int(w / target_ratio)
        pad_top = (new_h - h) // 2
        pad_bottom = new_h - h - pad_top
        pad_left = pad_right = 0
    else:
        new_w = int(h * target_ratio)
        pad_left = (new_w - w) // 2
        pad_right = new_w - w - pad_left
        pad_top = pad_bottom = 0
    return cv2.copyMakeBorder(
        img, pad_top, pad_bottom, pad_left, pad_right, cv2.BORDER_CONSTANT, value=bg_color.tolist()
    )


def resize_to_target(img: np.ndarray, target_width, target_height) -> np.ndarray:
    if img.shape[0] > img.shape[1]:
        img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
    return cv2.resize(img, (target_width, target_height), interpolation=cv2.INTER_LANCZOS4)


def _preprocess_image(input_image_path, target_width=TARGET_WIDTH, target_height=TARGET_HEIGHT):
    img = cv2.imread(input_image_path)
    if img is None:
        logger.error(f"错误: 无法读取图片 {input_image_path}")
        return None

    logger.info(f"原始尺寸: {img.shape[1]}x{img.shape[0]}")

    bg_color = get_background_color(img)
    left, right, top, bottom = detect_object_bounds(img, bg_color)
    cropped = img[top:bottom, left:right]
    logger.info(f"裁切后尺寸: {cropped.shape[1]}x{cropped.shape[0]}")

    h, w = cropped.shape[:2]
    target_ratio = target_width / target_height if w >= h else target_height / target_width

    if is_solid_background(cropped):
        logger.info("背景为纯色，进行Padding到指定比例...")
        padded = pad_to_ratio(cropped, target_ratio)
    else:
        logger.info("背景不为纯色，尽量裁剪到目标比例...")
        padded = crop_to_target_ratio(cropped, target_ratio)

    logger.info(f"处理后尺寸: {padded.shape[1]}x{padded.shape[0]}")
    return resize_to_target(padded, target_width, target_height)
