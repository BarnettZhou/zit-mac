"""
sd-server 进程管理器
负责启动、停止、监控 sd-server 进程
支持模型热切换
"""

import os
import json
import time
import signal
import subprocess
import threading
from pathlib import Path
from typing import Optional, Callable
from dataclasses import dataclass, asdict
from datetime import datetime

import psutil

from config import (
    ModelConfig, build_sd_server_args,
    DEFAULT_SD_SERVER_HOST, DEFAULT_SD_SERVER_PORT
)
from sd_server_client import SDServerClient


@dataclass
class ServerStatus:
    """服务器状态"""
    running: bool = False
    pid: Optional[int] = None
    port: int = DEFAULT_SD_SERVER_PORT
    model_name: Optional[str] = None
    start_time: Optional[str] = None
    uptime_seconds: Optional[float] = None
    error_message: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "running": self.running,
            "pid": self.pid,
            "port": self.port,
            "model_name": self.model_name,
            "start_time": self.start_time,
            "uptime_seconds": self.uptime_seconds,
            "error_message": self.error_message
        }


class SDServerProcessManager:
    """
    sd-server 进程管理器
    
    功能：
    1. 启动/停止 sd-server 进程
    2. 监控进程状态
    3. 支持模型切换（重启服务）
    4. 健康检查
    """
    
    def __init__(
        self,
        host: str = DEFAULT_SD_SERVER_HOST,
        port: int = DEFAULT_SD_SERVER_PORT,
        verbose: bool = True
    ):
        self.host = host
        self.port = port
        self.verbose = verbose
        
        self._process: Optional[subprocess.Popen] = None
        self._current_model: Optional[ModelConfig] = None
        self._status = ServerStatus(port=port)
        self._lock = threading.Lock()
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_monitoring = threading.Event()
        
        # 创建客户端
        self.client = SDServerClient(f"http://{host}:{port}")
        
        # 启动监控线程
        self._start_monitor()
    
    def _start_monitor(self):
        """启动监控线程"""
        self._stop_monitoring.clear()
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
    
    def _monitor_loop(self):
        """监控循环"""
        while not self._stop_monitoring.is_set():
            with self._lock:
                if self._process is not None:
                    # 检查进程是否还在运行
                    ret_code = self._process.poll()
                    if ret_code is not None:
                        # 进程已退出
                        print(f"[ProcessManager] 检测到 sd-server 进程已退出，返回码: {ret_code}")
                        self._status.running = False
                        self._status.pid = None
                        if self._status.error_message is None:
                            self._status.error_message = f"进程异常退出 (code: {ret_code})"
                        self._process = None
            
            time.sleep(2)  # 每 2 秒检查一次
    
    def get_status(self) -> ServerStatus:
        """获取当前状态"""
        with self._lock:
            status = ServerStatus(
                running=self._status.running,
                pid=self._status.pid,
                port=self._status.port,
                model_name=self._status.model_name,
                start_time=self._status.start_time,
                error_message=self._status.error_message
            )
            
            # 计算运行时间
            if self._status.running and self._status.start_time:
                try:
                    start = datetime.fromisoformat(self._status.start_time)
                    status.uptime_seconds = (datetime.now() - start).total_seconds()
                except:
                    pass
            
            return status
    
    def is_running(self) -> bool:
        """检查服务是否运行中"""
        with self._lock:
            if self._process is None:
                return False
            return self._process.poll() is None
    
    def is_healthy(self) -> bool:
        """健康检查"""
        if not self.is_running():
            return False
        return self.client.health_check()
    
    def start(self, model_config: ModelConfig, wait_ready: bool = True, timeout: int = 120) -> bool:
        """
        启动 sd-server
        
        Args:
            model_config: 模型配置
            wait_ready: 是否等待服务就绪
            timeout: 等待超时时间（秒）
        
        Returns:
            bool: 是否启动成功
        """
        with self._lock:
            # 如果已经在运行，先停止
            if self._process is not None:
                print(f"[ProcessManager] 服务已在运行，先停止当前服务")
                self._stop_locked()
            
            # 构建启动参数
            args = build_sd_server_args(
                model_config=model_config,
                host=self.host,
                port=self.port,
                verbose=self.verbose
            )
            
            print(f"[ProcessManager] 启动 sd-server...")
            print(f"[ProcessManager] 模型: {model_config.name}")
            print(f"[ProcessManager] 命令: {' '.join(args)}")
            
            try:
                # 启动进程
                self._process = subprocess.Popen(
                    args,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True
                )
                
                self._current_model = model_config
                self._status.running = True
                self._status.pid = self._process.pid
                self._status.model_name = model_config.name
                self._status.start_time = datetime.now().isoformat()
                self._status.error_message = None
                
                print(f"[ProcessManager] 进程已启动，PID: {self._process.pid}")
                
            except Exception as e:
                self._status.running = False
                self._status.error_message = f"启动失败: {str(e)}"
                print(f"[ProcessManager] 启动失败: {e}")
                return False
        
        # 等待服务就绪
        if wait_ready:
            return self._wait_for_ready(timeout)
        
        return True
    
    def _wait_for_ready(self, timeout: int = 120) -> bool:
        """等待服务就绪"""
        print(f"[ProcessManager] 等待服务就绪（超时 {timeout}s）...")
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            # 检查进程是否还在运行
            if not self.is_running():
                with self._lock:
                    self._status.running = False
                    if self._status.error_message is None:
                        self._status.error_message = "进程启动后立即退出"
                print(f"[ProcessManager] 进程启动后立即退出")
                return False
            
            # 尝试健康检查
            try:
                if self.client.health_check():
                    print(f"[ProcessManager] 服务已就绪！")
                    return True
            except:
                pass
            
            time.sleep(0.5)
        
        # 超时
        with self._lock:
            self._status.error_message = f"等待服务就绪超时（{timeout}s）"
        print(f"[ProcessManager] 等待服务就绪超时")
        return False
    
    def stop(self, timeout: int = 10) -> bool:
        """停止服务"""
        with self._lock:
            return self._stop_locked(timeout)
    
    def _stop_locked(self, timeout: int = 10) -> bool:
        """内部停止方法（需要持有锁）"""
        if self._process is None:
            return True
        
        print(f"[ProcessManager] 停止 sd-server (PID: {self._process.pid})...")
        
        try:
            # 尝试优雅终止
            self._process.terminate()
            
            # 等待进程退出
            try:
                self._process.wait(timeout=timeout)
                print(f"[ProcessManager] 进程已正常终止")
            except subprocess.TimeoutExpired:
                # 强制终止
                print(f"[ProcessManager] 进程未响应，强制终止...")
                self._process.kill()
                self._process.wait()
            
        except Exception as e:
            print(f"[ProcessManager] 停止进程时出错: {e}")
        finally:
            self._process = None
            self._status.running = False
            self._status.pid = None
        
        return True
    
    def restart(self, model_config: Optional[ModelConfig] = None, timeout: int = 120) -> bool:
        """
        重启服务
        
        Args:
            model_config: 新模型配置，为 None 则使用当前模型
            timeout: 超时时间
        
        Returns:
            bool: 是否重启成功
        """
        if model_config is None:
            model_config = self._current_model
        
        if model_config is None:
            print(f"[ProcessManager] 错误: 未指定模型配置")
            return False
        
        print(f"[ProcessManager] 重启服务...")
        
        # 停止当前服务
        self.stop()
        time.sleep(1)  # 等待端口释放
        
        # 启动新服务
        return self.start(model_config, wait_ready=True, timeout=timeout)
    
    def switch_model(self, model_config: ModelConfig) -> bool:
        """
        切换模型（重启服务）
        
        Args:
            model_config: 新模型配置
        
        Returns:
            bool: 是否切换成功
        """
        if self._current_model and self._current_model.name == model_config.name:
            print(f"[ProcessManager] 已经是当前模型: {model_config.name}")
            return True
        
        print(f"[ProcessManager] 切换模型: {model_config.name}")
        return self.restart(model_config)
    
    def get_logs(self, lines: int = 50) -> str:
        """获取最近日志（如果启用了捕获）"""
        # 当前实现使用 PIPE，但异步读取较复杂
        # 可以通过重定向到文件来实现日志持久化
        return "日志捕获功能待实现"
    
    def shutdown(self):
        """关闭管理器"""
        print(f"[ProcessManager] 关闭管理器...")
        self._stop_monitoring.set()
        self.stop()
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=2)


# 全局管理器实例
_manager: Optional[SDServerProcessManager] = None


def get_manager() -> SDServerProcessManager:
    """获取全局管理器实例"""
    global _manager
    if _manager is None:
        _manager = SDServerProcessManager()
    return _manager


def init_manager(host: str = DEFAULT_SD_SERVER_HOST, port: int = DEFAULT_SD_SERVER_PORT) -> SDServerProcessManager:
    """初始化全局管理器"""
    global _manager
    _manager = SDServerProcessManager(host=host, port=port)
    return _manager
