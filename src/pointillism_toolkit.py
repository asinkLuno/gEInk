import random
from pathlib import Path

import cv2
import numpy as np
from loguru import logger

from .dithering_toolkit import DITHER_KERNELS, FLOYD_STEINBERG_KERNEL, error_diffusion


def prepare_textures(src_dir: str, only: list[str] | None = None) -> str:
    """
    将 src_dir 里的笔触 PNG 用 PIL 重新编码到 <src_dir>/.fixed/，
    修复 CRC 损坏等问题，使 Node.js canvas 可以正常加载。
    返回修复后的目录路径。
    """
    from PIL import Image, ImageFile

    ImageFile.LOAD_TRUNCATED_IMAGES = True

    src = Path(src_dir)
    dst = src / ".fixed"
    dst.mkdir(exist_ok=True)

    files = [f for ext in ("*.png", "*.jpg", "*.jpeg") for f in src.glob(ext)]
    if only is not None:
        files = [f for f in files if f.name in only]
    for f in files:
        out = dst / f.name
        if out.exists():
            continue
        try:
            img = Image.open(f)
            img.load()
            img.save(out, format="PNG")
        except Exception as e:
            logger.warning(f"跳过损坏纹理 {f.name}: {e}")

    count = len(list(dst.glob("*.png")))
    logger.info(f"笔触纹理已准备: {count} 个 → {dst}")
    return str(dst)


def hex_to_bgr(hex_color: str) -> np.ndarray:
    """将 hex 颜色字符串转换为 OpenCV BGR 格式数组"""
    hex_color = hex_color.lstrip("#")
    r, g, b = tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
    return np.array([b, g, r], dtype=np.float32)


# 用户定义的柔和调色板 (OpenCV BGR 格式)
_DEFAULT_PALETTE_HEX = [
    "#000000",
    "#FFFFFF",
    "#26A7E1",
    "#13AF68",
    "#E95412",
    "#FFE009",
    "#E274A9",
]
DEFAULT_PALETTE: np.ndarray = np.array(
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
    closest_index = int(np.argmin(distances))
    return palette[closest_index]


def color_atkinson_dithering(
    color_img: np.ndarray,
    palette: np.ndarray,
    method: str = "floyd_steinberg",
) -> np.ndarray:
    """
    第二阶段：数字排线与光学混合
    method: "floyd_steinberg" (default, best for photos), "stucki" (smoothest), "atkinson" (graphics)
    """
    kernel = DITHER_KERNELS.get(method, FLOYD_STEINBERG_KERNEL)
    logger.info(f"应用彩色 {method} 抖动 (计算光学混合)...")
    return error_diffusion(
        color_img,
        lambda p: find_closest_palette_color(p, palette),
        kernel,
    )


def export_dots_json(
    dithered_img: np.ndarray,
    base_radius: int = 3,
    jitter: int = 1,
    bg_color: tuple[int, int, int] = (240, 245, 245),  # BGR
    alpha: float = 0.5,
    texture_dir: str | None = None,
) -> dict:
    """
    第三阶段（数据）：将抖动后的像素矩阵转换为点列表，供 Node.js Canvas 渲染。
    返回 dict 可直接 json.dump 为 dots.json。
    """
    h, w = dithered_img.shape[:2]
    logger.info(f"生成点彩数据... (基础半径: {base_radius}px)")

    step = max(1, base_radius * 2)  # 点间距 = 直径，点之间刚好相切
    dots = []
    for y in range(step // 2, h, step):
        for x in range(step // 2, w, step):
            pixel_color = dithered_img[y, x]  # BGR uint8
            if np.array_equal(pixel_color, [255, 255, 255]):
                continue

            cx = x + random.randint(-jitter, jitter)
            cy = y + random.randint(-jitter, jitter)
            r = base_radius + random.randint(0, base_radius // 4 + 1)

            # BGR → RGB for JSON / Canvas
            b, g, rv = int(pixel_color[0]), int(pixel_color[1]), int(pixel_color[2])
            dots.append({"x": cx, "y": cy, "r": r, "rgb": [rv, g, b]})

    # bg BGR → RGB
    bg_rgb: list[int] = [int(bg_color[2]), int(bg_color[1]), int(bg_color[0])]
    logger.info(f"共生成 {len(dots)} 个点")
    return {
        "width": w,
        "height": h,
        "step": step,
        "bg": bg_rgb,
        "alpha": alpha,
        "texture_dir": texture_dir,
        "dots": dots,
    }
