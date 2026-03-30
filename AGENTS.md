# AGENTS.md - Z-Image Turbo GGUF 文生图 Demo

> 本文件面向 AI 编程助手，提供项目架构、技术栈和开发约定的完整说明。

## 项目概述

本项目是在 Apple Silicon Mac 上运行 Z-Image Turbo 量化模型的文生图 (Text-to-Image) 演示环境。它通过 stable-diffusion.cpp 利用 Metal GPU 加速进行本地 AI 图像生成。

### 核心特性

- **模型架构**: S3-DiT (Scalable Single-Stream Diffusion Transformer)
- **加速技术**: Metal GPU 加速 + GGUF 8-bit 量化
- **少步推理**: Turbo 变体仅需 4-8 步即可生成高质量图像
- **运行平台**: Apple Silicon Mac (M3 Pro 等)

## 技术栈

| 组件 | 技术 |
|------|------|
| 包管理器 | [uv](https://docs.astral.sh/uv/) (Python 3.11+) |
| 深度学习后端 | stable-diffusion.cpp (C++ / Metal) |
| 前端接口 | Python 3 + Bash |
| 模型格式 | GGUF (量化)、Safetensors |

### Python 依赖

```toml
torch>=2.0.0
torchvision>=0.15.0
pillow>=10.0.0
tqdm>=4.65.0
```

## 项目结构

```
.
├── models/                          # 模型文件目录
│   ├── z-image-turbo-Q8_0.gguf     # DiT 扩散模型 (已包含)
│   ├── Qwen3-4B-Q4_K_M.gguf        # 文本编码器 (已包含)
│   ├── ae.safetensors              # VAE 解码器 (已包含)
│   └── flux-ae.sft                 # 备选 VAE (可选)
├── output/                          # 输出目录 (自动生成，被 gitignore)
├── stable-diffusion.cpp/           # 外部依赖：需自行克隆编译
│   └── build/bin/sd-cli            # 编译后的可执行文件
├── run_z_image.sh                  # 主运行脚本 (Bash)
├── generate.py                     # Python 接口包装器
├── pyproject.toml                  # uv 项目配置
├── uv.lock                         # uv 锁定文件
├── README.md                       # 用户文档 (中文)
└── AGENTS.md                       # 本文件
```

## 核心文件说明

### 1. run_z_image.sh (主脚本)

Bash 脚本，直接调用 `sd-cli` 可执行文件进行图像生成。

**关键路径（硬编码）**:
- DiT 模型: `models/z-image-turbo-Q8_0.gguf`
- 文本编码器: `models/Qwen3-4B-Q4_K_M.gguf`
- VAE: `models/ae.safetensors`
- sd-cli: `stable-diffusion.cpp/build/bin/sd-cli`

**主要功能**:
- 命令行参数解析
- `%date%` 占位符替换为当前日期 (YYYY-MM-DD)
- 自动编号输出文件 (如 `cat_0001.png`, `cat_0002.png`)
- 子目录自动创建

**默认参数**:
- 尺寸: 512x512
- 步数: 4
- 采样方法: `res_multistep`
- Guidance: 3.5
- CFG Scale: 1.0 (Turbo 模型固定值)

### 2. generate.py (Python 接口)

Python 包装器，提供与 `run_z_image.sh` 相同的功能。

**设计模式**:
- 参数解析后调用 `run_z_image.sh` (subprocess)
- 不直接调用 sd-cli，而是通过 shell 脚本中转

**主要函数**:
- `process_prefix()`: 处理前缀路径、日期替换、自动编号
- `main()`: 参数解析和脚本调用

### 3. pyproject.toml (项目配置)

```toml
[project]
name = "z-image-turbo-demo"
version = "0.1.0"
description = "Z-Image Turbo GGUF 文生图 Demo for Apple Silicon Mac"
requires-python = ">=3.11"
```

## 构建和运行

### 环境准备

```bash
# 1. 确保 uv 已安装
which uv

# 2. 虚拟环境已配置 (项目已包含 .venv)
source .venv/bin/activate

# 3. 如需重新安装依赖
uv pip install -e .
```

### 编译 stable-diffusion.cpp (必需的外部依赖)

```bash
# 克隆仓库
git clone --recursive https://github.com/leejet/stable-diffusion.cpp.git

# 编译 (Apple Silicon Mac)
cd stable-diffusion.cpp
cmake -B build -DSD_METAL=ON
cmake --build build -j8

# 可执行文件位置: stable-diffusion.cpp/build/bin/sd-cli
```

### 运行方式

**方式 1: Bash 脚本 (推荐)**
```bash
./run_z_image.sh -p "a beautiful sunset" --prefix "%date%/sunset"
```

**方式 2: Python 接口**
```bash
uv run generate.py -p "a beautiful sunset" --prefix "%date%/sunset"
# 或
python generate.py -p "a beautiful sunset" --prefix "%date%/sunset"
```

**常用参数**:
| 参数 | 说明 | 示例 |
|------|------|------|
| `-p, --prompt` | 文本提示词 (必需) | `"cute cat"` |
| `--prefix` | 输出前缀，支持 `%date%` 和子目录 | `"%date%/cats/cat"` |
| `-W, -H` | 图像尺寸 | `-W 1024 -H 1024` |
| `-s, --steps` | 推理步数 (Turbo 推荐 4-8) | `-s 8` |
| `--sampling-method` | 采样方法 | `--sampling-method euler` |
| `--scheduler` | 调度器 | `--scheduler sgm_uniform` |
| `--guidance` | 蒸馏引导尺度 (2.5-5.0) | `--guidance 4.0` |

## 代码风格和约定

### 文件命名

- 脚本文件: 小写，下划线分隔 (e.g., `run_z_image.sh`)
- 模型文件: 保留原始下载名称
- 输出文件: `{prefix}_{0001}.png` (自动编号)

### 代码规范

**Python**:
- 使用类型注解 (如 `def process_prefix(prefix: str, output_base: Path) -> Path`)
- 文档字符串使用中文（与用户文档一致）
- 遵循 PEP 8

**Bash**:
- 使用 `set -e` 确保错误时退出
- 函数定义使用 `function_name() { ... }`
- 局部变量使用 `local` 关键字

### 注释风格

- 文件头部包含功能描述和使用示例
- 函数/复杂逻辑使用中文注释
- 关键配置项（如模型路径）保持明确注释

## 模型架构说明

### 组件分工

| 组件 | 文件 | 作用 |
|------|------|------|
| DiT 模型 | `z-image-turbo-Q8_0.gguf` | 处理扩散过程的 Transformer |
| 文本编码器 | `Qwen3-4B-Q4_K_M.gguf` | 将提示词编码为嵌入向量 (Qwen3-4B) |
| VAE | `ae.safetensors` | 将潜在空间解码为图像 |

### Turbo 模型特殊配置

- **CFG Scale 必须设为 1.0**: Turbo 模型不需要传统分类器引导
- **Guidance 参数**: 控制提示词遵循程度
  - `3.0-3.5`: 自然质感，适合风景
  - `4.0-4.5`: 强提示词遵循，适合人物/复杂场景
- **推荐步数**: 4-8 步

## Git 和版本控制

### .gitignore 关键规则

```gitignore
# 模型文件 (大文件)
models/*.gguf
models/*.safetensors
!models/.gitkeep

# 输出目录
output/

# 生成图片
*.png
*.jpg

# 外部依赖 (需手动下载)
stable-diffusion.cpp/

# uv
uv.lock
```

**注意**: 当前 `models/` 目录中的模型文件实际上已存在，但 `.gitignore` 配置表明它们不应被提交到 Git。这是预期行为——模型文件通常通过 Git LFS 或其他方式单独管理。

## 故障排除指南

### 常见问题

**1. 找不到 sd-cli**
```
错误: 找不到 sd-cli 可执行文件
```
- 解决: 编译 stable-diffusion.cpp (见上文)

**2. 缺少模型文件**
- 确认 `models/` 目录包含:
  - `z-image-turbo-Q8_0.gguf` 或类似 GGUF 文件
  - `Qwen3-4B-Q4_K_M.gguf`
  - `ae.safetensors`

**3. 内存不足**
- 减小图像尺寸: `-W 512 -H 512`
- 确保使用 GGUF 量化模型
- 使用更小的文本编码器

**4. 生成结果异常**
- 确保 CFG Scale = 1.0 (脚本已默认设置)
- 尝试调整 guidance: `--guidance 4.0`
- 使用推荐采样组合: `--sampling-method euler --scheduler sgm_uniform`

## 参考链接

- [Z-Image Turbo HuggingFace](https://huggingface.co/unsloth/Z-Image-Turbo-GGUF)
- [Qwen3-4B-GGUF](https://huggingface.co/unsloth/Qwen3-4B-GGUF)
- [ComfyUI Z-Image VAE](https://huggingface.co/Comfy-Org/z_image_turbo/tree/main/split_files/vae)
- [stable-diffusion.cpp](https://github.com/leejet/stable-diffusion.cpp)
- [Z-Image 论文](https://arxiv.org/abs/2511.22699)

## 修改注意事项

1. **模型路径**: 如需更换模型版本，需同时修改 `run_z_image.sh` 中的硬编码路径
2. **输出组织**: `%date%` 占位符和自动编号逻辑在两个文件中重复实现（`run_z_image.sh` 和 `generate.py`），修改时需保持同步
3. **stable-diffusion.cpp 路径**: 项目依赖特定目录结构，不要重命名 `stable-diffusion.cpp` 目录
