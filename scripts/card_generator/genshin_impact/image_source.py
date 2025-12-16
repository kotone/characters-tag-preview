"""
原神图像源
从本地角色数据获取官方图标
"""

import asyncio
import aiohttp
from typing import Dict, Optional
from ..image_source import ImageSource
from ..stats import Stats
from .data_loader import GenshinCharacterDataLoader


class GenshinImageSource(ImageSource):
    """原神图像源 - 从本地数据获取角色官方图标"""
    
    def __init__(self):
        self.data_loader = GenshinCharacterDataLoader()
    
    def get_name(self) -> str:
        return "Genshin"
    
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
        获取原神角色图标
        
        Args:
            tag: 角色标签
            item_data: 角色数据
            其他参数为兼容性参数（未使用）
        
        Returns:
            图标URL
        """
        # 直接从本地数据获取，无需异步操作
        image_url = self.data_loader.get_character_icon(tag)
        
        if image_url:
            stats.img_success += 1
            return image_url
        
        stats.img_fail += 1
        return None
