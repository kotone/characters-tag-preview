"""
图片源抽象基类
定义所有图片源实现必须遵循的接口
"""

import asyncio
import aiohttp
from abc import ABC, abstractmethod
from typing import Dict, Optional
from ..stats import Stats


class ImageSource(ABC):
    """
    图片源抽象基类
    所有图片源实现都需要继承此类并实现 search 方法
    """
    
    @abstractmethod
    async def search(
        self,
        session: aiohttp.ClientSession,
        tag: str,
        item_data: Dict,
        sem_img: asyncio.Semaphore,
        retry_times: int,
        retry_delay: int,
        stats: Stats
    ) -> Optional[str]:
        """
        搜索图片
        
        Args:
            session: aiohttp 会话
            tag: 角色标签
            item_data: 完整的角色数据（包含 cn_name, source_en 等信息）
            sem_img: 图片并发信号量
            retry_times: 重试次数
            retry_delay: 重试延迟（秒）
            stats: 统计对象
        
        Returns:
            图片 URL，如果失败返回 None
        """
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """返回图片源名称"""
        pass
