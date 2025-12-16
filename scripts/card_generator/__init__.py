"""
Card Generator Package

角色卡片数据生成工具包
提供 LLM 翻译、图片搜索、数据处理等功能
"""

__version__ = "1.0.0"
__author__ = "Character Tag Preview"

from .config import Config
from .stats import Stats

__all__ = ['Config', 'Stats']
