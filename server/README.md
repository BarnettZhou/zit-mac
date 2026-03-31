# Web UI Server (Legacy)

基于 FastAPI 的 Web 界面，通过调用 `run_z_image.sh` 脚本进行图像生成。

## 概述

这是项目的原始 Web UI 实现，使用 subprocess 调用命令行工具生成图片。每次请求都需要重新加载模型，适合简单的使用场景。

**注意**：如需更好的性能（模型常驻内存），请使用 [server-capi](../server-capi/)。

## 架构

```
浏览器 → FastAPI → run_z_image.sh → sd-cli (每次请求重新加载模型)
```

## 启动服务

```bash
# 方式1：使用 uv
uv run python server/main.py

# 方式2：使用 python
source .venv/bin/activate
python server/main.py
```

服务启动后，打开浏览器访问：**http://localhost:11451**

## 功能特性

- 🎨 **可视化配置**：支持选择 Diffusion 模型、采样方法、调度器等
- 🖼️ **实时预览**：生成完成后直接在网页展示图片
- ⬇️ **一键下载**：生成的图片可直接下载保存
- 📱 **响应式设计**：支持桌面和移动端访问
- 📂 **自动编号**：按日期组织输出文件，自动递增编号

## API 接口

### 获取可用模型列表

```bash
curl http://localhost:11451/api/models
```

### 生成图片

```bash
curl -X POST http://localhost:11451/api/generate \
  -F "prompt=a beautiful sunset" \
  -F "diffusion_model=z-image-turbo-Q8_0.gguf" \
  -F "text_encoder=Qwen3-4B-Q4_K_M.gguf" \
  -F "vae=ae.safetensors" \
  -F "width=512" \
  -F "height=512" \
  -F "steps=4" \
  -F "sampling_method=euler" \
  -F "scheduler=sgm_uniform" \
  -F "guidance=3.5" \
  -F "seed=-1" \
  -F "output_prefix=%date%/webui"
```

### 获取服务状态

```bash
curl http://localhost:11451/api/status
```

### 获取历史图片

```bash
curl http://localhost:11451/api/history?limit=20
```

### 删除图片

```bash
curl -X DELETE http://localhost:11451/api/history/webui_0001.png
```

## 与 server-capi 的对比

| 特性 | server (本目录) | server-capi |
|------|----------------|-------------|
| 模型加载 | 每次请求重新加载 | 常驻内存 |
| 首次生成延迟 | 30-60 秒 | 5-10 秒 |
| 后续生成延迟 | 30-60 秒 | 5-10 秒 |
| 内存占用 | 低（临时） | 高（常驻） |
| 进程管理 | 无 | 自动管理 |
| 模型切换 | 无需重启 | 需要重启服务 |
| 适用场景 | 偶尔使用 | 频繁使用 |

## 文件说明

- `main.py` - FastAPI 应用主文件
- `templates/index.html` - Web UI 页面模板

## 注意事项

1. 同一时间只能处理一个生成请求（单任务限制）
2. 模型切换不需要重启服务（因为每次请求都重新加载）
3. 确保 `run_z_image.sh` 和 `stable-diffusion.cpp` 已正确配置
