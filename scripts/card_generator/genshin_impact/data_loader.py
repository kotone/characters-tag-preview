"""
原神角色数据加载器
负责加载和管理角色数据
"""

import json
import os
from typing import Optional, Dict
from ..utils import extract_character_name_from_tag, normalize_name, is_genshin_tag


class GenshinCharacterDataLoader:
    """原神角色数据加载器"""
    
    def __init__(self):
        self.name_to_data = {}
        self._load_data()
    
    def _load_data(self):
        """加载原神角色数据"""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.normpath(os.path.join(current_dir, '..', '..', '..', '..'))
        data_file = os.path.join(project_root, 'output', 'genshin_characters-en-cn.json')
        
        try:
            with open(data_file, 'r', encoding='utf-8') as f:
                characters = json.load(f)
            
            for char in characters:
                name_en = char.get('name_en', '').strip()
                if name_en:
                    normalized_name = normalize_name(name_en)
                    self.name_to_data[normalized_name] = char
            
            print(f"✅ 已加载 {len(self.name_to_data)} 个原神角色数据")
        
        except FileNotFoundError:
            print(f"⚠️ 未找到原神角色数据文件: {data_file}")
        except Exception as e:
            print(f"⚠️ 加载原神角色数据失败: {e}")
    
    def get_character_data(self, tag: str) -> Optional[Dict]:
        """
        根据标签获取角色数据
        
        Args:
            tag: 原神标签
        
        Returns:
            角色数据字典
        """
        if not is_genshin_tag(tag):
            return None
        
        char_name = extract_character_name_from_tag(tag)
        if not char_name:
            return None
        
        normalized_name = normalize_name(char_name)
        char_data = self.name_to_data.get(normalized_name)
        
        if char_data:
            return {
                'entry_page_id': char_data.get('entry_page_id'),
                'name_cn': char_data.get('name_cn'),
                'name_en': char_data.get('name_en'),
                'icon_url': char_data.get('icon_url'),
                'header_img_url': char_data.get('header_img_url')
            }
        
        return None
    
    def get_character_icon(self, tag: str) -> Optional[str]:
        """获取角色图标URL"""
        char_data = self.get_character_data(tag)
        return char_data.get('icon_url') if char_data else None
    
    def get_character_header(self, tag: str) -> Optional[str]:
        """获取角色头图URL"""
        char_data = self.get_character_data(tag)
        return char_data.get('header_img_url') if char_data else None


# 全局单例
_data_loader = GenshinCharacterDataLoader()


def get_data_loader() -> GenshinCharacterDataLoader:
    """获取数据加载器单例"""
    return _data_loader
