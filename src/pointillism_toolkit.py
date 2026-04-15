import numpy as np
import cv2
import random
from loguru import logger


# Atkinson 误差扩散矩阵 (dy, dx, weight)
def hex_to_bgr(hex_color: str) -> np.ndarray:
    """将 hex 颜色字符串转换为 OpenCV BGR 格式数组"""
    hex_color = hex_color.lstrip("#")
    r, g, b = tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
    return np.array([b, g, r], dtype=np.float32)


ATKINSON_KERNEL = [
    (0, 1, 1 / 8),
    (0, 2, 1 / 8),
    (1, -1, 1 / 8),
    (1, 0, 1 / 8),
    (1, 1, 1 / 8),
    (2, 0, 1 / 8),
]

# 用户定义的柔和调色板 (OpenCV BGR 格式)
# 通过降低饱和度、提高灰度，减少视觉疲劳
_DEFAULT_PALETTE_HEX = [
    "#000000",
    "#FFFFFF",
    "#ECB4C8",
    "#EED838",
    "#CAE9C5",
    "#DF7E53",
    "#92CE68",
]
DEFAULT_PALETTE = np.array(
    [hex_to_bgr(h) for h in _DEFAULT_PALETTE_HEX], dtype=np.float32
)


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
    closest_index = np.argmin(distances)
    return palette[closest_index]


def color_atkinson_dithering(color_img: np.ndarray, palette: np.ndarray) -> np.ndarray:
    """
    第二阶段：数字排线与光学混合
    对彩色图像进行三通道 Atkinson 抖动，利用调色板中的纯色交替排布来混合出原本不存在的颜色。
    """
    dithered = color_img.astype(np.float32)
    height, width, channels = dithered.shape

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
    bg_color: tuple = (240, 245, 245),  # 偏暖灰的纸张底色 (BGR格式)
) -> np.ndarray:
    """
    第三阶段：物理笔触渲染
    将生成的数字像素矩阵渲染为带有颜料重叠、大小差异和手绘随机性的画作。
    """
    height, width, _ = dithered_img.shape

    # 创建高分辨率的彩色空白画布
    canvas = np.full((height * scale, width * scale, 3), bg_color, dtype=np.uint8)

    logger.info(
        f"开始渲染彩色点彩效果... (放大倍数: {scale}x, 基础半径: {base_radius})"
    )

    for y in range(height):
        for x in range(width):
            color = dithered_img[y, x].tolist()

            # 跳过纯白色，利用“留白”透出画布底层纸张的颜色
            if color == [255.0, 255.0, 255.0]:
                continue

            # 计算在高分辨率画布上的基础中心坐标
            center_x = x * scale + scale // 2
            center_y = y * scale + scale // 2

            # 引入位置随机偏移 (打破机械排布)
            offset_x = random.randint(-jitter, jitter)
            offset_y = random.randint(-jitter, jitter)

            # 引入笔触大小微小变化
            r = base_radius + random.randint(0, 1)

            final_x = center_x + offset_x
            final_y = center_y + offset_y

            dot_color = (int(color[0]), int(color[1]), int(color[2]))
            # 绘制实心圆点
            cv2.circle(canvas, (final_x, final_y), r, dot_color, -1)

    return canvas
