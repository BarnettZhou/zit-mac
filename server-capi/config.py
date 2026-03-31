"""
sd-server C API 服务配置
"""

from pathlib import Path
from dataclasses import dataclass
from typing import Optional

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.absolute()
OUTPUT_DIR = PROJECT_ROOT / "output"
MODELS_DIR = PROJECT_ROOT / "models"

# 模型子目录
DIFFUSION_DIR = MODELS_DIR / "diffusion_models"
VAE_DIR = MODELS_DIR / "vae"
TEXT_ENCODER_DIR = MODELS_DIR / "text_encoder"

# sd-server 可执行文件路径
SD_SERVER_PATH = PROJECT_ROOT / "stable-diffusion.cpp" / "build" / "bin" / "sd-server"

# 默认服务配置
DEFAULT_SD_SERVER_PORT = 11450
DEFAULT_SD_SERVER_HOST = "127.0.0.1"

# 默认生成参数
DEFAULT_WIDTH = 512
DEFAULT_HEIGHT = 512
DEFAULT_STEPS = 4
DEFAULT_GUIDANCE = 3.5
DEFAULT_SAMPLING_METHOD = "euler"
DEFAULT_SCHEDULER = "sgm_uniform"


@dataclass
class ModelConfig:
    """模型配置"""
    diffusion_model: str
    text_encoder: str
    vae: str
    name: Optional[str] = None
    
    def __post_init__(self):
        if self.name is None:
            self.name = self.diffusion_model


# 预定义的模型配置（可从配置文件加载）
DEFAULT_MODELS = [
    ModelConfig(
        name="z-image-turbo-q8",
        diffusion_model="z-image-turbo-Q8_0.gguf",
        text_encoder="Qwen3-4B-Q4_K_M.gguf",
        vae="ae.safetensors"
    ),
]


def get_available_models() -> list[ModelConfig]:
    """扫描模型目录获取可用模型"""
    models = []
    
    if DIFFUSION_DIR.exists():
        for gguf_file in DIFFUSION_DIR.glob("*.gguf"):
            name = gguf_file.stem
            models.append(ModelConfig(
                name=name,
                diffusion_model=gguf_file.name,
                text_encoder="Qwen3-4B-Q4_K_M.gguf",  # 默认文本编码器
                vae="ae.safetensors"  # 默认 VAE
            ))
    
    return models if models else DEFAULT_MODELS


def build_sd_server_args(
    model_config: ModelConfig,
    host: str = DEFAULT_SD_SERVER_HOST,
    port: int = DEFAULT_SD_SERVER_PORT,
    verbose: bool = False
) -> list[str]:
    """构建 sd-server 启动参数"""
    args = [
        str(SD_SERVER_PATH),
        "-l", host,
        "--listen-port", str(port),
        "--diffusion-model", str(DIFFUSION_DIR / model_config.diffusion_model),
        "--llm", str(TEXT_ENCODER_DIR / model_config.text_encoder),
        "--vae", str(VAE_DIR / model_config.vae),
        "-W", str(DEFAULT_WIDTH),
        "-H", str(DEFAULT_HEIGHT),
        "-s", str(DEFAULT_STEPS),
        "--sampling-method", DEFAULT_SAMPLING_METHOD,
        "--scheduler", DEFAULT_SCHEDULER,
        "--guidance", str(DEFAULT_GUIDANCE),
    ]
    
    if verbose:
        args.append("--verbose")
    
    return args
