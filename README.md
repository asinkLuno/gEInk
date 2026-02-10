# E-Ink Image Processor (geink)

一个用于电子墨水屏图片预处理、抖动和格式转换的命令行工具。

## 功能模块 (Commands)

`geink` 工具提供以下子命令，每个子命令负责处理图像的不同阶段：

### 1. `preprocess` - 图像预处理
负责将输入图片进行灰度转换、智能裁切、方向处理、Padding 和 Resize 到指定尺寸。

**处理流程:**
```mermaid
flowchart TD
    A[输入图片] --> B[转换为灰度图]
    B --> C[物体检测与裁切]
    C --> D{判断方向}
    D -->|纵向 height > width| E[旋转 90°]
    D -->|横向 width > height| F[保持横向]
    E --> G[Padding 到 5:3 比例]
    F --> G
    G --> H[Resize 到目标尺寸]
    H --> I[输出预处理后的图片]
```

### 2. `dither` - 图像抖动
对预处理后的灰度图片应用抖动算法（如 Floyd-Steinberg 或 Jarvis, Judice, Ninke），转换为多级灰度图或二值图。

**处理流程:**
```mermaid
flowchart TD
    A[输入灰度图] --> B[应用抖动算法]
    B --> C[输出抖动后的图片]
```

### 3. `convert` - 转换为 EPD 格式
将抖动后的图片（多级灰度或二值）转换为电子墨水屏专用的原始二进制 (`.bin`) 格式。

**处理流程:**
```mermaid
flowchart TD
    A[输入抖动后的图片] --> B[转换为 EPD 二进制格式]
    B --> C[输出 .bin 文件]
```
## 使用方法

首先，安装项目依赖：
```bash
pip install -e ".[dev]"
```

`geink` 是一个命令行工具，通过子命令进行操作。

### 1. 图像预处理 (`preprocess`)
将图片预处理到目标尺寸。

```bash
geink preprocess path/to/image.jpg output_preprocessed.png --width 800 --height 480
```

### 2. 图像抖动 (`dither`)
对预处理后的图片进行抖动处理，生成多级灰度图像。

```bash
geink dither output_preprocessed.png output_dithered.png --method floyd_steinberg --color-levels 4
```

### 3. 转换为 EPD 格式 (`convert`)
将抖动后的图片转换为 EPD 原始二进制格式。

```bash
geink convert output_dithered.png output.bin --width 800 --height 480 --color-levels 4
```

## 命令行参数

`geink` 命令的参数是根据其子命令来定义的。

### `geink preprocess` 参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `INPUT_PATH` | (必填) | 输入图片文件路径 |
| `OUTPUT_PATH` | (必填) | 输出图片文件路径 |
| `--width` / `-w` | `800` (来自 `config.py`) | 目标宽度 |
| `--height` / `-h` | `480` (来自 `config.py`) | 目标高度 |

### `geink dither` 参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `INPUT_PATH` | (必填) | 输入灰度图片文件路径 |
| `OUTPUT_PATH` | (必填) | 输出抖动后的图片文件路径 |
| `--method` / `-m` | `floyd_steinberg` | 抖动算法 |
| `--color-levels` / `-c` | `4` (来自 `config.py`) | 抖动后的颜色级别数 (2 的幂次) |

### `geink convert` 参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `INPUT_PATH` | (必填) | 输入抖动后的图片文件路径 |
| `OUTPUT_PATH` | (必填) | 输出 EPD 原始二进制文件路径 |
| `--width` / `-w` | `800` (来自 `config.py`) | 目标宽度 |
| `--height` / `-h` | `480` (来自 `config.py`) | 目标高度 |
| `--color-levels` / `-c` | `4` (来自 `config.py`) | 输入图片使用的颜色级别数 (2 的幂次) |

### 支持的抖动算法 (`--method` 参数)

- `floyd_steinberg`: Floyd-Steinberg（默认，速度快）
- `jarvis_judice_ninke`: Jarvis, Judice, Ninke（质量更高，扩散更均匀）

## 输出格式

输出为 `.bin` 原始二进制文件，每像素 1 bit，按行优先排列。
文件大小计算：`width × height ÷ 8` bytes

例如 800×480 的图片输出文件大小为 48,000 bytes。
