"""
LLM 交互模块 - LLM API 调用和翻译逻辑
"""

import asyncio
import json
import aiohttp
from typing import List, Dict, Optional, Tuple
from .stats import Stats
from .config import Config


def load_source_name_mapping(mapping_file: str) -> Optional[Dict]:
    """
    加载作品名称规范化映射表
    
    Args:
        mapping_file: 映射表文件路径
    
    Returns:
        包含规范化规则的字典，失败返回 None
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


def normalize_source_names(
    source_en: str, 
    source_cn: str,
    source_name_mapping: Optional[Dict]
) -> Tuple[str, str]:
    """
    规范化作品英文名和中文名
    
    Args:
        source_en: 原始英文作品名
        source_cn: 原始中文作品名
        source_name_mapping: 映射表字典
    
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


async def call_llm_custom(
    session: aiohttp.ClientSession, 
    prompt: str,
    config: Config,
    sem_llm: asyncio.Semaphore
) -> Optional[str]:
    """
    调用 LLM 接口获取元数据（带重试机制）
    
    Args:
        session: aiohttp 会话
        prompt: 提示词
        config: 配置对象
        sem_llm: LLM 并发信号量
    
    Returns:
        LLM 返回的内容，失败返回 None
    """
    headers = {
        "Authorization": f"Bearer {config.llm_api_key}",
        "Content-Type": "application/json"
    }
    data = {
        "model": config.llm_model,
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
    for attempt in range(config.llm_retry_times):
        try:
            async with sem_llm:  # 使用信号量限制 LLM 并发
                async with session.post(config.llm_api_url, headers=headers, json=data) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result['choices'][0]['message']['content']
                    else:
                        # 打印错误状态码，方便调试
                        if attempt == config.llm_retry_times - 1:
                            print(f"\n[LLM Error] Status: {response.status} (已重试{attempt+1}次)")
        except Exception as e:
            if attempt == config.llm_retry_times - 1:
                print(f"\n[LLM] 请求异常: {e} (已重试{attempt+1}次)")
        
        # 如果不是最后一次尝试，等待后重试
        if attempt < config.llm_retry_times - 1:
            await asyncio.sleep(config.llm_retry_delay * (attempt + 1))  # 指数退避
    
    return None


async def translate_batch_task(
    session: aiohttp.ClientSession, 
    batch_data: List[Dict],
    config: Config,
    sem_llm: asyncio.Semaphore,
    stats: Stats,
    source_name_mapping: Optional[Dict]
) -> List[Dict]:
    """
    LLM 翻译任务
    
    Args:
        session: aiohttp 会话
        batch_data: 包含 {"tag": str, "color": int, "content": str} 的列表
        config: 配置对象
        sem_llm: LLM 并发信号量
        stats: 统计对象
        source_name_mapping: 作品名称映射表
    
    Returns:
        翻译后的数据列表
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
    
    content = await call_llm_custom(session, prompt, config, sem_llm)
    
    # 构造默认返回值，防止 LLM 挂了导致整个批次丢失
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
            stats.llm_fail += len(batch_data)
            return default_res
        
        # 验证并处理 LLM 返回数量问题
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
            normalized_en, normalized_cn = normalize_source_names(source_en, source_cn, source_name_mapping)
            item['source_en'] = normalized_en
            item['source_cn'] = normalized_cn
        
        # 统计成功的角色数量
        stats.llm_success += len(items)
        return items
    except Exception as e:
        print(f"\n❌ LLM 数据解析异常: {e}")
        stats.llm_fail += len(batch_data)
        return default_res
