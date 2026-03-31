# Z-Image Turbo C API Server

基于 stable-diffusion.cpp 内置 sd-server 的 FastAPI Web UI 服务。

## 特性

- ✅ **模型常驻内存** - 首次加载后，后续生成无需重复加载模型
- ✅ **进程管理** - 自动启动/停止/重启 sd-server 进程
- ✅ **模型热切换** - 支持在 Web UI 中切换不同模型（自动重启服务）
- ✅ **健康检查** - 实时监控 sd-server 状态
- ✅ **任务队列** - 单任务限制，避免并发问题
- ✅ **OpenAI 兼容 API** - `/v1/images/generations` 标准接口

## 架构

```
┌─────────────┐     ┌─────────────────────┐     ┌──────────────┐
│   Web UI    │────▶│  FastAPI (Python)   │────▶│   sd-server  │
│  (浏览器)    │     │  (./server-capi)    │     │  (C++ 进程)   │
└─────────────┘     └─────────────────────┘     └──────────────┘
                              │                          │
                              ▼                          ▼
                    ┌─────────────────┐         ┌──────────────┐
                    │  进程管理器      │         │  模型常驻内存 │
                    │  (启动/停止/重启)│         │  (加载一次)   │
                    └─────────────────┘         └──────────────┘
```

## 使用方法

### 1. 编译 sd-server

```bash
cd stable-diffusion.cpp
cmake -B build -DSD_METAL=ON -DSD_BUILD_SERVER=ON
cmake --build build -j8
```

### 2. 启动服务

```bash
# 使用 uv
uv run server-capi/start_server.py

# 或使用 Python
python server-capi/start_server.py

# 指定端口
python server-capi/start_server.py --port 8080 --sd-port 11450
```

### 3. 访问 Web UI

打开浏览器访问: http://localhost:11451

## API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/` | GET | Web UI 主页 |
| `/api/status` | GET | 获取服务状态 |
| `/api/models` | GET | 获取可用模型列表 |
| `/api/generate` | POST | 生成图片 |
| `/api/server/start` | POST | 启动/切换 sd-server |
| `/api/server/stop` | POST | 停止 sd-server |
| `/api/history` | GET | 获取历史图片 |
| `/api/history/{filename}` | DELETE | 删除图片 |

## 配置

模型目录结构：

```
models/
├── diffusion_models/    # 扩散模型 (.gguf, .safetensors)
│   └── z-image-turbo-Q8_0.gguf
├── text_encoder/        # 文本编码器 (.gguf)
│   └── Qwen3-4B-Q4_K_M.gguf
└── vae/                 # VAE (.safetensors, .sft)
    └── ae.safetensors
```

## 与旧版对比

| 特性 | 旧版 (./server) | 新版 (./server-capi) |
|------|-----------------|---------------------|
| 模型加载 | 每次请求重新加载 | 常驻内存 |
| 首次生成 | 30-60 秒 | 5-10 秒 |
| 后续生成 | 30-60 秒 | 5-10 秒 |
| 进程管理 | 无 | 自动管理 |
| 内存占用 | 低（临时） | 高（常驻） |

## 注意事项

1. **内存要求** - 模型常驻内存需要约 2-6GB 内存（取决于模型大小）
2. **单任务限制** - 同一时间只能处理一个生成请求
3. **模型切换** - 切换模型需要重启 sd-server，耗时约 10-30 秒
4. **端口占用** - sd-server 默认使用 11450 端口，确保未被占用

## 故障排除

### sd-server 启动失败

```bash
# 检查 sd-server 是否存在
ls -la stable-diffusion.cpp/build/bin/sd-server

# 手动启动测试
./stable-diffusion.cpp/build/bin/sd-server \
    --diffusion-model models/diffusion_models/z-image-turbo-Q8_0.gguf \
    --llm models/text_encoder/Qwen3-4B-Q4_K_M.gguf \
    --vae models/vae/ae.safetensors
```

### 端口被占用

```bash
# 查找占用 11450 端口的进程
lsof -i :11450

# 或修改 sd-server 端口
python server-capi/start_server.py --sd-port 1235
```
