import asyncio
import json
import os
import aiohttp
import time
import random
import argparse
from typing import List, Dict
from tqdm.asyncio import tqdm
import os
import sys
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ================= 配置加载 =================
def load_config():
    """加载配置文件"""
    config_file = os.path.join(BASE_DIR, 'config.json')
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        return config
    except FileNotFoundError:
        print(f"⚠️ 警告: 配置文件不存在 {config_file}，使用默认配置")
        return None
    except Exception as e:
        print(f"⚠️ 警告: 加载配置文件失败: {e}，使用默认配置")
        return None

# 加载配置
CONFIG = load_config()

# ================= 配置项 =================
# 从配置文件读取，如果没有配置文件则使用默认值
if CONFIG:
    # LLM 配置
    BATCH_SIZE = CONFIG['llm'].get('batch_size', 10)
    LLM_CONCURRENCY = CONFIG['llm'].get('concurrency', 5)
    LLM_RETRY_TIMES = CONFIG['llm'].get('retry_times', 3)
    LLM_RETRY_DELAY = CONFIG['llm'].get('retry_delay', 2)
    
    # 图片配置
    IMG_CONCURRENCY = CONFIG['image'].get('concurrency', 10)
    IMG_RETRY_TIMES = CONFIG['image'].get('retry_times', 2)
    IMG_RETRY_DELAY = CONFIG['image'].get('retry_delay', 1)
    
    # 处理配置
    SAVE_INTERVAL_BATCHES = CONFIG['processing'].get('save_interval_batches', 5)
    
    # 路径配置
    INPUT_URL = CONFIG['paths'].get('input_url')
    OUTPUT_FILE = os.path.join(BASE_DIR, CONFIG['paths'].get('output_file'))
    DEBUG_OUTPUT_FILE = os.path.join(BASE_DIR, CONFIG['paths'].get('debug_output_file'))
    DATA_DIR = os.path.join(BASE_DIR, CONFIG['paths'].get('data_dir'))
    CACHED_SOURCE_FILE = os.path.join(BASE_DIR, CONFIG['paths'].get('cached_source_file'))
    MAPPING_FILE = os.path.join(BASE_DIR, CONFIG['paths'].get('mapping_file'))
else:
    # 默认配置
    BATCH_SIZE = 10
    LLM_CONCURRENCY = 5
    LLM_RETRY_TIMES = 3
    LLM_RETRY_DELAY = 2
    IMG_CONCURRENCY = 10
    IMG_RETRY_TIMES = 2
    IMG_RETRY_DELAY = 1
    SAVE_INTERVAL_BATCHES = 5
    
    INPUT_URL = "https://raw.githubusercontent.com/DominikDoom/a1111-sd-webui-tagcomplete/refs/heads/main/tags/noob_characters-chants.json"
    OUTPUT_FILE = os.path.join(BASE_DIR, '..', 'output', 'noob_characters-chants-en-cn.json')
    DEBUG_OUTPUT_FILE = os.path.join(BASE_DIR, '..', 'output', 'debug_output.json')
    DATA_DIR = os.path.join(BASE_DIR, '..', 'data')
    CACHED_SOURCE_FILE = os.path.join(DATA_DIR, 'noob_characters-chants.json')
    MAPPING_FILE = os.path.join(BASE_DIR, 'source_name_mapping.json')

# --- LLM API 配置（从环境变量读取） ---
LLM_API_URL = os.getenv("LLM_API_URL") 
LLM_API_KEY = os.getenv("LLM_API_KEY") 
LLM_MODEL = os.getenv("LLM_MODEL")

# 全局信号量（将在 main 中根据命令行参数初始化）
sem_llm = None
sem_img = None

# 全局映射表（将在 main 中加载）
source_name_mapping = None



# 全局统计对象
class Stats:
    """性能统计类"""
    def __init__(self):
        self.llm_success = 0
        self.llm_fail = 0
        self.img_success = 0
        self.img_fail = 0
        self.total_processed = 0
        self.start_time = time.time()
    
    def print_summary(self):
        duration = time.time() - self.start_time
        llm_total = self.llm_success + self.llm_fail
        img_total = self.img_success + self.img_fail
        
        print("\n" + "="*50)
        print("📊 处理统计报告")
        print("="*50)
        print(f"⏱️  总耗时: {duration:.2f} 秒")
        print(f"🎯 总处理: {self.total_processed} 个角色")
        if duration > 0:
            print(f"⚡ 平均速度: {self.total_processed / duration:.2f} 个/秒")
        print(f"\n🤖 LLM 翻译:")
        if llm_total > 0:
            print(f"   ✅ 成功: {self.llm_success}/{llm_total} ({self.llm_success/llm_total*100:.1f}%)")
            print(f"   ❌ 失败: {self.llm_fail}/{llm_total} ({self.llm_fail/llm_total*100:.1f}%)")
        print(f"\n🖼️  图片搜索:")
        if img_total > 0:
            print(f"   ✅ 成功: {self.img_success}/{img_total} ({self.img_success/img_total*100:.1f}%)")
            print(f"   ❌ 失败: {self.img_fail}/{img_total} ({self.img_fail/img_total*100:.1f}%)")
        print("="*50)

stats = Stats()

def load_source_name_mapping(mapping_file: str) -> Dict:
    """
    加载作品名称规范化映射表
    
    Returns:
        包含规范化规则的字典
    """
    try:
        with open(mapping_file, 'r', encoding='utf-8') as f:
            mapping = json.load(f)
        print(f"✅ 已加载作品名称映射表: {mapping_file}")
        return mapping
    except FileNotFoundError:
        print(f"⚠️  警告: 映射表文件不存在: {mapping_file}")
        return None
    except Exception as e:
        print(f"⚠️  警告: 加载映射表失败: {e}")
        return None

def normalize_source_names(source_en: str, source_cn: str) -> tuple:
    """
    规范化作品英文名和中文名
    
    Args:
        source_en: 原始英文作品名
        source_cn: 原始中文作品名
    
    Returns:
        (规范化后的英文名, 规范化后的中文名)
    """
    if not source_name_mapping:
        return source_en, source_cn
    
    mappings = source_name_mapping.get('mappings', {})
    en_rules = mappings.get('english_normalization', {}).get('rules', {})
    cn_rules = mappings.get('chinese_normalization', {}).get('rules', {})
    standard_pairs = mappings.get('standard_pairs', {}).get('pairs', {})
    
    normalized_en = source_en
    normalized_cn = source_cn
    
    # 1. 先尝试规范化英文名
    for standard_en, variants in en_rules.items():
        if source_en in variants:
            normalized_en = standard_en
            break
    
    # 2. 再尝试规范化中文名
    for standard_cn, variants in cn_rules.items():
        if source_cn in variants:
            normalized_cn = standard_cn
            break
    
    # 3. 如果英文名是标准的，且中文名为空或不标准，使用标准配对
    if normalized_en in standard_pairs and (not normalized_cn or normalized_cn != standard_pairs[normalized_en]):
        normalized_cn = standard_pairs[normalized_en]
    
    # 4. 如果中文名是标准的，且英文名为空或不标准，反向查找标准配对
    if normalized_cn:
        for std_en, std_cn in standard_pairs.items():
            if normalized_cn == std_cn and (not normalized_en or normalized_en != std_en):
                normalized_en = std_en
                break
    
    return normalized_en, normalized_cn





async def call_llm_custom(session: aiohttp.ClientSession, prompt: str) -> str:
    """调用 LLM 接口获取元数据（带重试机制）"""
    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": "You are a JSON generator helper."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 65536,
        "thinking": {
            "type": "disabled"
        },
        "temperature": 0.6,
        "top_p": 0.95,
        "response_format": {"type": "json_object"}
    }

    # 重试逻辑
    for attempt in range(LLM_RETRY_TIMES):
        try:
            async with sem_llm: # 使用信号量限制 LLM 并发
                async with session.post(LLM_API_URL, headers=headers, json=data) as response:
                    if response.status == 200:
                        result = await response.json()
                        # 统计已移至 translate_batch_task 按角色数量统计
                        return result['choices'][0]['message']['content']
                    else:
                        # 打印错误状态码，方便调试
                        if attempt == LLM_RETRY_TIMES - 1:
                            print(f"\n[LLM Error] Status: {response.status} (已重试{attempt+1}次)")
        except Exception as e:
            if attempt == LLM_RETRY_TIMES - 1:
                print(f"\n[LLM] 请求异常: {e} (已重试{attempt+1}次)")
        
        # 如果不是最后一次尝试，等待后重试
        if attempt < LLM_RETRY_TIMES - 1:
            await asyncio.sleep(LLM_RETRY_DELAY * (attempt + 1))  # 指数退避
    
    # 统计失败已移至 translate_batch_task
    return None

async def search_image_safebooru(session: aiohttp.ClientSession, tag: str) -> str:
    """Safebooru 搜图（带重试机制）"""
    url = f"https://safebooru.org/index.php?page=dapi&s=post&q=index&tags={tag}+solo&limit=1&json=1"
    
    # 重试逻辑
    for attempt in range(IMG_RETRY_TIMES):
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
        if attempt < IMG_RETRY_TIMES - 1:
            await asyncio.sleep(IMG_RETRY_DELAY)
    
    stats.img_fail += 1
    return None

async def process_images_for_list(session: aiohttp.ClientSession, data_list: List[Dict]) -> List[Dict]:
    """为列表中的每个条目并发获取图片"""
    tasks = []
    
    async def _task(item):
        # 如果已经有图，直接返回
        if item.get('image_url') and str(item['image_url']).startswith('http'):
            return item
        
        # 没图则去搜
        img_url = await search_image_safebooru(session, item['tag'])
        item['image_url'] = img_url
        
        # 简单的日志输出 (可选，高并发下刷屏可注释掉)
        # log_name = item.get('cn_name') or item['tag']
        # status = "✅" if img_url else "❌"
        # print(f"{status} {log_name}", end="\r") 
        
        return item

    for item in data_list:
        tasks.append(_task(item))
    
    # 等待该批次所有图片任务完成
    return await asyncio.gather(*tasks)

async def translate_batch_task(session: aiohttp.ClientSession, batch_data: List[Dict]) -> List[Dict]:
    """
    LLM 翻译任务
    """
    
    # 提取要翻译的 tag 列表
    tags_to_translate = [item['tag'] for item in batch_data]
    tags_str = '\n'.join([f"{i+1}. {tag}" for i, tag in enumerate(tags_to_translate)])
    
    prompt = f"""
    你是一个精通ACG文化的专家。请将以下 {len(batch_data)} 个 Danbooru Character Tags 翻译成 JSON 格式。

    **要翻译的角色标签**：
{tags_str}

    **翻译要求**:
    1. 必须返回 {len(batch_data)} 个对象，不能多也不能少
    2. 每个对象必须包含以下字段：
       - "tag": 原标签（从上面列表中选择，保持不变）
       - "cn_name": 中文角色名（如果无法确定，留空）
       - "cn_name_status": 中文名状态（官方译名/推断译名/未知）
       - "en_name": 英文角色名（去掉下划线，首字母大写）
       - "source_cn": 作品中文名（如果无法确定，留空）
       - "source_en": 作品英文名
       - "source_name_status": 作品名状态（官方译名/推断译名/未知）

    3. **括号处理规则**：
       如果 tag 中包含括号，例如 character_(xxx)，请按以下规则处理：
       
       - 如果是**服装/形态/版本**描述（如 1st_costume, 2nd_costume, summer, winter, casual, maid, racing, idol 等）：
         * 在 cn_name 中添加对应的中文描述，格式：角色名（描述）
         * 在 en_name 中也保留括号，格式：Character Name (Description)
         例如：inuyama_tamaki_(1st_costume) → cn_name: "犬山玉姬（第一套服装）", en_name: "Inuyama Tamaki (1st Costume)"
       
       - 如果是**作品名称**（用于区分同名角色，如 touhou, fate, pokemon 等）：
         * cn_name 和 en_name **不包含括号和作品名**，只写角色名
         * 将括号内的作品名提取到 source_cn 和 source_en
         例如：ringo_(touhou) → cn_name: "铃瑚", en_name: "Ringo", source_cn: "东方Project", source_en: "Touhou Project"
         例如：sakura_(cardcaptor_sakura) → cn_name: "小樱", en_name: "Sakura", source_cn: "魔卡少女樱", source_en: "Cardcaptor Sakura"


    4. 严禁使用 Markdown 代码块包裹，直接返回 JSON 数组

    请翻译以上 {len(batch_data)} 个标签，确保返回数量正确。
    """
    
    content = await call_llm_custom(session, prompt)
    
    # 构造默认返回值，防止 LLM 挂了导致整个批次丢失
    # 同时保留原始的 color 和 content 字段
    # LLM错误时 cn_name_status 留空，方便区分真正的"未知"状态
    default_res = [
        {
            "tag": item['tag'], 
            "cn_name": "", 
            "cn_name_status": "",  # LLM错误时留空
            "en_name": item['tag'], 
            "source_cn": "", 
            "source_en": "",
            "source_name_status": "",  # LLM错误时留空
            "color": item['color'],
            "content": item['content']
        } 
        for item in batch_data
    ]

    if not content:
        print("\n⚠️ LLM 返回内容为空")
        # 统计失败的角色数量
        stats.llm_fail += len(batch_data)
        return default_res

    try:
        clean_content = content.replace("```json", "").replace("```", "").strip()
        result = json.loads(clean_content)
        
        # 兼容 LLM 可能返回 {"items": [...]} 或直接 [...] 的情况
        items = None
        if isinstance(result, dict):
            for val in result.values():
                if isinstance(val, list): 
                    items = val
                    break
        elif isinstance(result, list):
            items = result
        
        if not items:
            print("\n⚠️ 无法从 LLM 返回中提取列表数据")
            # 统计失败的角色数量
            stats.llm_fail += len(batch_data)
            return default_res
        
        # 修复：验证并处理 LLM 返回数量问题
        if len(items) != len(batch_data):
            if len(items) > len(batch_data):
                # 返回数量过多，截断
                print(f"\n⚠️ 警告: LLM 返回 {len(items)} 项，超过批次大小 {len(batch_data)}，截断多余项")
                items = items[:len(batch_data)]
            else:
                # 返回数量不足
                missing_count = len(batch_data) - len(items)
                print(f"\n⚠️ 警告: LLM 返回 {len(items)} 项，缺少 {missing_count} 项")
                
                # 如果缺失过多（超过50%），认为失败
                if len(items) < len(batch_data) * 0.5:
                    print(f"  → 返回数量太少，标记为失败")
                    stats.llm_fail += len(batch_data)
                    return default_res
                else:
                    # 只缺少一点，补充默认值
                    print(f"  → 补充缺失的 {missing_count} 项")
                    
                    # 获取已返回的 tag
                    returned_tags = {item.get('tag') for item in items}
                    
                    # 为缺失的条目添加默认值
                    for item in batch_data:
                        if item['tag'] not in returned_tags:
                            items.append({
                                "tag": item['tag'],
                                "cn_name": "",
                                "cn_name_status": "",
                                "en_name": item['tag'],
                                "source_cn": "",
                                "source_en": "",
                                "color": item['color'],
                                "content": item['content']
                            })
                    
                    # 部分成功，部分失败
                    stats.llm_success += len(items) - missing_count
                    stats.llm_fail += missing_count
        
        # 将 color 和 content 字段合并到 LLM 返回的结果中
        tag_to_data = {item['tag']: item for item in batch_data}
        for item in items:
            tag = item.get('tag')
            if tag and tag in tag_to_data:
                item['color'] = tag_to_data[tag]['color']
                item['content'] = tag_to_data[tag]['content']
            
            # 规范化作品名称
            source_en = item.get('source_en', '')
            source_cn = item.get('source_cn', '')
            normalized_en, normalized_cn = normalize_source_names(source_en, source_cn)
            item['source_en'] = normalized_en
            item['source_cn'] = normalized_cn
        
        # 统计成功的角色数量
        stats.llm_success += len(items)
        return items
    except Exception as e:
        print(f"\n❌ LLM 数据解析异常: {e}")
        # 统计失败的角色数量
        stats.llm_fail += len(batch_data)
        return default_res

async def pipeline_batch(session: aiohttp.ClientSession, batch_data: List[Dict]) -> List[Dict]:
    """
    单个批次的完整流水线：
    1. 等待 LLM 信号量 -> 请求 LLM
    2. 获取到 JSON -> 请求 Images (内部有 Image 信号量)
    3. 返回结果
    
    Args:
        batch_data: 包含 {"tag": str, "color": int, "content": str} 的列表
    """
    # 1. LLM 阶段
    translated_items = await translate_batch_task(session, batch_data)
    
    # 2. 搜图阶段
    # 注意：这里不需要再显式加锁，因为 search_image_safebooru 内部有 sem_img 控制
    final_items = await process_images_for_list(session, translated_items)
    
    return final_items

def save_data(data: List[Dict], output_file: str = None):
    """辅助函数：保存数据到磁盘
    
    Args:
        data: 要保存的数据
        output_file: 输出文件路径，默认为 OUTPUT_FILE
    """
    if output_file is None:
        output_file = OUTPUT_FILE
    
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ 保存失败: {e}")

# LLM 配置完整性检测
def check_llm_config():
    # 检查 URL 是否为空
    if not LLM_API_URL or not LLM_API_URL.strip():
        print("\n❌ 错误：环境变量 LLM_API_URL 未配置！")
        print("💡 提示：请设置系统环境变量，或使用 .env 文件。")
        sys.exit(1)

    # 检查 Key 是否为空
    if not LLM_API_KEY or not LLM_API_KEY.strip():
        print("\n❌ 错误：环境变量 LLM_API_KEY 未配置！")
        print("💡 提示：请设置系统环境变量 LLM_API_KEY。")
        sys.exit(1)

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

async def fetch_tags_from_url(url: str, cache_file: str = None) -> Dict[str, Dict]:
    """
    从指定 URL 获取角色标签数据，并可选地保存到缓存文件
    
    Args:
        url: JSON 数据的 URL 地址
        cache_file: 可选的缓存文件路径，如果提供则保存原始数据到该文件
    
    Returns:
        字典，key 为角色 name，value 为包含 color 和 content 的字典
        格式: {"character_name": {"color": 4, "content": "..."}}
        如果获取失败返回空字典
    
    Note:
        数据格式示例:
        [
            {
                "name": "00_gundam",
                "terms": "Character",
                "content": "00 gundam,no humans, blue eyes...",
                "color": 4
            }
        ]
        只提取 terms == "Character" 的条目
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



def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='异步批量处理动漫角色数据：LLM翻译 + 图片搜索',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例用法:
  # 只处理前10000个角色
  python %(prog)s --limit 10000
  
  # 生产模式：处理所有数据
  python %(prog)s
  
  # 自定义并发数
  python %(prog)s --llm-concurrency 10 --img-concurrency 20
        ''')
    
    # 数据处理选项
    parser.add_argument('--limit', type=int, default=0, 
                        help='限制处理的数据量（0表示不限制，默认: 0）。例如 --limit 10000 只处理10000个角色')
    parser.add_argument('--random', action='store_true', 
                        help='随机抽取数据（默认：按顺序）。需配合 --limit 使用')
    parser.add_argument('--force-update', action='store_true',
                        help='强制从 URL 重新拉取源数据（忽略本地缓存）')
    parser.add_argument('--debug', action='store_true',
                        help='Debug 模式：忽略历史数据，输出到 debug_output.json，不影响正式文件')
    
    # 并发控制
    parser.add_argument('--llm-concurrency', type=int, default=LLM_CONCURRENCY,
                        help=f'LLM 并发数（默认: {LLM_CONCURRENCY}）')
    parser.add_argument('--img-concurrency', type=int, default=IMG_CONCURRENCY,
                        help=f'图片搜索并发数（默认: {IMG_CONCURRENCY}）')
    
    # 批处理配置
    parser.add_argument('--batch-size', type=int, default=BATCH_SIZE,
                        help=f'批处理大小（默认: {BATCH_SIZE}）')
    
    return parser.parse_args()

async def main():
    global sem_llm, sem_img, source_name_mapping
    
    # 解析命令行参数
    args = parse_args()
    
    # 加载作品名称映射表
    source_name_mapping = load_source_name_mapping(MAPPING_FILE)
    
    # 初始化信号量
    sem_llm = asyncio.Semaphore(args.llm_concurrency)
    sem_img = asyncio.Semaphore(args.img_concurrency)
    
    check_llm_config()

    # 1. 读取输入数据（优先使用缓存，除非强制更新）
    tags_dict = {}
    
    if not args.force_update and os.path.exists(CACHED_SOURCE_FILE):
        # 优先从缓存读取
        print(f"📂 发现本地缓存文件: {CACHED_SOURCE_FILE}")
        tags_dict = load_tags_from_file(CACHED_SOURCE_FILE)
        
        if not tags_dict:
            print("⚠️ 缓存文件无效，尝试从 URL 获取数据")
            tags_dict = await fetch_tags_from_url(INPUT_URL, CACHED_SOURCE_FILE)
    else:
        # 从 URL 获取数据并缓存
        if args.force_update:
            print("🔄 强制更新模式：从 URL 重新拉取数据")
        else:
            print("📥 本地缓存不存在，从 URL 获取数据")
        tags_dict = await fetch_tags_from_url(INPUT_URL, CACHED_SOURCE_FILE)
    
    if not tags_dict:
        print("❌ 错误: 无法获取有效的标签数据")
        return
    
    print(f"🚀 输入总数: {len(tags_dict)}")
    
    # 应用数量限制过滤
    tags_dict = apply_debug_filter(tags_dict, args.limit, args.random)
    
    # Debug 模式提示
    if args.debug:
        print("\n" + "="*60)
        print("🐛 DEBUG 模式已启用")
        print("="*60)
        print("⚠️  此模式将：")
        print("  1. 忽略历史数据，重新处理所有指定的角色")
        print("  2. 输出到 debug_output.json（不影响正式文件）")
        print("  3. 每次运行清空上次的 debug 结果")
        print("="*60 + "\n")
    
    print(f"⚡ 并发配置: LLM x {args.llm_concurrency} | Image x {args.img_concurrency}")
    print(f"🔄 重试配置: LLM {LLM_RETRY_TIMES}次 | Image {IMG_RETRY_TIMES}次")

    # 2. 读取历史数据（区分完整和不完整的数据）
    complete_data = []      # 完整的数据（有 cn_name 和 image_url）
    incomplete_tags = set() # 不完整的 tag（需要重新处理）
    existing_tags = set()   # 所有已存在的 tag
    
    # Debug 模式：忽略历史数据，处理所有指定的角色
    if args.debug:
        print("🐛 Debug 模式：忽略历史数据，重新处理所有角色")
        # Debug 模式不读取历史数据
        complete_data = []
        incomplete_tags = set()
        existing_tags = set()
    elif os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
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
            complete_data = []
            incomplete_tags = set()
            existing_tags = set()

    # 构建待处理的数据列表（两部分数据）
    # 1. 远程新增的 tag（本地不存在）
    # 2. 本地已有但不完整的 tag（需重新处理）
    data_to_process = [
        {"tag": tag, "color": info["color"], "content": info["content"]}
        for tag, info in tags_dict.items()
        if tag not in existing_tags or tag in incomplete_tags
    ]

    if not data_to_process:
        print("🎉 所有数据均已完整，无需处理！")
        return

    print(f"🔥 本次需处理: {len(data_to_process)} 个角色")

    # 3. 创建任务队列
    # 使用同一个 ClientSession 可以复用 TCP 连接，显著提升 SSL 握手速度
    timeout = aiohttp.ClientTimeout(total=90) # 给整个链路更长的宽容度
    async with aiohttp.ClientSession(timeout=timeout) as session:
        
        # 将所有待处理数据分组
        batches = [data_to_process[i : i + args.batch_size] for i in range(0, len(data_to_process), args.batch_size)]
        
        tasks = []
        for batch in batches:
            # 创建所有批次的协程任务
            # 注意：它们不会立刻全部执行，而是会被信号量(Semaphore)卡住
            task = asyncio.create_task(pipeline_batch(session, batch))
            tasks.append(task)
        
        # 4. 异步执行并显示进度
        # current_data 用于在内存中累积数据（只保留完整的旧数据）
        current_data = complete_data.copy()
        finished_batches = 0
        
        # 使用角色数量而不是批次数量来显示进度
        total_characters = len(data_to_process)
        pbar = tqdm(total=total_characters, desc="🚀 处理中", unit="角色")
        
        for coro in asyncio.as_completed(tasks):
            batch_result = await coro
            current_data.extend(batch_result)
            finished_batches += 1
            stats.total_processed += len(batch_result)
            
            # 更新进度条（按角色数量）
            pbar.update(len(batch_result))
            
            # 计算并显示实时成功率
            llm_total = stats.llm_success + stats.llm_fail
            img_total = stats.img_success + stats.img_fail
            postfix_dict = {}
            if llm_total > 0:
                postfix_dict['LLM'] = f"{stats.llm_success/llm_total*100:.0f}%"
            if img_total > 0:
                postfix_dict['图片'] = f"{stats.img_success/img_total*100:.0f}%"
            if postfix_dict:
                pbar.set_postfix(postfix_dict)
            
            # 定期存盘，而不是每批次都存
            if finished_batches % SAVE_INTERVAL_BATCHES == 0:
                # Debug 模式输出到独立文件
                output_file = DEBUG_OUTPUT_FILE if args.debug else OUTPUT_FILE
                save_data(current_data, output_file)
        
        pbar.close()
        
        # 最后再一次性保存，确保数据完整
        # Debug 模式输出到独立文件
        output_file = DEBUG_OUTPUT_FILE if args.debug else OUTPUT_FILE
        save_data(current_data, output_file)
    
    # 打印统计报告
    stats.print_summary()
    
    if args.debug:
        print(f"\n🐛 Debug 模式：数据已保存至 {output_file}")
        print("⚠️  正式文件未受影响")
    else:
        print(f"\n✅ 全部完成！完整数据已保存至 {output_file}")

if __name__ == '__main__':
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())