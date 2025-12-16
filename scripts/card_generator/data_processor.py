"""
数据处理模块 - 数据获取、过滤和批处理流水线
"""

import asyncio
import json
import os
import random
import aiohttp
from typing import List, Dict, Optional
from .config import Config
from .stats import Stats
from .llm import translate_batch_task
from .image_source import ImageSourceManager
from .safebooru import SafebooruImageSource


#初始化图片源管理器
_image_manager = ImageSourceManager()
_image_manager.register_source(SafebooruImageSource())

# 配置图片源规则（示例，可从配置文件加载）
# 原神标签由 genshin_character_mapper 直接处理，不需要额外的图片源



def load_tags_from_file(filepath: str) -> Dict[str, Dict]:
    """
    从本地文件加载角色标签数据
    
    Args:
        filepath: 本地JSON文件路径
    
    Returns:
        字典，key 为角色 name，value 为包含 color 和 content 的字典
        如果加载失败返回空字典
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 从 JSON 数组中提取 terms 为 "Character" 的数据
        if isinstance(data, list):
            tags_dict = {}
            for item in data:
                if item.get('name') and item.get('terms') == 'Character':
                    tags_dict[item['name']] = {
                        'color': item.get('color', 0),
                        'content': item.get('content', '')
                    }
            print(f"✅ 从缓存加载 {len(tags_dict)} 个角色标签")
            return tags_dict
        else:
            print(f"⚠️ 警告: 缓存文件格式不正确")
            return {}
    except FileNotFoundError:
        return {}
    except Exception as e:
        print(f"⚠️ 警告: 加载缓存文件失败 - {e}")
        return {}


async def fetch_tags_from_url(url: str, cache_file: Optional[str] = None) -> Dict[str, Dict]:
    """
    从指定 URL 获取角色标签数据，并可选地保存到缓存文件
    
    Args:
        url: JSON 数据的 URL 地址
        cache_file: 可选的缓存文件路径，如果提供则保存原始数据到该文件
    
    Returns:
        字典，key 为角色 name，value 为包含 color 和 content 的字典
        格式: {"character_name": {"color": 4, "content": "..."}}
        如果获取失败返回空字典
    """
    print(f"📥 正在从 URL 获取数据: {url}")
    timeout = aiohttp.ClientTimeout(total=30)
    
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as response:
                if response.status != 200:
                    print(f"❌ 错误: 无法获取数据，状态码: {response.status}")
                    return {}
                
                # GitHub raw 文件返回 text/plain，需要忽略 Content-Type 检查
                data = await response.json(content_type=None)
                
                # 如果提供了缓存文件路径，保存原始数据
                if cache_file:
                    try:
                        # 确保目录存在
                        os.makedirs(os.path.dirname(cache_file), exist_ok=True)
                        with open(cache_file, 'w', encoding='utf-8') as f:
                            json.dump(data, f, ensure_ascii=False, indent=2)
                        print(f"💾 原始数据已缓存至: {cache_file}")
                    except Exception as e:
                        print(f"⚠️ 警告: 缓存文件保存失败 - {e}")
                
                # 从 JSON 数组中提取 terms 为 "Character" 的数据
                if isinstance(data, list):
                    # 构建字典: {name: {color, content}}
                    tags_dict = {}
                    for item in data:
                        if item.get('name') and item.get('terms') == 'Character':
                            tags_dict[item['name']] = {
                                'color': item.get('color', 0),
                                'content': item.get('content', '')
                            }
                    print(f"✅ 成功获取 {len(tags_dict)} 个角色标签")
                    return tags_dict
                elif isinstance(data, dict):
                    # 如果是字典格式，返回空（不支持）
                    print(f"⚠️ 警告: 数据为字典格式，请检查 URL")
                    return {}
                else:
                    print(f"❌ 错误: 未知的数据格式")
                    return {}
                
    except Exception as e:
        print(f"❌ 错误: 获取数据失败 - {e}")
        return {}


def apply_debug_filter(tags_dict: Dict[str, Dict], limit: int, random_sample: bool) -> Dict[str, Dict]:
    """
    应用数量限制过滤
    
    Args:
        tags_dict: 完整的标签字典
        limit: 数量限制（0表示不限制）
        random_sample: 是否随机抽取
    
    Returns:
        过滤后的标签字典
    """
    # 如果未设置限制，返回全部
    if limit == 0:
        return tags_dict
    
    original_count = len(tags_dict)
    all_tags = list(tags_dict.keys())
    
    if random_sample:
        # 随机抽取
        selected_tags = random.sample(all_tags, min(limit, len(all_tags)))
        print(f"🔍 限量模式: 随机抽取 {len(selected_tags)}/{original_count} 条数据")
    else:
        # 按顺序取前N条
        selected_tags = all_tags[:limit]
        print(f"🔍 限量模式: 取前 {len(selected_tags)}/{original_count} 条数据")
    
    # 返回过滤后的字典
    return {tag: tags_dict[tag] for tag in selected_tags}


async def pipeline_batch(
    session: aiohttp.ClientSession, 
    batch_data: List[Dict],
    config: Config,
    sem_llm: asyncio.Semaphore,
    sem_img: asyncio.Semaphore,
    stats: Stats,
    source_name_mapping: Optional[Dict]
) -> List[Dict]:
    """
    单个批次的完整流水线：
    1. 检查原神标签 -> 直接使用本地数据
    2. 等待 LLM 信号量 -> 请求 LLM
    3. 获取到 JSON -> 请求 Images (内部有 Image 信号量)
    4. 返回结果
    
    Args:
        session: aiohttp 会话
        batch_data: 包含 {"tag": str, "color": int, "content": str} 的列表
        config: 配置对象
        sem_llm: LLM 并发信号量
        sem_img: 图片并发信号量
        stats: 统计对象
        source_name_mapping: 作品名称映射表
    
    Returns:
        处理完成的数据列表
    """
    # 导入工具函数和数据加载器
    from .utils import is_genshin_tag
    from .genshin_impact import get_data_loader as get_genshin_loader
    from .honkai_starrail import get_data_loader as get_starrail_loader, is_honkai_starrail_tag
    
    # 获取数据加载器
    genshin_loader = get_genshin_loader()
    starrail_loader = get_starrail_loader()
    
    # 分离原神/星铁标签和普通标签
    special_items = []  # 原神+星铁
    normal_items = []
    
    for item in batch_data:
        tag = item.get('tag', '')
        
        # 检查原神标签
        if is_genshin_tag(tag):
            char_data = genshin_loader.get_character_data(tag)
            if char_data:
                item['tag_cn'] = char_data['name_cn']
                item['tag_en'] = char_data['name_en']
                item['image_url'] = char_data['icon_url']
                item['source_game'] = 'genshin_impact'
                item['character_id'] = char_data['entry_page_id']
                
                special_items.append(item)
                stats.llm_success_count += 1
                stats.img_success_count += 1
                print(f"✨ 原神角色: {tag} -> {char_data['name_cn']} ({char_data['name_en']})")
            else:
                normal_items.append(item)
                print(f"⚠️ 原神标签未找到映射: {tag}")
        
        # 检查星铁标签
        elif is_honkai_starrail_tag(tag):
            char_data = starrail_loader.get_character_data(tag)
            if char_data:
                item['tag_cn'] = char_data['name_cn']
                item['tag_en'] = char_data['name_en']
                item['image_url'] = char_data['icon_url']
                item['source_game'] = 'honkai_starrail'
                item['character_id'] = char_data['entry_page_id']
                
                special_items.append(item)
                stats.llm_success_count += 1
                stats.img_success_count += 1
                print(f"✨ 星铁角色: {tag} -> {char_data['name_cn']} ({char_data['name_en']})")
            else:
                normal_items.append(item)
                print(f"⚠️ 星铁标签未找到映射: {tag}")
        
        # 普通标签
        else:
            normal_items.append(item)
    
    # 1. LLM 阶段 - 只处理普通标签
    translated_items = []
    if normal_items:
        translated_items = await translate_batch_task(
            session, normal_items, config, sem_llm, stats, source_name_mapping
        )
    
    # 2. 搜图阶段 - 使用图片源管理器（只处理普通标签，原神/星铁标签已有图）
    async def _process_image(item):
        # 如果已经有图，直接返回
        if item.get('image_url') and str(item['image_url']).startswith('http'):
            return item
        
        # 使用图片源管理器搜图（支持多源和降级）
        img_url = await _image_manager.search_with_fallback(
            session, item['tag'], item, sem_img, 
            config.img_retry_times, config.img_retry_delay, stats
        )
        item['image_url'] = img_url
        
        return item
    
    # 并发处理所有图片（只处理普通标签）
    tasks = [_process_image(item) for item in translated_items]
    final_normal_items = await asyncio.gather(*tasks) if tasks else []
    
    # 3. 合并特殊标签（原神+星铁）和普通标签结果
    final_items = special_items + final_normal_items
    
    return final_items
