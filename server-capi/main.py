"""
Z-Image Turbo Web UI - C API Server
基于 stable-diffusion.cpp sd-server 的 FastAPI 服务
"""

import os
import sys
import json
import asyncio
import threading
from pathlib import Path
from datetime import datetime
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, Form, HTTPException, Request, Query
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware

# 添加当前目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from config import (
    PROJECT_ROOT, OUTPUT_DIR, MODELS_DIR,
    DIFFUSION_DIR, VAE_DIR, TEXT_ENCODER_DIR,
    DEFAULT_WIDTH, DEFAULT_HEIGHT, DEFAULT_STEPS,
    DEFAULT_GUIDANCE, DEFAULT_SAMPLING_METHOD, DEFAULT_SCHEDULER,
    get_available_models, ModelConfig
)
from sd_server_client import SDServerClient, GenerateParams, GenerateResult
from process_manager import get_manager, init_manager, SDServerProcessManager


# 确保输出目录存在
OUTPUT_DIR.mkdir(exist_ok=True)

# 任务锁 - 限制同时只有一个生成任务
generate_lock = asyncio.Lock()

# 当前任务信息
current_task_info = {
    "running": False,
    "prompt": "",
    "start_time": None,
}

# 采样方法和调度器选项
SAMPLING_METHODS = [
    "euler", "euler_a", "heun", "dpm2", "dpm++2s_a", "dpm++2m",
    "dpm++2mv2", "ipndm", "ipndm_v", "lcm", "ddim_trailing",
    "tcd", "res_multistep", "res_2s"
]

SCHEDULERS = [
    "discrete", "karras", "exponential", "ays", "gits", "smoothstep",
    "sgm_uniform", "simple", "kl_optimal", "lcm", "bong_tangent"
]


def get_available_diffusion_models() -> list[str]:
    """获取可用的扩散模型列表"""
    models = []
    if DIFFUSION_DIR.exists():
        for ext in ["*.gguf", "*.safetensors"]:
            for f in DIFFUSION_DIR.glob(ext):
                models.append(f.name)
    return models if models else ["z-image-turbo-Q8_0.gguf"]


def get_available_text_encoders() -> list[str]:
    """获取可用的文本编码器列表"""
    encoders = []
    if TEXT_ENCODER_DIR.exists():
        for f in TEXT_ENCODER_DIR.glob("*.gguf"):
            encoders.append(f.name)
    return encoders if encoders else ["Qwen3-4B-Q4_K_M.gguf"]


def get_available_vaes() -> list[str]:
    """获取可用的 VAE 列表"""
    vaes = []
    if VAE_DIR.exists():
        for ext in ["*.safetensors", "*.sft", "*.gguf"]:
            for f in VAE_DIR.glob(ext):
                vaes.append(f.name)
    return vaes if vaes else ["ae.safetensors"]


def get_next_number(prefix: str) -> int:
    """获取下一个可用的编号"""
    max_num = 0
    if OUTPUT_DIR.exists():
        # 处理 %date% 前缀
        if "%date%" in prefix:
            from datetime import datetime
            date_str = datetime.now().strftime("%Y-%m-%d")
            prefix = prefix.replace("%date%", date_str)
        
        # 处理子目录
        if "/" in prefix:
            parts = prefix.rsplit("/", 1)
            search_dir = OUTPUT_DIR / parts[0]
            file_prefix = parts[1]
        else:
            search_dir = OUTPUT_DIR
            file_prefix = prefix
        
        if search_dir.exists():
            for f in search_dir.glob(f"{file_prefix}_*.png"):
                try:
                    num = int(f.stem.rsplit("_", 1)[-1])
                    max_num = max(max_num, num)
                except:
                    pass
    
    return max_num + 1


# 禁用缓存中间件
class NoCacheMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/output"):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response


# 生命周期管理
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    print("[FastAPI] 启动中...")
    
    # 初始化进程管理器
    manager = init_manager()
    
    # 如果有默认模型，自动启动
    models = get_available_models()
    if models:
        print(f"[FastAPI] 准备启动默认模型: {models[0].name}")
        # 在后台线程启动，避免阻塞 FastAPI 启动
        def start_server():
            success = manager.start(models[0], wait_ready=True, timeout=180)
            if success:
                print(f"[FastAPI] sd-server 启动成功")
            else:
                print(f"[FastAPI] sd-server 启动失败，请检查日志")
        
        threading.Thread(target=start_server, daemon=True).start()
    
    yield
    
    # 关闭时
    print("[FastAPI] 关闭中...")
    manager = get_manager()
    manager.shutdown()


app = FastAPI(title="Z-Image Turbo Web UI - C API", lifespan=lifespan)
app.add_middleware(NoCacheMiddleware)

# 挂载静态文件
app.mount("/output", StaticFiles(directory=str(OUTPUT_DIR)), name="output")

# 模板
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """主页"""
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "sampling_methods": SAMPLING_METHODS,
            "schedulers": SCHEDULERS,
            "diffusion_models": get_available_diffusion_models(),
            "text_encoders": get_available_text_encoders(),
            "vaes": get_available_vaes(),
        }
    )


@app.get("/api/models")
async def get_models():
    """获取可用模型列表 API"""
    return {
        "diffusion_models": get_available_diffusion_models(),
        "text_encoders": get_available_text_encoders(),
        "vaes": get_available_vaes(),
        "sampling_methods": SAMPLING_METHODS,
        "schedulers": SCHEDULERS,
        "predefined_models": [m.name for m in get_available_models()],
    }


@app.get("/api/status")
async def get_status():
    """获取服务和任务状态"""
    manager = get_manager()
    server_status = manager.get_status()
    
    return {
        "server": server_status.to_dict(),
        "task": {
            "running": current_task_info["running"],
            "prompt": current_task_info["prompt"] if current_task_info["running"] else None,
            "start_time": current_task_info["start_time"] if current_task_info["running"] else None,
        },
        "healthy": manager.is_healthy(),
    }


@app.post("/api/server/start")
async def start_server(
    diffusion_model: str = Form(...),
    text_encoder: str = Form(...),
    vae: str = Form(...),
):
    """手动启动/重启 sd-server"""
    manager = get_manager()
    
    # 检查是否有任务在运行
    if generate_lock.locked():
        raise HTTPException(status_code=429, detail="有任务正在生成中，请等待完成后再切换模型")
    
    model_config = ModelConfig(
        name=f"{diffusion_model}",
        diffusion_model=diffusion_model,
        text_encoder=text_encoder,
        vae=vae
    )
    
    success = manager.switch_model(model_config)
    
    if not success:
        raise HTTPException(status_code=500, detail="启动 sd-server 失败")
    
    return {"success": True, "message": "服务已启动", "model": model_config.name}


@app.post("/api/server/stop")
async def stop_server():
    """停止 sd-server"""
    manager = get_manager()
    
    if generate_lock.locked():
        raise HTTPException(status_code=429, detail="有任务正在生成中，请等待完成后再停止")
    
    success = manager.stop()
    
    return {"success": success, "message": "服务已停止"}


@app.post("/api/generate")
async def generate_image(
    prompt: str = Form(...),
    diffusion_model: str = Form(...),
    text_encoder: str = Form(...),
    vae: str = Form(...),
    sampling_method: str = Form("euler"),
    scheduler: str = Form("sgm_uniform"),
    steps: int = Form(4),
    width: int = Form(512),
    height: int = Form(512),
    guidance: float = Form(3.5),
    seed: int = Form(-1),
    output_prefix: str = Form("%date%/webui"),
):
    """生成图片 API - 限制同时只有一个任务运行"""
    import traceback
    
    manager = get_manager()
    
    # 检查服务是否健康
    if not manager.is_healthy():
        # 尝试自动启动
        model_config = ModelConfig(
            name=diffusion_model,
            diffusion_model=diffusion_model,
            text_encoder=text_encoder,
            vae=vae
        )
        
        print(f"[API] 服务未运行，尝试自动启动...")
        success = await asyncio.to_thread(
            manager.start, model_config, wait_ready=True, timeout=180
        )
        
        if not success:
            raise HTTPException(status_code=503, detail="sd-server 未运行，自动启动失败，请手动启动")
    
    # 检查模型是否匹配（如果不匹配则切换）
    current_model = manager._current_model
    model_changed = (
        current_model is None or
        current_model.diffusion_model != diffusion_model or
        current_model.text_encoder != text_encoder or
        current_model.vae != vae
    )
    
    if model_changed:
        print(f"[API] 模型配置变更，切换模型...")
        new_config = ModelConfig(
            name=diffusion_model,
            diffusion_model=diffusion_model,
            text_encoder=text_encoder,
            vae=vae
        )
        
        success = await asyncio.to_thread(manager.switch_model, new_config)
        if not success:
            raise HTTPException(status_code=500, detail="切换模型失败")
    
    # 检查是否有任务在运行
    if generate_lock.locked():
        raise HTTPException(
            status_code=429,
            detail="已有任务在运行，请稍后再试。当前任务: " +
                   (current_task_info.get("prompt", "")[:30] + "..." if current_task_info.get("prompt") else "未知")
        )
    
    # 处理输出前缀
    if "%date%" in output_prefix:
        date_str = datetime.now().strftime("%Y-%m-%d")
        output_prefix = output_prefix.replace("%date%", date_str)
    
    # 生成输出路径
    next_num = get_next_number(output_prefix)
    
    if "/" in output_prefix:
        parts = output_prefix.rsplit("/", 1)
        output_dir = OUTPUT_DIR / parts[0]
        file_prefix = parts[1]
    else:
        output_dir = OUTPUT_DIR
        file_prefix = output_prefix
    
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{file_prefix}_{next_num:04d}.png"
    
    async with generate_lock:
        try:
            # 更新任务状态
            current_task_info["running"] = True
            current_task_info["prompt"] = prompt[:50] + "..." if len(prompt) > 50 else prompt
            current_task_info["start_time"] = datetime.now().isoformat()
            
            # 构建生成参数
            gen_params = GenerateParams(
                prompt=prompt,
                width=width,
                height=height,
                steps=steps,
                seed=seed,
                sampling_method=sampling_method,
                scheduler=scheduler,
                guidance=guidance
            )
            
            print(f"[API] 开始生成: {prompt[:50]}...")
            print(f"[API] 输出文件: {output_file}")
            
            # 调用 sd-server 生成
            result = await asyncio.to_thread(
                manager.client.generate,
                gen_params,
                output_file
            )
            
            if not result.success:
                raise HTTPException(status_code=500, detail=result.error or "生成失败")
            
            # 返回结果
            relative_path = output_file.relative_to(PROJECT_ROOT)
            return {
                "success": True,
                "image_url": f"/{relative_path}",
                "filename": output_file.name,
                "full_path": str(output_file),
            }
            
        except HTTPException:
            raise
        except Exception as e:
            error_detail = f"{str(e)}\n{traceback.format_exc()}"
            print(f"[API] 异常: {error_detail}")
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            current_task_info["running"] = False


@app.get("/api/history")
async def get_history(limit: int = Query(20, ge=1, le=100)):
    """获取最近生成的图片历史"""
    images = []
    
    if OUTPUT_DIR.exists():
        # 获取所有 png 文件并按修改时间排序
        png_files = list(OUTPUT_DIR.rglob("*.png"))
        png_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        
        for f in png_files[:limit]:
            try:
                stat = f.stat()
                images.append({
                    "filename": f.name,
                    "path": str(f.relative_to(PROJECT_ROOT)),
                    "url": f"/{f.relative_to(PROJECT_ROOT)}",
                    "created": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "size": stat.st_size,
                })
            except Exception:
                pass
    
    return {"images": images}


@app.delete("/api/history/{filename:path}")
async def delete_image(filename: str):
    """删除生成的图片"""
    # 安全起见，只删除 output 目录下的文件
    file_path = OUTPUT_DIR / filename
    
    # 确保文件在 output 目录内
    try:
        file_path.resolve().relative_to(OUTPUT_DIR.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="无效的文件路径")
    
    if file_path.exists():
        file_path.unlink()
        return {"success": True, "message": "文件已删除"}
    else:
        raise HTTPException(status_code=404, detail="文件不存在")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=11451)
