"""
通用工具函数
"""

import re
from typing import Optional


def is_genshin_tag(tag: str) -> bool:
    """判断是否为原神标签"""
    return '_(genshin_impact)' in tag.lower()


def extract_character_name_from_tag(tag: str, game_suffix: str = 'genshin_impact') -> Optional[str]:
    """
    从标签中提取角色名
    
    Args:
        tag: 标签，如 "zhongli_(genshin_impact)"
        game_suffix: 游戏后缀
    
    Returns:
        角色名，如 "zhongli"
    """
    pattern = rf'^(.+?)_\({game_suffix}\)$'
    match = re.match(pattern, tag.lower())
    if match:
        return match.group(1)
    return None


def normalize_name(name: str) -> str:
    """标准化名称（转小写，去空格）"""
    return name.strip().lower()
