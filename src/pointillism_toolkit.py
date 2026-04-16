import random
from pathlib import Path

import cv2
import numpy as np
from loguru import logger


def hex_to_bgr(hex_color: str) -> np.ndarray:
    """将 hex 颜色字符串转换为 OpenCV BGR 格式数组"""
    hex_color = hex_color.lstrip("#")
    r, g, b = tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
    return np.array([b, g, r], dtype=np.float32)


# Atkinson 误差扩散矩阵 (dy, dx, weight)
ATKINSON_KERNEL: list[tuple[int, int, float]] = [
    (0, 1, 1 / 8),
    (0, 2, 1 / 8),
    (1, -1, 1 / 8),
    (1, 0, 1 / 8),
    (1, 1, 1 / 8),
    (2, 0, 1 / 8),
]

# 用户定义的柔和调色板 (OpenCV BGR 格式)
_DEFAULT_PALETTE_HEX = [
    "#000000",
    "#FFFFFF",
    "#ECB4C8",
    "#EED838",
    "#CAE9C5",
    "#DF7E53",
    "#92CE68",
]
DEFAULT_PALETTE: np.ndarray = np.array(
    [hex_to_bgr(h) for h in _DEFAULT_PALETTE_HEX], dtype=np.float32
)


def load_brush_textures(texture_dir: str) -> list[np.ndarray]:
    """
    扫描目录并加载笔触纹理。
    期望 PNG 格式，并提取 alpha 通道作为 mask。
    """
    textures = []
    path = Path(texture_dir)
    if not path.exists():
        logger.warning(f"纹理目录不存在: {texture_dir}")
        return []

    # 支持常用的图片格式
    files = (
        list(path.glob("*.png")) + list(path.glob("*.jpg")) + list(path.glob("*.jpeg"))
    )
    for f in files:
        # 使用 IMREAD_UNCHANGED 保留 alpha 通道
        img = cv2.imread(str(f), cv2.IMREAD_UNCHANGED)
        if img is None:
            continue

        # 如果有 alpha 通道，提取它作为 mask
        if img.shape[2] == 4:
            mask = img[:, :, 3].astype(np.float32) / 255.0
        else:
            # 否则转为灰度并反转（假设白底黑字笔触）
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            mask = (255 - gray).astype(np.float32) / 255.0

        textures.append(mask)

    logger.info(f"已加载 {len(textures)} 个笔触纹理")
    return textures


def create_color_blocks(
    img: np.ndarray, spatial_rad: int = 15, color_rad: int = 40
) -> np.ndarray:
    """
    第一阶段：底稿概括
    使用均值漂移滤波抹平细碎纹理，保留结构边缘，划分出明确的大色块。
    """
    logger.info(
        f"正在进行平滑减色处理 (空间半径:{spatial_rad}, 色彩半径:{color_rad})...这可能需要几秒钟"
    )
    shifted = cv2.pyrMeanShiftFiltering(img, sp=spatial_rad, sr=color_rad)
    return shifted


def find_closest_palette_color(pixel: np.ndarray, palette: np.ndarray) -> np.ndarray:
    """计算当前像素与调色板中所有颜色的欧氏距离，返回最接近的纯色"""
    distances = np.sum((palette - pixel) ** 2, axis=1)
    closest_index = int(np.argmin(distances))
    return palette[closest_index]


def color_atkinson_dithering(color_img: np.ndarray, palette: np.ndarray) -> np.ndarray:
    """
    第二阶段：数字排线与光学混合
    对彩色图像进行三通道 Atkinson 抖动，利用调色板中的纯色交替排布来混合出原本不存在的颜色。
    """
    dithered = color_img.astype(np.float32)
    height, width = dithered.shape[:2]

    logger.info("应用彩色 Atkinson 抖动 (计算光学混合)...")

    for y in range(height):
        for x in range(width):
            old_pixel = dithered[y, x].copy()

            # 寻找调色板中最接近的颜色
            new_pixel = find_closest_palette_color(old_pixel, palette)
            dithered[y, x] = new_pixel

            # 计算三通道误差向量 (B, G, R 的偏差)
            error = old_pixel - new_pixel

            if np.all(error == 0):
                continue

            # 将色彩误差扩散给尚未处理的周围像素
            for dy, dx, w in ATKINSON_KERNEL:
                ny, nx = y + dy, x + dx
                if 0 <= ny < height and 0 <= nx < width:
                    dithered[ny, nx] += error * w

    return np.clip(dithered, 0, 255).astype(np.uint8)


def render_color_pointillism(
    dithered_img: np.ndarray,
    scale: int = 4,
    base_radius: int = 3,
    jitter: int = 1,
    bg_color: tuple[int, int, int] = (240, 245, 245),  # 偏暖灰的纸张底色 (BGR格式)
    alpha: float = 0.5,  # 水彩透明度，0=完全透明，1=不透明
    brush_textures: list[np.ndarray] | None = None,
) -> np.ndarray:
    """
    第三阶段：水彩渲染
    将生成的数字像素矩阵渲染为柔边、透明、颜色相互渗透的水彩效果。
    """
    height, width = dithered_img.shape[:2]

    # float32 画布支持真正的 alpha 混合
    canvas = np.full((height * scale, width * scale, 3), bg_color, dtype=np.float32)

    logger.info(
        f"开始渲染水彩点彩效果... (放大倍数: {scale}x, 基础半径: {base_radius}, 透明度: {alpha})"
    )

    canvas_h, canvas_w = canvas.shape[:2]

    for y in range(height):
        for x in range(width):
            pixel_color = dithered_img[y, x]

            # 跳过纯白色，利用"留白"透出画布底层纸张的颜色
            if np.array_equal(pixel_color, [255, 255, 255]):
                continue

            # 计算在高分辨率画布上的基础中心坐标
            center_x = x * scale + scale // 2
            center_y = y * scale + scale // 2

            # 引入位置随机偏移 (打破机械排布)
            offset_x = random.randint(-jitter, jitter)
            offset_y = random.randint(-jitter, jitter)

            final_x = center_x + offset_x
            final_y = center_y + offset_y

            # 引入笔触大小微小变化
            r = base_radius + random.randint(0, 1)

            if brush_textures:
                # 随机选一个笔触并进行随机旋转和缩放
                texture = random.choice(brush_textures)
                angle = random.uniform(0, 360)
                # 将 texture 缩放到 size 约等于 r*3
                size = r * 3

                # 旋转矩阵逻辑：
                # 1. 原始纹理中心 (tw/2, th/2)
                # 2. 目标 patch 中心 (patch_size/2, patch_size/2)
                th, tw = texture.shape[:2]
                patch_size = int(size * 1.5)
                m_rot = cv2.getRotationMatrix2D(
                    (tw / 2, th / 2), angle, size / max(th, tw)
                )

                # 关键修正：调整平移分量，使原始纹理中心映射到 patch 中心
                m_rot[0, 2] += (patch_size / 2) - (tw / 2)
                m_rot[1, 2] += (patch_size / 2) - (th / 2)

                soft_mask = (
                    cv2.warpAffine(
                        texture, m_rot, (patch_size, patch_size), flags=cv2.INTER_LINEAR
                    )
                    * alpha
                )

                local_cx, local_cy = patch_size // 2, patch_size // 2
                y1, y2 = (
                    max(0, final_y - local_cy),
                    min(canvas_h, final_y - local_cy + patch_size),
                )
                x1, x2 = (
                    max(0, final_x - local_cx),
                    min(canvas_w, final_x - local_cx + patch_size),
                )

                if y1 >= y2 or x1 >= x2:
                    continue

                # 裁剪 mask 以匹配画布边缘
                mask_y1 = y1 - (final_y - local_cy)
                mask_y2 = mask_y1 + (y2 - y1)
                mask_x1 = x1 - (final_x - local_cx)
                mask_x2 = mask_x1 + (x2 - x1)

                soft_mask = soft_mask[mask_y1:mask_y2, mask_x1:mask_x2]
            else:
                # 局部 patch 边界（含边缘模糊扩展）
                pad = r + 2
                y1, y2 = max(0, final_y - pad), min(canvas_h, final_y + pad + 1)
                x1, x2 = max(0, final_x - pad), min(canvas_w, final_x + pad + 1)
                if y1 >= y2 or x1 >= x2:
                    continue

                patch_h, patch_w = y2 - y1, x2 - x1
                local_cx, local_cy = final_x - x1, final_y - y1

                # 圆形遮罩 → Gaussian 软化边缘 → 乘以 alpha
                hard_mask = np.zeros((patch_h, patch_w), dtype=np.float32)
                cv2.circle(hard_mask, (local_cx, local_cy), r, 1.0, -1)
                ksize = r * 2 + 1
                soft_mask = cv2.GaussianBlur(hard_mask, (ksize, ksize), r / 2) * alpha

            # 将颜色 alpha 混合到画布（颜色渗透，不是覆盖）
            dot_color = pixel_color.astype(np.float32)
            m = soft_mask[:, :, np.newaxis]
            canvas[y1:y2, x1:x2] = canvas[y1:y2, x1:x2] * (1 - m) + dot_color * m

    return np.clip(canvas, 0, 255).astype(np.uint8)
