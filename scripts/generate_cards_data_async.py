import asyncio
import json
import os
import aiohttp
import time
from typing import List, Dict
from tqdm.asyncio import tqdm
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ================= 配置区 =================
INPUT_FILE = os.path.join(BASE_DIR, '..', 'data', 'WAI-il-characters.txt')
OUTPUT_FILE = os.path.join(BASE_DIR, '..', 'output', 'character_data.json')

# --- LLM 配置 ---
LLM_API_URL = ""
LLM_API_KEY = "sk-"  # 【请确保 Key 正确】
LLM_MODEL = "deepseek-chat"

# 批处理大小 (保持不变，DeepSeek 一次处理太多容易幻觉)
BATCH_SIZE = 10

# --- 并发控制 (核心优化点) ---
# LLM 并发数：同时发送给 DeepSeek 的请求数
# 建议 3-5，太高可能会触发 Rate Limit 或超时
LLM_CONCURRENCY = 5

# 搜图并发数：全局同时请求 Safebooru 的数量
# Safebooru 比较宽松，但在高并发下建议设为 10-20
IMG_CONCURRENCY = 10 

# 存盘频率：每处理完多少个批次存一次盘 (减少 IO 开销)
SAVE_INTERVAL_BATCHES = 5
# ===========================================

# 全局信号量
sem_llm = asyncio.Semaphore(LLM_CONCURRENCY)
sem_img = asyncio.Semaphore(IMG_CONCURRENCY)

async def call_llm_custom(session: aiohttp.ClientSession, prompt: str) -> str:
    """调用 LLM 接口获取元数据"""
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

    try:
        async with sem_llm: # 使用信号量限制 LLM 并发
            async with session.post(LLM_API_URL, headers=headers, json=data) as response:
                if response.status == 200:
                    result = await response.json()
                    return result['choices'][0]['message']['content']
                else:
                    # 打印错误状态码，方便调试
                    print(f"\n[LLM Error] Status: {response.status}")
                    return None
    except Exception as e:
        print(f"\n[LLM] 请求异常: {e}")
        return None

async def search_image_safebooru(session: aiohttp.ClientSession, tag: str) -> str:
    """Safebooru 搜图"""
    url = f"https://safebooru.org/index.php?page=dapi&s=post&q=index&tags={tag}&limit=1&json=1"
    try:
        # 使用全局信号量限制图片并发
        async with sem_img:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json(content_type=None)
                    if data and isinstance(data, list) and len(data) > 0:
                        img = data[0]
                        return f"https://safebooru.org/images/{img['directory']}/{img['image']}"
            # 这里的 sleep 移到信号量内或外都可以，放在这里是为了给服务器喘息
            await asyncio.sleep(0.2) 
    except Exception:
        pass
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

async def translate_batch_task(session: aiohttp.ClientSession, tags: List[str]) -> List[Dict]:
    """LLM 翻译任务"""
    prompt = f"""
    你是一个二次元资深专家。请将以下 Danbooru Character Tags 翻译成 JSON 格式。
    
    标签列表:
    {json.dumps(tags)}

    要求:
    1. 返回纯 JSON 数组 (Array)。
    2. 每个对象包含: 
       - "tag": 原字符串
       - "cn_name": 中文角色名(不知道则留空)
       - "en_name": 英文角色名(去下划线)
       - "source_cn": 作品中文名(不知道留空)
       - "source_en": 作品英文名
    3. 严禁使用 Markdown 代码块。
    """
    
    content = await call_llm_custom(session, prompt)
    
    # 构造默认返回值，防止 LLM 挂了导致整个批次丢失
    default_res = [{"tag": t, "cn_name": "", "en_name": t, "source_cn": "", "source_en": ""} for t in tags]

    if not content:
        return default_res

    try:
        clean_content = content.replace("```json", "").replace("```", "").strip()
        result = json.loads(clean_content)
        # 兼容 LLM 可能返回 {"items": [...]} 或直接 [...] 的情况
        if isinstance(result, dict):
            for val in result.values():
                if isinstance(val, list): return val
            return default_res
        if isinstance(result, list):
            return result
        return default_res
    except Exception:
        return default_res

async def pipeline_batch(session: aiohttp.ClientSession, batch_tags: List[str]) -> List[Dict]:
    """
    单个批次的完整流水线：
    1. 等待 LLM 信号量 -> 请求 LLM
    2. 获取到 JSON -> 请求 Images (内部有 Image 信号量)
    3. 返回结果
    """
    # 1. LLM 阶段
    translated_items = await translate_batch_task(session, batch_tags)
    
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

async def main():
    # --- LLM 配置完整性检测 ---
    # 检查 URL 是否为空
    if not LLM_API_URL or not LLM_API_URL.strip():
        print("\n❌ 错误：LLM_API_URL 未配置！")
        print("💡 提示：请在代码顶部的【配置区】填写完整的 API 地址。")
        sys.exit(1)

    # 检查 Key 是否为空或仍为默认值 "sk-"
    if not LLM_API_KEY or LLM_API_KEY.strip() == "sk-" or not LLM_API_KEY.strip():
        print("\n❌ 错误：LLM_API_KEY 未配置！")
        print("💡 提示：请在代码顶部的【配置区】填写有效的 API Key (当前仍为默认值 'sk-')。")
        sys.exit(1)
    # -------------------------------

    if not os.path.exists(INPUT_FILE):
        print(f"错误: 未找到输入文件 {INPUT_FILE}")
        return

    # 1. 读取输入
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        all_input_tags = [line.strip() for line in f if line.strip() and not line.startswith('[')]
    all_input_tags = list(set(all_input_tags))
    
    print(f"🚀 输入总数: {len(all_input_tags)}")
    print(f"⚡ 并发配置: LLM x {LLM_CONCURRENCY} | Image x {IMG_CONCURRENCY}")

    # 2. 读取历史 (逻辑保持不变：只要缺中文名或缺图，就视为未完成)
    valid_results = []
    completed_tags = set()
    
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
                history_data = json.load(f)
            for item in history_data:
                tag = item.get('tag')
                cn_name = item.get('cn_name')
                image_url = item.get('image_url')
                # 只有信息完整的才跳过
                if tag and cn_name and str(cn_name).strip() and image_url and str(image_url).startswith('http'):
                    valid_results.append(item)
                    completed_tags.add(tag)
        except Exception:
            valid_results = []
            completed_tags = set()

    tags_to_process = [t for t in all_input_tags if t not in completed_tags]

    if not tags_to_process:
        print("🎉 所有数据均已完整，无需处理！")
        return

    print(f"🔥 本次需处理: {len(tags_to_process)} 个角色")

    # 3. 创建任务队列
    # 使用同一个 ClientSession 可以复用 TCP 连接，显著提升 SSL 握手速度
    timeout = aiohttp.ClientTimeout(total=90) # 给整个链路更长的宽容度
    async with aiohttp.ClientSession(timeout=timeout) as session:
        
        # 将所有待处理 tag 分组
        batches = [tags_to_process[i : i + BATCH_SIZE] for i in range(0, len(tags_to_process), BATCH_SIZE)]
        
        tasks = []
        for batch in batches:
            # 创建所有批次的协程任务
            # 注意：它们不会立刻全部执行，而是会被信号量(Semaphore)卡住
            task = asyncio.create_task(pipeline_batch(session, batch))
            tasks.append(task)
        
        # 4. 异步执行并显示进度
        # final_results 用于在内存中累积数据
        current_data = valid_results.copy() 
        finished_batches = 0
        
        # tqdm 包装 as_completed，实现乱序完成也能更新进度条
        pbar = tqdm(asyncio.as_completed(tasks), total=len(tasks), desc="🚀 并发处理中")
        
        for coro in pbar:
            batch_result = await coro
            current_data.extend(batch_result)
            finished_batches += 1
            
            # 定期存盘，而不是每批次都存
            if finished_batches % SAVE_INTERVAL_BATCHES == 0:
                save_data(current_data)
                pbar.set_postfix({"Saved": len(current_data)})
        
        # 最后再一次性保存，确保数据完整
        save_data(current_data)
        
    print(f"\n✅ 全部完成！完整数据已保存至 {OUTPUT_FILE}")

if __name__ == '__main__':
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())