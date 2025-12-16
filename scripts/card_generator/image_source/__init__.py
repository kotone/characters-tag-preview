"""
图像源基础框架
提供图像源基类和管理器
"""

from .base import ImageSource
from .manager import ImageSourceManager

__all__ = [
    'ImageSource',
    'ImageSourceManager',
]
