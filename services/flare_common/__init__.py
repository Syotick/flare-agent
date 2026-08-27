"""Flare Agent 共享基础库：配置 / 日志 / 遥测 / 错误。"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("flare-agent")  # 单一事实来源：pyproject.toml
except PackageNotFoundError:  # 纯 PYTHONPATH 开发（未 pip install -e .）时回退
    __version__ = "0.1.0"
