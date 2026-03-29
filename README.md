# Z-Image Turbo GGUF 文生图 Demo

在 Apple Silicon Mac 上运行 Z-Image Turbo 量化模型的完整环境。

## 项目结构

```
.
├── models/                          # 模型文件目录
│   ├── z-image-turbo-Q8_0.gguf     # DiT 扩散模型 (已下载)
│   ├── Qwen3-4B-Q4_K_M.gguf        # 文本编码器 (需下载)
│   ├── ae.safetensors              # VAE 解码器 (需下载)
│   └── flux-ae.sft                 # 备选 VAE (可选)
├── output/                          # 输出目录 (自动生成)
│   └── 2026-03-29/                 # 按日期组织的子目录
│       ├── cat_0001.png
│       └── portrait_0001.png
├── stable-diffusion.cpp/           # stable-diffusion.cpp 源码 (需自行下载编译)

├── run_z_image.sh                  # 主要运行脚本 (Bash)
├── generate.py                     # Python 接口
├── pyproject.toml                  # uv 项目配置
└── README.md                       # 本文件
```

## 环境要求

- macOS (Apple Silicon)
- [uv](https://docs.astral.sh/uv/) - Python 包管理器
- Xcode Command Line Tools

## 快速开始

### 1. 环境准备

项目已配置好虚拟环境和依赖，直接运行即可：

```bash
# 查看虚拟环境状态
source .venv/bin/activate

# 如需重新安装依赖
uv pip install -e .
```

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

手动下载以下模型文件到 `models/` 目录：
- **文本编码器**: [Qwen3-4B-GGUF](https://huggingface.co/unsloth/Qwen3-4B-GGUF) (推荐 Q4_K_M)
- **VAE**: [ae.safetensors](https://huggingface.co/Comfy-Org/z_image_turbo/tree/main/split_files/vae)

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
# 确认模型文件存在
ls models/
```

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
