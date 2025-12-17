"""
ComfyUI 自定义节点：角色标签选择器
从 JSON 文件加载角色数据，支持按作品筛选角色，输出不同格式的标签
"""

import os
import json
from typing import  Dict, List, Tuple


class CharacterTagSelector:
    """角色标签选择器节点"""
    
    # 数据文件映射 - 从 output 目录加载
    DATA_FILES = {
        "原神": "genshin_characters-en-cn.json",
        "崩坏：星穹铁道": "honkai_starrail_characters-en-cn.json",
        "绝区零": "zzz_characters-en-cn.json",
        "鸣潮": "wuthering_waves_characters-en-cn.json",
    }
    
    # 输出类型
    OUTPUT_TYPES_MAP = {
        "Danbooru标签 (推荐)": "danbooru_tag",
        "简化标签": "simple_tag", 
        "英文自然语言": "natural_en",
        "中英混合": "natural_mixed",
        "仅中文名": "name_cn_only",
        "仅英文名": "name_en_only",
    }
    
    def __init__(self):
        # 当前脚本目录的父目录（characters-tag-preview）
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.output_dir = os.path.join(self.base_dir, "output")
        self.all_data = {}  # 缓存所有数据
        self._load_all_data()
    
    def _load_all_data(self):
        """加载所有JSON数据文件"""
        for source_cn, filename in self.DATA_FILES.items():
            filepath = os.path.join(self.output_dir, filename)
            if os.path.exists(filepath):
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        self.all_data[source_cn] = json.load(f)
                    print(f"✅ 已加载 {source_cn}: {len(self.all_data[source_cn])} 个角色")
                except Exception as e:
                    print(f"❌ 加载 {source_cn} 失败: {e}")
                    self.all_data[source_cn] = []
            else:
                print(f"⚠️ 文件不存在: {filepath}")
                self.all_data[source_cn] = []
    
    @classmethod
    def INPUT_TYPES(cls):
        """定义节点的输入参数"""
        # 创建临时实例来加载数据
        temp_instance = cls()
        
        # 获取所有作品名称
        sources = list(temp_instance.DATA_FILES.keys())
        
        # 先获取第一个作品的角色列表作为默认
        default_source = sources[0] if sources else "原神"
        characters = temp_instance.get_character_list(default_source)
        
        return {
            "required": {
                "source": (sources, {"default": default_source}),
                "character": (characters, {"default": characters[0] if characters else ""}),
                "output_type": (list(cls.OUTPUT_TYPES_MAP.keys()), {"default": "Danbooru标签 (推荐)"}),
            },
        }
    
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text",)
    FUNCTION = "generate_tag"
    CATEGORY = "🎮 Character Tags"
    
    OUTPUT_NODE = True  # 标记为输出节点
    
    def get_character_list(self, source: str) -> List[str]:
        """获取指定作品的角色列表"""
        if source not in self.all_data:
            return []
        
        characters_data = self.all_data[source]
        # 返回 "中文名 (英文名)" 格式的列表
        character_list = [
            f"{char.get('name_cn', '')} ({char.get('name_en', '')})"
            for char in characters_data
        ]
        return character_list if character_list else ["无角色数据"]
    
    def find_character_data(self, source: str, character_display: str) -> Dict:
        """根据显示名称查找角色数据"""
        if source not in self.all_data:
            return {}
        
        characters_data = self.all_data[source]
        
        # 从 "中文名 (英文名)" 格式中提取中文名
        if " (" in character_display:
            name_cn = character_display.split(" (")[0]
        else:
            name_cn = character_display
        
        # 查找匹配的角色
        for char in characters_data:
            if char.get('name_cn') == name_cn:
                return char
        
        return {}
    
    def generate_tag(self, source: str, character: str, output_type: str) -> Tuple[str]:
        """
        生成角色标签
        
        Args:
            source: 作品名称
            character: 角色显示名称（中文名 (英文名)）
            output_type: 输出类型
        
        Returns:
            (tag_string,) 元组
        """
        char_data = self.find_character_data(source, character)
        
        if not char_data:
            return (f"❌ 未找到角色数据: {character}",)
        
        name_cn = char_data.get('name_cn', '')
        name_en = char_data.get('name_en', '')
        source_cn = char_data.get('source_cn', source)
        tag = char_data.get('tag', '')
        
        output_format = self.OUTPUT_TYPES_MAP.get(output_type, "danbooru_tag")
        
        # 1. Danbooru标签格式 (推荐) - 完整tag
        if output_format == "danbooru_tag":
            if tag:
                return (tag,)
            # 如果没有tag，生成一个
            tag_name = name_en.lower().replace(' ', '_').replace('-', '_').replace(':', '').replace('•', '_')
            tag_name = '_'.join(filter(None, tag_name.split('_')))
            source_tag = char_data.get('source', 'unknown')
            return (f"{tag_name}_({source_tag})",)
        
        # 2. 简化标签 - 只有角色名，适合知名角色
        elif output_format == "simple_tag":
            tag_name = name_en.lower().replace(' ', '_').replace('-', '_').replace(':', '').replace('•', '_')
            tag_name = '_'.join(filter(None, tag_name.split('_')))
            return (tag_name,)
        
        # 3. 英文自然语言 - "Character Name from Game Name"
        elif output_format == "natural_en":
            return (f"{name_en} from {source_cn}",)
        
        # 4. 中英混合 - "中文名 (English Name), Game Name"
        elif output_format == "natural_mixed":
            return (f"{name_cn} ({name_en}), {source_cn}",)
        
        # 5. 仅中文名
        elif output_format == "name_cn_only":
            return (name_cn,)
        
        # 6. 仅英文名
        elif output_format == "name_en_only":
            return (name_en,)
        
        return ("❌ 未知的输出类型",)
    
    @classmethod
    def IS_CHANGED(cls, source, character, output_type):
        """检测参数变化，确保节点更新"""
        return f"{source}_{character}_{output_type}"


# ComfyUI 节点映射
NODE_CLASS_MAPPINGS = {
    "CharacterTagSelector": CharacterTagSelector,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "CharacterTagSelector": "🎮 Character Tag Selector",
}
