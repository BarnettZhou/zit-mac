#!/usr/bin/env python3
"""
Z-Image Turbo GGUF 文生图 Python 接口
适用于 Apple Silicon Mac (M3 Pro)

使用示例:
    # 基础用法 (保存到 output/output_0001.png)
    uv run generate.py -p "a beautiful sunset"

    # 使用前缀 (保存到 output/cat_0001.png)
    uv run generate.py -p "cute cat" --prefix "cat"

    # 使用子目录 (保存到 output/aa/cat_0001.png)
    uv run generate.py -p "cute cat" --prefix "aa/cat"

    # 使用日期子目录 (保存到 output/2026-03-29/cat_0001.png)
    uv run generate.py -p "cute cat" --prefix "%date%/cat"

    # 使用 euler + sgm_uniform 组合
    uv run generate.py -p "portrait" --prefix "%date%/portrait" --sampling-method euler --scheduler sgm_uniform

    # 高分辨率 + 更多步数
    uv run generate.py -p "landscape" --prefix "%date%/landscape" -W 1024 -H 1024 -s 8 --seed 42
"""

import subprocess
import argparse
import sys
from pathlib import Path
from datetime import datetime


def process_prefix(prefix: str, output_base: Path) -> Path:
    """
    处理前缀，替换 %date% 并确保目录存在
    返回完整输出路径
    """
    current_date = datetime.now().strftime("%Y-%m-%d")
    
    # 替换 %date% 为当前日期
    prefix = prefix.replace("%date%", current_date)
    
    # 构建完整输出目录
    if "/" in prefix or prefix.endswith("/"):
        # 包含目录分隔符
        full_output_dir = output_base / prefix
        # 如果 prefix 以 / 结尾，表示只有目录，使用默认文件名
        if prefix.endswith("/"):
            file_prefix = "output"
            full_output_dir = output_base / prefix.rstrip("/")
        else:
            # 分离目录和文件名前缀
            parts = prefix.rsplit("/", 1)
            if len(parts) == 2 and parts[0]:
                full_output_dir = output_base / parts[0]
                file_prefix = parts[1]
            else:
                full_output_dir = output_base
                file_prefix = parts[-1]
    else:
        # 没有目录，只有文件名前缀
        full_output_dir = output_base
        file_prefix = prefix
    
    # 创建目录
    full_output_dir.mkdir(parents=True, exist_ok=True)
    
    # 查找下一个可用的编号
    next_num = 1
    while True:
        output_file = full_output_dir / f"{file_prefix}_{next_num:04d}.png"
        if not output_file.exists():
            break
        next_num += 1
    
    return output_file


def main():
    parser = argparse.ArgumentParser(
        description="Z-Image Turbo GGUF 文生图工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
采样方法 (--sampling-method):
  euler, euler_a, heun, dpm2, dpm++2s_a, dpm++2m, dpm++2mv2,
  ipndm, ipndm_v, lcm, ddim_trailing, tcd, res_multistep, res_2s

调度器 (--scheduler):
  discrete, karras, exponential, ays, gits, smoothstep,
  sgm_uniform, simple, kl_optimal, lcm, bong_tangent

前缀 (--prefix) 说明:
  - 支持 %date% 占位符，会被替换为当前日期 (如 2026-03-29)
  - 支持子目录，如 "aa/cat" 会创建 aa 子目录
  - 最终文件名格式: {prefix}_0001.png (自动递增)

示例:
  uv run generate.py -p "a cat" --prefix "cat"
  uv run generate.py -p "a cat" --prefix "aa/cat"
  uv run generate.py -p "a cat" --prefix "%date%/cat"
        """
    )
    
    # 基本参数
    parser.add_argument(
        "-p", "--prompt",
        type=str,
        required=True,
        help="文本提示词 (必需)"
    )
    parser.add_argument(
        "--prefix",
        type=str,
        default="output",
        help="输出文件前缀 (默认: output)，支持 %%date%% 占位符和子目录"
    )
    parser.add_argument(
        "-W", "--width",
        type=int,
        default=512,
        help="图像宽度 (默认: 512)"
    )
    parser.add_argument(
        "-H", "--height",
        type=int,
        default=512,
        help="图像高度 (默认: 512)"
    )
    parser.add_argument(
        "-s", "--steps",
        type=int,
        default=4,
        help="推理步数 (默认: 4, Turbo推荐4-8)"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=-1,
        help="随机种子 (默认: 随机)"
    )
    
    # 采样参数
    parser.add_argument(
        "--sampling-method",
        type=str,
        default="res_multistep",
        help="采样方法 (默认: res_multistep)"
    )
    parser.add_argument(
        "--scheduler",
        type=str,
        default=None,
        help="调度器 (默认: simple)"
    )
    parser.add_argument(
        "--guidance",
        type=float,
        default=3.5,
        help="蒸馏引导尺度 (默认: 3.5, 建议范围: 2.5-5.0)"
    )
    
    args = parser.parse_args()
    
    script_dir = Path(__file__).parent.absolute()
    output_base = script_dir / "output"
    
    # 处理前缀，获取完整输出路径
    output_file = process_prefix(args.prefix, output_base)
    
    # 调用 shell 脚本
    cmd = [
        str(script_dir / "run_z_image.sh"),
        "-p", args.prompt,
        "--prefix", args.prefix,
        "-W", str(args.width),
        "-H", str(args.height),
        "-s", str(args.steps),
        "--seed", str(args.seed),
        "--sampling-method", args.sampling_method,
        "--guidance", str(args.guidance),
    ]
    
    # 如果指定了调度器，添加参数
    if args.scheduler:
        cmd.extend(["--scheduler", args.scheduler])
    
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"错误: 生成失败 (返回码 {e.returncode})")
        sys.exit(1)
    except FileNotFoundError:
        print("错误: 找不到 run_z_image.sh 脚本")
        sys.exit(1)


if __name__ == "__main__":
    main()
