"""
Safebooru 图片源实现
从 Safebooru 搜索角色图片
"""

import asyncio
import aiohttp
from typing import Dict, Optional
from ..image_source import ImageSource
from ..stats import Stats


class SafebooruImageSource(ImageSource):
    """Safebooru 图片源实现"""
    
    def get_name(self) -> str:
        return "Safebooru"
    
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
        Safebooru 搜图（带重试机制）
        
        搜索策略：使用 tag + "solo" 限定单人图
        返回格式：https://safebooru.org/images/{directory}/{image}
        """
        url = f"https://safebooru.org/index.php?page=dapi&s=post&q=index&tags={tag}+solo&limit=1&json=1"
        
        # 重试逻辑
        for attempt in range(retry_times):
            try:
                # 使用全局信号量限制图片并发
                async with sem_img:
                    async with session.get(url) as resp:
                        if resp.status == 200:
                            data = await resp.json(content_type=None)
                            if data and isinstance(data, list) and len(data) > 0:
                                img = data[0]
                                stats.img_success += 1
                                return f"https://safebooru.org/images/{img['directory']}/{img['image']}"
            except Exception:
                pass
            
            # 如果不是最后一次尝试，等待后重试
            if attempt < retry_times - 1:
                await asyncio.sleep(retry_delay)
        
        stats.img_fail += 1
        return None
