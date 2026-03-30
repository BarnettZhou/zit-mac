"""
Z-Image Turbo Web UI - FastAPI 服务端
端口: 11451
"""

import os
import sys
import json
import uuid
import asyncio
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.absolute()
OUTPUT_DIR = PROJECT_ROOT / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# 模型目录
MODELS_DIR = PROJECT_ROOT / "models"
DIFFUSION_DIR = MODELS_DIR / "diffusion_models"
VAE_DIR = MODELS_DIR / "vae"
TEXT_ENCODER_DIR = MODELS_DIR / "text_encoder"

app = FastAPI(title="Z-Image Turbo Web UI")

# 挂载静态文件
app.mount("/output", StaticFiles(directory=str(OUTPUT_DIR)), name="output")

# 模板
templates = Jinja2Templates(directory=str(PROJECT_ROOT / "server" / "templates"))


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
        for f in DIFFUSION_DIR.glob("*.gguf"):
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
    }


@app.get("/api/status")
async def get_status():
    """获取当前任务状态"""
    return {
        "running": generate_lock.locked(),
        "task": current_task_info if generate_lock.locked() else None,
    }


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
    output_prefix: str = Form("webui"),
):
    """生成图片 API - 限制同时只有一个任务运行"""
    import traceback
    
    # 检查是否有任务在运行
    if generate_lock.locked():
        raise HTTPException(
            status_code=429, 
            detail="已有任务在运行，请稍后再试。当前任务: " + 
                   (current_task_info.get("prompt", "")[:30] + "..." if current_task_info.get("prompt") else "未知")
        )
    
    # 使用前缀作为输出名称（run_z_image.sh 会处理自动递增编号）
    output_name = output_prefix
    
    # 构建命令
    script_path = PROJECT_ROOT / "run_z_image.sh"
    
    cmd = [
        str(script_path),
        "-p", prompt,
        "--prefix", output_name,
        "-W", str(width),
        "-H", str(height),
        "-s", str(steps),
        "--seed", str(seed),
        "--sampling-method", sampling_method,
        "--guidance", str(guidance),
    ]
    
    if scheduler:
        cmd.extend(["--scheduler", scheduler])
    
    # 临时修改环境变量以使用选定的模型
    env = os.environ.copy()
    # 注意：这里我们依赖 run_z_image.sh 使用新的目录结构
    # 如果用户选择的模型文件名与默认不同，需要特殊处理
    
    print(f"[DEBUG] 执行命令: {' '.join(cmd)}")
    print(f"[DEBUG] 工作目录: {PROJECT_ROOT}")
    
    # 更新任务状态
    current_task_info["running"] = True
    current_task_info["prompt"] = prompt[:50] + "..." if len(prompt) > 50 else prompt
    current_task_info["start_time"] = datetime.now().isoformat()
    
    async with generate_lock:
        try:
            # 运行生成脚本
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                cwd=str(PROJECT_ROOT)
            )
            
            stdout, stderr = await process.communicate()
            
            stdout_str = stdout.decode() if stdout else ""
            stderr_str = stderr.decode() if stderr else ""
            
            print(f"[DEBUG] 返回码: {process.returncode}")
            print(f"[DEBUG] stdout: {stdout_str}")
            print(f"[DEBUG] stderr: {stderr_str}")
            
            if process.returncode != 0:
                error_msg = stderr_str if stderr_str else stdout_str if stdout_str else "生成失败"
                print(f"[ERROR] 生成失败: {error_msg}")
                raise HTTPException(status_code=500, detail=f"生成失败: {error_msg}")
            
            # 查找生成的文件
            output_file = None
            
            # 尝试不同的编号查找文件
            for i in range(1, 100):
                potential_path = OUTPUT_DIR / f"{output_name}_{i:04d}.png"
                if potential_path.exists():
                    output_file = potential_path
                    break
            
            if not output_file or not output_file.exists():
                # 尝试直接在 output 目录查找
                for f in OUTPUT_DIR.glob(f"{output_name}_*.png"):
                    output_file = f
                    break
            
            if not output_file or not output_file.exists():
                print(f"[ERROR] 生成的文件未找到，output_name: {output_name}")
                print(f"[DEBUG] output 目录内容: {list(OUTPUT_DIR.glob('*.png'))}")
                raise HTTPException(status_code=500, detail="生成的文件未找到")
            
            print(f"[DEBUG] 找到生成文件: {output_file}")
            
            # 返回图片 URL
            relative_path = output_file.relative_to(PROJECT_ROOT)
            return {
                "success": True,
                "image_url": f"/{relative_path}",
                "filename": output_file.name,
            }
            
        except HTTPException:
            raise
        except Exception as e:
            error_detail = f"{str(e)}\n{traceback.format_exc()}"
            print(f"[ERROR] 异常: {error_detail}")
            raise HTTPException(status_code=500, detail=error_detail)
        finally:
            current_task_info["running"] = False


@app.get("/api/history")
async def get_history(limit: int = 20):
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


@app.delete("/api/history/{filename}")
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
