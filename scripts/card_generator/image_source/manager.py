"""
图片源管理器
负责注册、选择和协调多个图片源
"""

import asyncio
import aiohttp
import re
from typing import Dict, List, Optional, Callable
from .base import ImageSource
from ..stats import Stats


class ImageSourceManager:
    """
    图片源管理器
    负责根据规则选择合适的图片源，支持降级策略
    """
    
    def __init__(self):
        # 注册的图片源列表（按优先级排序）
        self.sources: List[ImageSource] = []
        
        # 规则列表：[(匹配函数, 图片源名称), ...]
        # 匹配函数接收 (tag, item_data)，返回 bool
        self.rules: List[tuple[Callable[[str, Dict], bool], str]] = []
        
        # 默认图片源名称
        self.default_source_name: str = "Safebooru"
    
    def register_source(self, source: ImageSource):
        """注册一个图片源"""
        self.sources.append(source)
    
    def add_rule(self, matcher: Callable[[str, Dict], bool], source_name: str):
        """
        添加规则
        
        Args:
            matcher: 匹配函数，接收 (tag, item_data)，返回是否匹配
            source_name: 匹配成功时使用的图片源名称
        """
        self.rules.append((matcher, source_name))
    
    def add_pattern_rule(self, pattern: str, source_name: str):
        """
        添加正则表达式规则
        
        Args:
            pattern: 正则表达式模式（匹配 tag）
            source_name: 匹配成功时使用的图片源名称
        
        Example:
            manager.add_pattern_rule(r'_\\(genshin_impact\\)', 'Miyoushe')
        """
        regex = re.compile(pattern)
        matcher = lambda tag, item_data: bool(regex.search(tag))
        self.add_rule(matcher, source_name)
    
    def add_source_rule(self, source_en: str, source_name: str):
        """
        添加作品来源规则
        
        Args:
            source_en: 作品英文名（source_en 字段）
            source_name: 匹配成功时使用的图片源名称
        
        Example:
            manager.add_source_rule('genshin_impact', 'Miyoushe')
        """
        matcher = lambda tag, item_data: item_data.get('source_en') == source_en
        self.add_rule(matcher, source_name)
    
    def get_source_by_name(self, name: str) -> Optional[ImageSource]:
        """根据名称获取图片源"""
        for source in self.sources:
            if source.get_name() == name:
                return source
        return None
    
    def select_sources(self, tag: str, item_data: Dict) -> List[ImageSource]:
        """
        根据规则选择图片源（支持降级）
        
        Args:
            tag: 角色标签
            item_data: 角色数据
        
        Returns:
            图片源列表（按优先级排序，包含降级选项）
        """
        selected_sources = []
        
        # 1. 根据规则匹配
        for matcher, source_name in self.rules:
            try:
                if matcher(tag, item_data):
                    source = self.get_source_by_name(source_name)
                    if source and source not in selected_sources:
                        selected_sources.append(source)
            except Exception:
                pass
        
        # 2. 添加默认源作为降级选项
        default_source = self.get_source_by_name(self.default_source_name)
        if default_source and default_source not in selected_sources:
            selected_sources.append(default_source)
        
        # 3. 如果还是没有，使用所有已注册的源
        if not selected_sources:
            selected_sources = self.sources.copy()
        
        return selected_sources
    
    async def search_with_fallback(
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
        搜索图片（支持自动降级）
        
        按优先级尝试多个图片源，直到成功或全部失败
        
        Args:
            session: aiohttp 会话
            tag: 角色标签
            item_data: 角色数据
            sem_img: 图片并发信号量
            retry_times: 重试次数
            retry_delay: 重试延迟（秒）
            stats: 统计对象
        
        Returns:
            图片 URL，如果失败返回 None
        """
        sources = self.select_sources(tag, item_data)
        
        for source in sources:
            try:
                img_url = await source.search(
                    session, tag, item_data, sem_img, retry_times, retry_delay, stats
                )
                if img_url:
                    return img_url
            except Exception:
                pass
        
        return None
