"""
文件操作模块 - JSON 文件读写
"""

import json
import os
from typing import List, Dict, Tuple, Set


def save_data(data: List[Dict], output_file: str):
    """
    保存数据到 JSON 文件
    
    Args:
        data: 要保存的数据列表
        output_file: 输出文件路径
    """
    try:
        # 确保目录存在
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ 保存失败: {e}")


def load_history_data(output_file: str, debug_mode: bool = False) -> Tuple[List[Dict], Set[str], Set[str]]:
    """
    加载历史数据，区分完整和不完整的数据
    
    Args:
        output_file: 历史数据文件路径
        debug_mode: 是否为 debug 模式（debug 模式忽略历史数据）
    
    Returns:
        (完整数据列表, 不完整的tag集合, 所有已存在的tag集合)
    """
    complete_data = []      # 完整的数据（有 cn_name 和 image_url）
    incomplete_tags = set() # 不完整的 tag（需要重新处理）
    existing_tags = set()   # 所有已存在的 tag
    
    # Debug 模式：忽略历史数据
    if debug_mode:
        print("🐛 Debug 模式：忽略历史数据，重新处理所有角色")
        return complete_data, incomplete_tags, existing_tags
    
    # 读取历史数据
    if os.path.exists(output_file):
        try:
            with open(output_file, 'r', encoding='utf-8') as f:
                history_data = json.load(f)
            for item in history_data:
                tag = item.get('tag')
                cn_name = item.get('cn_name')
                image_url = item.get('image_url')
                
                if tag:
                    existing_tags.add(tag)
                    
                    # 检查数据是否完整
                    is_complete = (
                        cn_name and str(cn_name).strip() and 
                        image_url and str(image_url).startswith('http')
                    )
                    
                    if is_complete:
                        complete_data.append(item)  # 完整数据保留
                    else:
                        incomplete_tags.add(tag)    # 不完整数据标记为待处理
        except Exception:
            pass
    
    return complete_data, incomplete_tags, existing_tags
