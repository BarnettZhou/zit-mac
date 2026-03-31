#!/usr/bin/env python3
"""
Z-Image Turbo C API Server 启动脚本
"""

import os
import sys
import argparse
from pathlib import Path

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent.absolute()
sys.path.insert(0, str(PROJECT_ROOT))

import uvicorn


def main():
    parser = argparse.ArgumentParser(description="Z-Image Turbo C API Server")
    parser.add_argument("--host", default="0.0.0.0", help="监听地址 (默认: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=11451, help="监听端口 (默认: 11451)")
    parser.add_argument("--sd-port", type=int, default=11450, help="sd-server 端口 (默认: 11450)")
    parser.add_argument("--no-auto-start", action="store_true", help="不自动启动 sd-server")
    parser.add_argument("--reload", action="store_true", help="开发模式：自动重载")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("🎨 Z-Image Turbo C API Server")
    print("=" * 60)
    print(f"Python: {sys.executable}")
    print(f"项目目录: {PROJECT_ROOT}")
    print(f"服务地址: http://{args.host}:{args.port}")
    print(f"sd-server 端口: {args.sd_port}")
    print("=" * 60)
    
    # 设置环境变量
    os.environ["SD_SERVER_PORT"] = str(args.sd_port)
    
    # 启动 FastAPI
    uvicorn.run(
        "server-capi.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info"
    )


if __name__ == "__main__":
    main()
