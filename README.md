# Z-Image Turbo GGUF 文生图 Demo

在 Apple Silicon Mac 上运行 Z-Image Turbo 量化模型的完整环境。

## 项目结构

```
.
├── models/                               # 模型文件目录
│   ├── diffusion_models/                # DiT 扩散模型目录
│   │   └── z-image-turbo-Q8_0.gguf     # 主模型 (需下载)
│   ├── text_encoder/                    # 文本编码器目录
│   │   └── Qwen3-4B-Q4_K_M.gguf        # Qwen 编码器 (需下载)
│   └── vae/                             # VAE 解码器目录
│       └── ae.safetensors              # VAE 模型 (需下载)
├── output/                              # 输出目录 (自动生成)
│   └── 2026-03-29/                      # 按日期组织的子目录
│       ├── cat_0001.png
│       └── portrait_0001.png
├── server/                              # Web UI 服务端
│   ├── main.py                          # FastAPI 应用
│   └── templates/                       # HTML 模板
│       └── index.html                   # Web UI 页面
├── stable-diffusion.cpp/                # stable-diffusion.cpp 源码 (需自行下载编译)
├── run_z_image.sh                       # 主要运行脚本 (Bash)
├── generate.py                          # Python 接口
├── pyproject.toml                       # uv 项目配置
└── README.md                            # 本文件
```

## 环境要求

- macOS (Apple Silicon)
- [uv](https://docs.astral.sh/uv/) - Python 包管理器
- Xcode Command Line Tools
- CMake 3.16+

## 快速开始

### 1. 环境准备

#### 1.1 安装 Xcode Command Line Tools

```bash
xcode-select --install
```

> 如果你已经完整安装了 Xcode，则无需额外安装 Command Line Tools。

#### 1.2 安装 CMake

**方式1：通过 Homebrew（推荐）**
```bash
brew install cmake
```

**方式2：通过官网下载**
从 https://cmake.org/download/ 下载 macOS 安装包，或使用：
```bash
sudo /Applications/CMake.app/Contents/bin/cmake-gui --install
```

#### 1.3 安装 uv（如未安装）

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

#### 1.4 激活 Python 环境

```bash
# 同步依赖（如 pyproject.toml 有变更）
uv sync

# 激活虚拟环境
source .venv/bin/activate
```

> **注意**：本项目仅依赖 Python 标准库，无需安装 PyTorch 等重型库。

### 2. 下载编译 stable-diffusion.cpp

```bash
# 克隆仓库
git clone --recursive https://github.com/leejet/stable-diffusion.cpp.git

# 编译 (Apple Silicon Mac)
cd stable-diffusion.cpp
cmake -B build -DSD_METAL=ON
cmake --build build -j8

# 编译完成后可执行文件位于:
# stable-diffusion.cpp/build/bin/sd-cli
```

### 3. 下载依赖模型

手动下载以下模型文件到对应目录：

| 模型类型 | 目标目录 | 推荐文件 | 下载地址 |
|----------|----------|----------|----------|
| **DiT 模型** | `models/diffusion_models/` | `z-image-turbo-Q8_0.gguf` | [Z-Image-Turbo-GGUF](https://huggingface.co/unsloth/Z-Image-Turbo-GGUF) |
| **文本编码器** | `models/text_encoder/` | `Qwen3-4B-Q4_K_M.gguf` | [Qwen3-4B-GGUF](https://huggingface.co/unsloth/Qwen3-4B-GGUF) |
| **VAE** | `models/vae/` | `ae.safetensors` | [ComfyUI Z-Image VAE](https://huggingface.co/Comfy-Org/z_image_turbo/tree/main/split_files/vae) |

创建目录并移动模型文件：

```bash
# 创建模型目录
mkdir -p models/diffusion_models models/text_encoder models/vae

# 移动模型到对应目录（根据实际下载的文件名调整）
mv z-image-turbo-Q8_0.gguf models/diffusion_models/
mv Qwen3-4B-Q4_K_M.gguf models/text_encoder/
mv ae.safetensors models/vae/

# 验证目录结构
ls -R models/
```

### 4. 生成图像

#### 基础用法

```bash
# 基础用法 (保存到 output/output_0001.png)
./run_z_image.sh -p "a beautiful sunset over mountains"
```

#### 使用前缀组织输出

```bash
# 自定义前缀 (output/cat_0001.png)
./run_z_image.sh -p "cute cat" --prefix "cat"

# 使用子目录 (output/aa/cat_0001.png)
./run_z_image.sh -p "cute cat" --prefix "aa/cat"

# 使用日期子目录 (output/2026-03-29/cat_0001.png)
./run_z_image.sh -p "cute cat" --prefix "%date%/cat"
```

#### 调整采样参数

```bash
# 使用 euler + sgm_uniform 组合 (推荐)
./run_z_image.sh -p "portrait of a woman" \
    --prefix "%date%/portraits/woman" \
    --sampling-method euler \
    --scheduler sgm_uniform \
    -W 1024 -H 1024 \
    -s 8

# 调整 guidance 获得更强提示词对齐
./run_z_image.sh -p "cyberpunk city at night" \
    --prefix "%date%/cyberpunk/city" \
    --guidance 4.5 \
    -W 1024 -H 1024 \
    -s 8
```

#### Python 接口

```bash
source .venv/bin/activate

# 基础用法
python generate.py -p "a beautiful sunset"

# 使用日期子目录
python generate.py -p "cute cat" --prefix "%date%/cat"

# 完整示例
python generate.py \
    -p "landscape with mountains" \
    --prefix "%date%/landscapes/mountain" \
    --sampling-method euler \
    --scheduler sgm_uniform \
    -W 1024 -H 1024 \
    -s 8
```

### 5. Web UI 界面

项目提供基于 FastAPI 的 Web 界面，支持可视化配置和生成图片。

#### 启动 Web 服务

```bash
# 方式1：使用 uv
uv run python server/main.py

# 方式2：使用 python
source .venv/bin/activate
python server/main.py
```

服务启动后，打开浏览器访问：**http://localhost:11451**

#### Web UI 功能

- 🎨 **可视化配置**：支持选择 Diffusion 模型、采样方法、调度器等
- 🖼️ **实时预览**：生成完成后直接在网页展示图片
- ⬇️ **一键下载**：生成的图片可直接下载保存
- 📱 **响应式设计**：支持桌面和移动端访问

#### API 接口

Web 服务同时提供 RESTful API：

```bash
# 获取可用模型列表
curl http://localhost:11451/api/models

# 生成图片
curl -X POST http://localhost:11451/api/generate \
  -F "prompt=a beautiful sunset" \
  -F "width=512" \
  -F "height=512" \
  -F "steps=4"
```

## 参数说明

### 基本参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `-p, --prompt` | 文本提示词 (必需) | - |
| `--prefix` | 输出文件前缀，支持 `%date%` 占位符和子目录 | `output` |
| `-W, --width` | 图像宽度 | 512 |
| `-H, --height` | 图像高度 | 512 |
| `-s, --steps` | 推理步数 (Turbo推荐4-8) | 4 |
| `--seed` | 随机种子 (-1表示随机) | -1 |

### 采样参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--sampling-method` | 采样方法 | `res_multistep` |
| `--scheduler` | 调度器 | `simple` |
| `--guidance` | 蒸馏引导尺度 (2.5-5.0) | 3.5 |

#### 支持的采样方法

- `euler`, `euler_a`, `heun`
- `dpm2`, `dpm++2s_a`, `dpm++2m`, `dpm++2mv2`
- `ipndm`, `ipndm_v`, `lcm`, `ddim_trailing`
- `tcd`, `res_multistep`, `res_2s`

#### 支持的调度器

- `discrete`, `karras`, `exponential`, `ays`, `gits`
- `smoothstep`, `sgm_uniform`, `simple`, `kl_optimal`, `lcm`, `bong_tangent`

### 文件命名规则

使用 `--prefix` 参数可以灵活组织输出文件：

| 示例 `--prefix` | 输出路径 |
|----------------|----------|
| `"cat"` | `output/cat_0001.png` |
| `"aa/cat"` | `output/aa/cat_0001.png` |
| `"%date%/cat"` | `output/2026-03-29/cat_0001.png` |
| `"%date%/aa/cat"` | `output/2026-03-29/aa/cat_0001.png` |

文件编号会自动递增：如果 `cat_0001.png` 已存在，则生成 `cat_0002.png`。

## 技术细节

### 模型架构

Z-Image Turbo 采用 S3-DiT (Scalable Single-Stream Diffusion Transformer) 架构：
- **DiT 模型**: 处理扩散过程的Transformer (z-image-turbo-Q8_0.gguf)
- **文本编码器**: 将提示词编码为嵌入向量 (Qwen3-4B)
- **VAE**: 将潜在空间解码为图像 (ae.safetensors)

### 加速技术

- **Metal GPU 加速**: 利用 M3 Pro 的 GPU 进行推理
- **GGUF 量化**: 8-bit 量化减少显存占用
- **少步推理**: Turbo 变体仅需 4-8 步即可生成高质量图像

### 采样参数说明

Z-Image Turbo 使用特定的采样配置：
- **CFG Scale**: 必须设为 `1.0` (Turbo 模型不需要传统分类器引导)
- **Guidance**: 蒸馏引导尺度，控制提示词遵循程度
  - `3.0-3.5`: 自然质感，适合风景
  - `4.0-4.5`: 强提示词遵循，适合人物/复杂场景
- **推荐步数**: 4-8 步

## 故障排除

### 模型文件缺失

```bash
# 确认模型目录结构正确
ls -R models/

# 预期输出:
# models/diffusion_models/z-image-turbo-*.gguf
# models/text_encoder/Qwen3-4B-*.gguf
# models/vae/ae.safetensors
```

如果提示找不到模型目录，请按"下载依赖模型"部分的说明创建目录并移动文件。

### 编译错误

如需重新编译 stable-diffusion.cpp：

```bash
cd stable-diffusion.cpp
cmake -B build -DSD_METAL=ON
cmake --build build -j8
```

### 内存不足

- 减小图像尺寸 (`-W 512 -H 512`)
- 确保使用 GGUF 量化模型而非 FP16
- 使用更小的文本编码器（如 Q3_K_S 代替 Q4_K_M）

### 生成结果异常

如果生成的图像看起来不正确：
- 确保 CFG Scale 设为 `1.0`（脚本已默认设置）
- 尝试调整 `--guidance` 参数（推荐 3.5-4.5）
- 使用推荐的采样组合：`--sampling-method euler --scheduler sgm_uniform`

## 参考链接

- [Z-Image Turbo HuggingFace](https://huggingface.co/unsloth/Z-Image-Turbo-GGUF)
- [Qwen3-4B-GGUF 文本编码器](https://huggingface.co/unsloth/Qwen3-4B-GGUF)
- [ComfyUI Z-Image VAE](https://huggingface.co/Comfy-Org/z_image_turbo/tree/main/split_files/vae)
- [stable-diffusion.cpp GitHub](https://github.com/leejet/stable-diffusion.cpp)
- [Z-Image 论文](https://arxiv.org/abs/2511.22699)

## 许可证

本项目仅用于学习和研究目的。模型使用权遵循原模型许可证。
