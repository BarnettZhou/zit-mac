"""
sd-server HTTP 客户端
提供与 sd-server 的通信接口
"""

import base64
import io
import json
import time
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

import requests
from PIL import Image


@dataclass
class GenerateParams:
    """生成参数"""
    prompt: str
    width: int = 512
    height: int = 512
    steps: int = 4
    seed: int = -1
    sampling_method: str = "euler"
    scheduler: str = "sgm_uniform"
    guidance: float = 3.5
    cfg_scale: float = 1.0
    output_format: str = "png"


@dataclass
class GenerateResult:
    """生成结果"""
    success: bool
    image_path: Optional[Path] = None
    filename: Optional[str] = None
    image_url: Optional[str] = None
    error: Optional[str] = None
    seed_used: Optional[int] = None


class SDServerClient:
    """
    stable-diffusion.cpp server 客户端
    
    提供与 sd-server HTTP API 的交互接口
    """
    
    def __init__(self, base_url: str = "http://127.0.0.1:11450", timeout: int = 300):
        """
        初始化客户端
        
        Args:
            base_url: sd-server 地址
            timeout: 请求超时时间（秒）
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self._session = requests.Session()
    
    def health_check(self) -> bool:
        """检查服务是否健康"""
        try:
            # 尝试访问根路径
            response = self._session.get(
                f"{self.base_url}/",
                timeout=5
            )
            return response.status_code == 200
        except Exception:
            return False
    
    def get_models(self) -> list[dict]:
        """获取可用模型列表"""
        try:
            response = self._session.get(
                f"{self.base_url}/v1/models",
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            return data.get("data", [])
        except Exception as e:
            print(f"[SDServerClient] 获取模型列表失败: {e}")
            return []
    
    def get_loras(self) -> list[dict]:
        """获取可用 LoRA 列表"""
        try:
            response = self._session.get(
                f"{self.base_url}/v1/loras",
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            return data.get("data", [])
        except Exception as e:
            print(f"[SDServerClient] 获取 LoRA 列表失败: {e}")
            return []
    
    def generate(
        self,
        params: GenerateParams,
        output_path: Path,
        progress_callback: Optional[callable] = None
    ) -> GenerateResult:
        """
        生成图片
        
        Args:
            params: 生成参数
            output_path: 输出图片路径
            progress_callback: 进度回调函数(step, total_steps)
        
        Returns:
            GenerateResult: 生成结果
        """
        try:
            # 构建额外参数 JSON
            extra_args = {
                "sample_steps": params.steps,
                "sample_method": params.sampling_method,
                "scheduler": params.scheduler,
                "guidance": params.guidance,
                "cfg_scale": params.cfg_scale,
                "width": params.width,
                "height": params.height,
            }
            
            # 添加种子（如果指定）
            if params.seed >= 0:
                extra_args["seed"] = params.seed
            
            # 将参数嵌入提示词（sd-server 的特殊格式）
            extra_args_json = json.dumps(extra_args, separators=(',', ':'))
            prompt_with_args = f'{params.prompt} <sd_cpp_extra_args>{extra_args_json}</sd_cpp_extra_args>'
            
            # 准备请求
            request_data = {
                "prompt": prompt_with_args,
                "n": 1,
                "size": f"{params.width}x{params.height}",
                "output_format": params.output_format,
                "output_compression": 100
            }
            
            print(f"[SDServerClient] 发送生成请求: {params.prompt[:50]}...")
            start_time = time.time()
            
            # 发送请求
            response = self._session.post(
                f"{self.base_url}/v1/images/generations",
                json=request_data,
                timeout=self.timeout
            )
            
            elapsed = time.time() - start_time
            print(f"[SDServerClient] 请求完成，耗时: {elapsed:.2f}s")
            
            # 检查响应
            if response.status_code != 200:
                error_msg = f"HTTP {response.status_code}"
                try:
                    error_data = response.json()
                    if "error" in error_data:
                        error_msg = error_data["error"]
                    elif "message" in error_data:
                        error_msg = error_data["message"]
                except:
                    error_msg = response.text[:200]
                
                return GenerateResult(
                    success=False,
                    error=f"生成失败: {error_msg}"
                )
            
            # 解析响应
            data = response.json()
            
            if "data" not in data or not data["data"]:
                return GenerateResult(
                    success=False,
                    error="响应中没有图片数据"
                )
            
            # 解码 Base64 图片
            b64_image = data["data"][0].get("b64_json")
            if not b64_image:
                return GenerateResult(
                    success=False,
                    error="响应中缺少图片数据"
                )
            
            # 解码并保存图片
            image_data = base64.b64decode(b64_image)
            image = Image.open(io.BytesIO(image_data))
            
            # 确保输出目录存在
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 保存图片
            image.save(output_path)
            
            return GenerateResult(
                success=True,
                image_path=output_path,
                filename=output_path.name,
                image_url=f"/{output_path.relative_to(output_path.parent.parent)}"
            )
            
        except requests.exceptions.Timeout:
            return GenerateResult(
                success=False,
                error=f"请求超时（超过 {self.timeout} 秒）"
            )
        except requests.exceptions.ConnectionError:
            return GenerateResult(
                success=False,
                error="无法连接到 sd-server，请检查服务是否已启动"
            )
        except Exception as e:
            import traceback
            print(f"[SDServerClient] 生成异常: {e}")
            print(traceback.format_exc())
            return GenerateResult(
                success=False,
                error=f"生成异常: {str(e)}"
            )
    
    def img2img(
        self,
        image_path: Path,
        params: GenerateParams,
        output_path: Path,
        strength: float = 0.75
    ) -> GenerateResult:
        """
        图生图
        
        Args:
            image_path: 输入图片路径
            params: 生成参数
            output_path: 输出图片路径
            strength: 重绘强度 (0.0-1.0)
        
        Returns:
            GenerateResult: 生成结果
        """
        try:
            # 读取并编码图片
            with open(image_path, "rb") as f:
                image_data = f.read()
            
            # 构建请求
            files = {
                "image": (image_path.name, image_data, "image/png")
            }
            
            data = {
                "prompt": params.prompt,
                "strength": str(strength),
            }
            
            # 发送请求
            response = self._session.post(
                f"{self.base_url}/v1/images/edits",
                files=files,
                data=data,
                timeout=self.timeout
            )
            
            if response.status_code != 200:
                return GenerateResult(
                    success=False,
                    error=f"图生图失败: HTTP {response.status_code}"
                )
            
            # 解析并保存
            result_data = response.json()
            b64_image = result_data["data"][0].get("b64_json")
            
            if not b64_image:
                return GenerateResult(
                    success=False,
                    error="响应中缺少图片数据"
                )
            
            # 解码并保存
            image_data = base64.b64decode(b64_image)
            image = Image.open(io.BytesIO(image_data))
            
            output_path.parent.mkdir(parents=True, exist_ok=True)
            image.save(output_path)
            
            return GenerateResult(
                success=True,
                image_path=output_path,
                filename=output_path.name,
                image_url=f"/{output_path.relative_to(output_path.parent.parent)}"
            )
            
        except Exception as e:
            return GenerateResult(
                success=False,
                error=f"图生图异常: {str(e)}"
            )
