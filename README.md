# E-Ink Image Processor (geink)

一个用于电子墨水屏图片预处理、抖动和格式转换的命令行工具。

## 功能模块 (Commands)

`geink` 工具提供以下子命令，每个子命令负责处理图像的不同阶段：

### 1. `preprocess` - 图像预处理
负责将输入图片进行物体检测、智能裁切、背景处理、方向处理和 Resize 到指定尺寸。

**处理流程:**
```mermaid
flowchart TD
    A[输入图片] --> B[物体检测与裁切]
    B --> C{背景是否为纯色?}
    C -->|是| D[Padding 到 5:3]
    C -->|否| E[居中裁剪到 5:3]
    D --> F{是否纵向图片?}
    E --> F
    F -->|是| G[旋转 90°]
    F -->|否| H[保持横向]
    G --> I[Resize 到目标尺寸]
    H --> I
    I --> J[输出预处理后的图片]
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
| `--color-levels` / `-c` | `2` (来自 `config.py`) | 抖动后的颜色级别数 (2 的幂次) |

### `geink convert` 参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `INPUT_PATH` | (必填) | 输入抖动后的图片文件路径 |
| `OUTPUT_PATH` | (必填) | 输出 EPD 原始二进制文件路径 |
| `--width` / `-w` | `800` (来自 `config.py`) | 目标宽度 |
| `--height` / `-h` | `480` (来自 `config.py`) | 目标高度 |
| `--color-levels` / `-c` | `2` (来自 `config.py`) | 输入图片使用的颜色级别数 (2 的幂次) |
| `--espslider-dir` | `ESPSlider/` | ESPSlider 目录，自动生成 .h 头文件 |

### 支持的抖动算法 (`--method` 参数)

- `floyd_steinberg`: Floyd-Steinberg（默认，速度快，扩散到相邻 4 像素）
- `jarvis_judice_ninke`: Jarvis, Judice, Ninke（质量更高，扩散到相邻 12 像素）
- `stucki`: Stucki（JNN 变体，产生更平滑的结果）

## 输出格式

输出为 `.bin` 原始二进制文件，每像素 1 bit，按行优先排列。
文件大小计算：`width × height ÷ 8` bytes

例如 800×480 的图片输出文件大小为 48,000 bytes。

---

## ESPSlider 固件烧录

ESPSlider 是运行在 ESP8266 上的电子墨水屏驱动程序，通过 Web 界面接收并显示处理后的图像。

### 编译固件

```bash
# 进入项目目录
cd ESPSlider

# 确保主文件名与目录名匹配（Arduino CLI 要求）
mv Loader.ino ESPSlider.ino

# 编译（使用 generic 板型）
arduino-cli compile --fqbn esp8266:esp8266:generic /home/guozr/CODE/gEInk/ESPSlider
```

编译成功后会生成固件文件：
- `/home/guozr/.cache/arduino/sketches/.../ESPSlider.ino.bin` - 烧录用固件
- `/home/guozr/.cache/arduino/sketches/.../ESPSlider.ino.elf` - ELF 调试文件

### 烧录固件

```bash
# 通过串口烧录（需要先连接 USB 转串口模块）
arduino-cli upload -p /dev/ttyUSB0 --fqbn esp8266:esp8266:generic /home/guozr/CODE/gEInk/ESPSlider
```

### 查看串口日志

```bash
# 115200 波特率查看启动日志
screen /dev/ttyUSB0 115200
# 或
minicom -D /dev/ttyUSB0 -b 115200
```

### 资源使用

| 资源 | 使用量 | 总量 | 占比 |
|------|--------|------|------|
| RAM (全局/静态) | 48,472 B | 80,192 B | 60% |
| IRAM (指令内存) | 60,807 B | 65,536 B | 92% |
| Flash (代码) | 304,024 B | 1,048,576 B | 28% |
