"""
工具函数模块
提供通用工具和文件操作工具
"""

from .common import (
    is_genshin_tag,
    extract_character_name_from_tag,
    normalize_name,
)

from .file import (
    ensure_dir,
    safe_filename,
    load_json,
    save_json,
)

__all__ = [
    # 通用工具
    'is_genshin_tag',
    'extract_character_name_from_tag',
    'normalize_name',
    
    # 文件工具
    'ensure_dir',
    'safe_filename',
    'load_json',
    'save_json',
]
