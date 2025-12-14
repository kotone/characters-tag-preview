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

# ================= 配置区 =================
INPUT_URL = "https://raw.githubusercontent.com/DominikDoom/a1111-sd-webui-tagcomplete/refs/heads/main/tags/noob_characters-chants.json"
OUTPUT_FILE = os.path.join(BASE_DIR, '..', 'output', 'noob_characters-chants-en-cn.json')
MAPPING_FILE = os.path.join(BASE_DIR, 'source_name_mapping.json')

# --- LLM 配置 ---
LLM_API_URL = os.getenv("LLM_API_URL") 
LLM_API_KEY = os.getenv("LLM_API_KEY") 
LLM_MODEL = os.getenv("LLM_MODEL")


# 批处理大小 (保持不变，DeepSeek 一次处理太多容易幻觉)
BATCH_SIZE = 10

# --- 并发控制 ---
# LLM 并发数：同时发送给 DeepSeek 的请求数
# 建议 3-5，太高可能会触发 Rate Limit 或超时
LLM_CONCURRENCY = 5

# 搜图并发数：全局同时请求 Safebooru 的数量
# Safebooru 比较宽松，但在高并发下建议设为 10-20
IMG_CONCURRENCY = 10 

# 存盘频率：每处理完多少个批次存一次盘 (减少 IO 开销)
SAVE_INTERVAL_BATCHES = 5

# --- 重试配置 ---
LLM_RETRY_TIMES = 3  # LLM 重试次数
LLM_RETRY_DELAY = 2  # LLM 重试延迟（秒）
IMG_RETRY_TIMES = 2  # 图片搜索重试次数
IMG_RETRY_DELAY = 1  # 图片搜索重试延迟（秒）

# --- Danbooru API 配置 ---
DANBOORU_API_BASE = "https://safebooru.donmai.us"
DANBOORU_RATE_LIMIT = 0.5  # 2 请求/秒 (匿名用户)
DANBOORU_RETRY_TIMES = 2  # Danbooru API 重试次数
DANBOORU_RETRY_DELAY = 1  # Danbooru API 重试延迟（秒）

# --- 调试模式（默认值，可通过命令行参数覆盖） ---
DEBUG_MODE = False
DEBUG_LIMIT = 10
DEBUG_RANDOM = True
# ===========================================

# 全局信号量（将在 main 中根据命令行参数初始化）
sem_llm = None
sem_img = None
sem_danbooru = None  # Danbooru API 信号量

# 全局映射表（将在 main 中加载）
source_name_mapping = None

# 全局 Danbooru 缓存
copyright_cache = {}  # {tag: [copyright_tags]}
last_danbooru_request = 0  # 上次请求时间戳

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


async def fetch_copyright_from_danbooru(session: aiohttp.ClientSession, tag: str) -> List[str]:
    """
    从 Danbooru API 获取角色的版权标签
    
    Args:
        tag: 角色标签名
    
    Returns:
        版权标签列表，如 ["fate/grand_order", "fate_(series)"] 或空列表
    """
    global last_danbooru_request
    
    # 检查缓存
    if tag in copyright_cache:
        return copyright_cache[tag]
    
    # 构建 API 请求 URL
    # 使用 tag search API 查询角色标签的版权信息
    api_url = f"{DANBOORU_API_BASE}/tags.json?search[name]={tag}"
    
    copyrights = []
    
    for attempt in range(DANBOORU_RETRY_TIMES):
        try:
            async with sem_danbooru:
                # 速率限制：确保两次请求之间至少间隔 DANBOORU_RATE_LIMIT 秒
                current_time = time.time()
                time_since_last = current_time - last_danbooru_request
                if time_since_last < DANBOORU_RATE_LIMIT:
                    await asyncio.sleep(DANBOORU_RATE_LIMIT - time_since_last)
                
                last_danbooru_request = time.time()
                
                async with session.get(api_url) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # 如果找到标签信息
                        if data and isinstance(data, list) and len(data) > 0:
                            tag_info = data[0]
                            # 检查是否有关联的版权标签
                            # 注意：这里需要进一步查询角色关联的帖子来获取版权信息
                            # 因为 tag API 不直接返回版权信息，我们需要查询使用该标签的帖子
                            
                            # 查询使用该标签的帖子（限制1个即可）
                            posts_url = f"{DANBOORU_API_BASE}/posts.json?tags={tag}&limit=1"
                            async with session.get(posts_url) as posts_response:
                                if posts_response.status == 200:
                                    posts_data = await posts_response.json()
                                    if posts_data and isinstance(posts_data, list) and len(posts_data) > 0:
                                        post = posts_data[0]
                                        # 从帖子的 tag_string_copyright 字段获取版权标签
                                        copyright_string = post.get('tag_string_copyright', '')
                                        if copyright_string:
                                            copyrights = [c.strip() for c in copyright_string.split() if c.strip()]
                        
                        # 缓存结果
                        copyright_cache[tag] = copyrights
                        return copyrights
                        
        except Exception as e:
            if attempt == DANBOORU_RETRY_TIMES - 1:
                # 最后一次重试失败，返回空列表
                pass
        
        # 如果不是最后一次尝试，等待后重试
        if attempt < DANBOORU_RETRY_TIMES - 1:
            await asyncio.sleep(DANBOORU_RETRY_DELAY)
    
    # 缓存空结果，避免重复请求
    copyright_cache[tag] = []
    return []


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
        "temperature": 0.1,
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
                # 给服务器喘息
                await asyncio.sleep(0.2)
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
    
    Args:
        batch_data: 包含 {"tag": str, "color": int, "content": str, "copyrights": List[str]} 的列表
    """
    # 构建带版权信息的标签列表
    tags_with_copyright = [
        {
            "tag": item['tag'],
            "copyrights": item.get('copyrights', [])
        }
        for item in batch_data
    ]
    
    # 检查是否有任何非空的版权信息
    has_copyright_info = any(item['copyrights'] for item in tags_with_copyright)
    
    # 根据是否有版权信息，动态调整 prompt
    if has_copyright_info:
        copyright_instruction = """每个角色都附带了从 Danbooru 获取的版权标签（copyrights），请优先使用这些信息来确定作品名称。

标签列表（含版权信息）:"""
        
        source_rules = """3. source_cn 和 source_en 填写规则（重要）：
   - **优先使用提供的 copyrights 信息**来确定作品名称
   - 如果 copyrights 包含作品标签（如 ["date_a_live"]），将其转换为规范的作品名称
   - 作品名称转换规则：
     * "date_a_live" → source_en: "Date A Live", source_cn: "约会大作战"
     * "fate/grand_order" 或 "fate_(series)" → source_en: "Fate/Grand Order", source_cn: "命运/冠位指定"
     * "blue_archive" → source_en: "Blue Archive", source_cn: "蔚蓝档案"
     * "original" → source_en: "Original", source_cn: "" (原创角色/VTuber)
   - 如果 copyrights 为空或包含 "original"，且你能从角色名推断出准确来源，可以使用推断结果
   - 如果完全无法确定，source_en 填写 "Original"，source_cn 留空"""
    else:
        copyright_instruction = """标签列表:"""
        
        source_rules = """3. source_cn 和 source_en 填写规则（重要）：
   - **根据角色标签名称推断作品来源**（没有提供版权信息）
   - 如果角色名中包含作品提示（如括号中的系列名），使用该信息
   - 作品名称转换规则示例：
     * 包含 "_(fate)" → 通常是 Fate 系列作品
     * 包含 "_(blue_archive)" → Blue Archive / 蔚蓝档案
     * 包含 "_(kancolle)" → Kantai Collection / 舰队Collection
   - 如果角色名中没有作品提示，根据你的 ACG 知识推断
   - 如果完全无法确定或是原创角色/VTuber，source_en 填写 "Original"，source_cn 留空"""
    
    prompt = f"""
你是一个精通ACG文化的专家。请将以下 Danbooru Character Tags 翻译成 JSON 格式。

{copyright_instruction}
{json.dumps(tags_with_copyright, ensure_ascii=False)}

翻译要求:
1. 返回纯 JSON 数组，每个对象包含：
   - "tag": 原标签（保持不变）
   - "cn_name": 中文角色名
   - "cn_name_status": 中文名状态标注
   - "en_name": 英文角色名（去掉下划线，首字母大写）
   - "source_cn": 作品中文名
   - "source_en": 作品英文名

2. cn_name 和 cn_name_status 填写规则（重要）：
   - 如果是知名角色，填写官方中文译名，cn_name_status 填写 true
   - 如果是日文角色但没有官方中文名，进行合理音译（如：リン → 凛，输出`リン（凛）`），cn_name_status 填写 "音译"
   - 如果是英文角色名，可以音译或留空（如：Asia Argento 可以音译为"亚细亚·阿尔真托"），cn_name_status 填写 "音译"
   - 如果完全不知道或无法推断，cn_name 留空，cn_name_status 填写 "未知"

{source_rules}

4. 严禁使用 Markdown 代码块包裹，直接返回 JSON 数组。

示例：
[
  {{"tag": "hatsune_miku", "cn_name": "初音未来", "cn_name_status": "", "en_name": "Hatsune Miku", "source_cn": "Vocaloid", "source_en": "Vocaloid"}},
  {{"tag": "yamai_yuzuru", "cn_name": "八舞夕弦", "cn_name_status": "", "en_name": "Yamai Yuzuru", "source_cn": "约会大作战", "source_en": "Date A Live"}},
  {{"tag": "rin_(vocaloid)", "cn_name": "リン（凛）", "cn_name_status": "音译", "en_name": "Rin", "source_cn": "Vocaloid", "source_en": "Vocaloid"}},
  {{"tag": "unknown_character_xyz", "cn_name": "", "cn_name_status": "未知", "en_name": "Unknown Character Xyz", "source_cn": "", "source_en": "Original"}}
]
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
        print(f"\n[DEBUG] LLM原始返回前100字符: {content[:100]}")
        
        clean_content = content.replace("```json", "").replace("```", "").strip()
        result = json.loads(clean_content)
        
        print(f"[DEBUG] 解析后类型: {type(result)}")
        
        # 兼容 LLM 可能返回 {"items": [...]} 或直接 [...] 的情况
        items = None
        if isinstance(result, dict):
            print(f"[DEBUG] 返回的是字典，键: {list(result.keys())}")
            for val in result.values():
                if isinstance(val, list): 
                    items = val
                    print(f"[DEBUG] 从字典中提取到列表，长度: {len(items)}")
                    break
        elif isinstance(result, list):
            items = result
            print(f"[DEBUG] 返回的是列表，长度: {len(items)}")
        
        if not items:
            print("\n⚠️ 无法从 LLM 返回中提取列表数据")
            print(f"[DEBUG] 返回内容: {json.dumps(result, ensure_ascii=False)[:200]}")
            # 统计失败的角色数量
            stats.llm_fail += len(batch_data)
            return default_res
        
        print(f"✅ 解析成功，共 {len(items)} 项")
        # 调试：输出解析后的第一个项目
        if items:
            print(f"✅ 解析成功，共 {len(items)} 项")
        
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

def save_data(data: List[Dict]):
    """辅助函数：保存数据到磁盘"""
    try:
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
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

async def fetch_tags_from_url(url: str) -> Dict[str, Dict]:
    """
    从指定 URL 获取角色标签数据，并从 Danbooru 获取版权信息
    
    Args:
        url: JSON 数据的 URL 地址
    
    Returns:
        字典，key 为角色 name，value 为包含 color、content 和 copyrights 的字典
        格式: {"character_name": {"color": 4, "content": "...", "copyrights": [...]}}
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
                
                # 从 JSON 数组中提取 terms 为 "Character" 的数据
                if isinstance(data, list):
                    # 构建字典: {name: {color, content}}
                    tags_dict = {}
                    for item in data:
                        if item.get('name') and item.get('terms') == 'Character':
                            tags_dict[item['name']] = {
                                'color': item.get('color', 0),
                                'content': item.get('content', ''),
                                'copyrights': []  # 初始化为空列表
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

def apply_debug_filter(tags_dict: Dict[str, Dict], debug_mode: bool, debug_limit: int, debug_random: bool) -> Dict[str, Dict]:
    """
    应用数量限制过滤
    
    Args:
        tags_dict: 完整的标签字典
        debug_mode: 是否启用调试模式（启用随机抽取）
        debug_limit: 数量限制（0表示不限制）
        debug_random: 是否随机抽取
    
    Returns:
        过滤后的标签字典
    """
    # 如果未设置限制，返回全部
    if debug_limit == 0:
        return tags_dict
    
    original_count = len(tags_dict)
    all_tags = list(tags_dict.keys())
    
    if debug_random:
        # 随机抽取
        selected_tags = random.sample(all_tags, min(debug_limit, len(all_tags)))
        print(f"🔍 限量模式: 随机抽取 {len(selected_tags)}/{original_count} 条数据")
    else:
        # 按顺序取前N条
        selected_tags = all_tags[:debug_limit]
        print(f"🔍 限量模式: 取前 {len(selected_tags)}/{original_count} 条数据")
    
    # 返回过滤后的字典
    return {tag: tags_dict[tag] for tag in selected_tags}

async def enrich_with_copyrights(session: aiohttp.ClientSession, data_list: List[Dict]) -> List[Dict]:
    """
    为待处理的数据列表批量获取版权信息
    
    Args:
        session: aiohttp ClientSession
        data_list: 包含 {"tag": str, ...} 的列表
    
    Returns:
        添加了 "copyrights" 字段的数据列表
    """
    if not data_list:
        return data_list
    
    print(f"🔍 正在从 Danbooru 获取 {len(data_list)} 个角色的版权信息...")
    
    from tqdm import tqdm
    pbar = tqdm(total=len(data_list), desc="获取版权", unit="角色")
    
    for item in data_list:
        tag = item['tag']
        copyrights = await fetch_copyright_from_danbooru(session, tag)
        item['copyrights'] = copyrights
        pbar.update(1)
    
    pbar.close()
    print(f"✅ 版权信息获取完成")
    return data_list

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='异步批量处理动漫角色数据：LLM翻译 + 图片搜索',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例用法:
  # 只处理前10000个角色（快速模式，跳过版权获取）
  python %(prog)s --limit 10000 --skip-copyright
  
  # 处理10000个角色（包含版权信息，较慢）
  python %(prog)s --limit 10000
  
  # 生产模式：处理所有数据
  python %(prog)s
  
  # 自定义并发数
  python %(prog)s --llm-concurrency 10 --img-concurrency 20
        ''')
    
    # 数据处理选项
    parser.add_argument('--debug', action='store_true', 
                        help='启用调试模式（随机抽取数据）')
    parser.add_argument('--limit', type=int, default=0, 
                        help='限制处理的数据量（0表示不限制，默认: 0）。例如 --limit 10000 只处理10000个角色')
    parser.add_argument('--random', action='store_true', 
                        help='随机抽取数据（默认：按顺序）。需配合 --limit 使用')
    parser.add_argument('--skip-copyright', action='store_true',
                        help='跳过 Danbooru 版权信息获取（显著提升速度，但依赖 LLM 推断作品来源）')
    
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
    global sem_llm, sem_img, sem_danbooru, source_name_mapping
    
    # 解析命令行参数
    args = parse_args()
    
    # 加载作品名称映射表
    source_name_mapping = load_source_name_mapping(MAPPING_FILE)
    
    # 初始化信号量
    sem_llm = asyncio.Semaphore(args.llm_concurrency)
    sem_img = asyncio.Semaphore(args.img_concurrency)
    sem_danbooru = asyncio.Semaphore(5)  # Danbooru API 并发限制为5
    
    check_llm_config()

    # 1. 从 URL 读取输入数据
    tags_dict = await fetch_tags_from_url(INPUT_URL)
    
    if not tags_dict:
        print("❌ 错误: 无法获取有效的标签数据")
        return
    
    print(f"🚀 输入总数: {len(tags_dict)}")
    
    # 应用调试模式过滤
    tags_dict = apply_debug_filter(tags_dict, args.debug, args.limit, args.random)
    
    print(f"⚡ 并发配置: LLM x {args.llm_concurrency} | Image x {args.img_concurrency}")
    print(f"🔄 重试配置: LLM {LLM_RETRY_TIMES}次 | Image {IMG_RETRY_TIMES}次")

    # 2. 读取历史数据（区分完整和不完整的数据）
    complete_data = []      # 完整的数据（有 cn_name 和 image_url）
    incomplete_tags = set() # 不完整的 tag（需要重新处理）
    existing_tags = set()   # 所有已存在的 tag
    
    if os.path.exists(OUTPUT_FILE):
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
    
    # 为待处理的角色获取版权信息（如果未跳过）
    if not args.skip_copyright:
        timeout = aiohttp.ClientTimeout(total=90)
        async with aiohttp.ClientSession(timeout=timeout) as copyright_session:
            data_to_process = await enrich_with_copyrights(copyright_session, data_to_process)
    else:
        print("⚡ 已跳过 Danbooru 版权信息获取（使用 --skip-copyright）")
        # 为每个角色添加空的 copyrights 字段
        for item in data_to_process:
            item['copyrights'] = []

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
            
            # 定期存盘，而不是每批次都存
            if finished_batches % SAVE_INTERVAL_BATCHES == 0:
                save_data(current_data)
                pbar.set_postfix({"已保存": len(current_data)})
        
        pbar.close()
        
        # 最后再一次性保存，确保数据完整
        save_data(current_data)
    
    # 打印统计报告
    stats.print_summary()
    print(f"\n✅ 全部完成！完整数据已保存至 {OUTPUT_FILE}")

if __name__ == '__main__':
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())