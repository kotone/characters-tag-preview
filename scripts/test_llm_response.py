#!/usr/bin/env python3
"""
测试LLM响应格式，帮助诊断82%失败率问题
"""
import asyncio
import aiohttp
import json
import os
from dotenv import load_dotenv

load_dotenv()

LLM_API_URL = os.getenv("LLM_API_URL")
LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")

async def test_llm_response():
    """测试LLM返回格式"""
    
    # 测试数据
    test_batch = [
        {"tag": "hatsune_miku", "copyrights": ["vocaloid"]},
        {"tag": "rem_(re:zero)", "copyrights": ["re:zero_kara_hajimeru_isekai_seikatsu"]}
    ]
    
    prompt = f"""
你是一个精通ACG文化的专家。请将以下 Danbooru Character Tags 翻译成 JSON 格式。

每个角色都附带了从 Danbooru 获取的版权标签（copyrights），请优先使用这些信息来确定作品名称。

标签列表（含版权信息）:
{json.dumps(test_batch, ensure_ascii=False)}

翻译要求:
1. 返回纯 JSON 数组，每个对象包含：
   - "tag": 原标签（保持不变）
   - "cn_name": 中文角色名
   - "en_name": 英文角色名（去掉下划线，首字母大写）
   - "source_cn": 作品中文名
   - "source_en": 作品英文名

2. 严禁使用 Markdown 代码块包裹，直接返回 JSON 数组。

示例：
[
  {{"tag": "hatsune_miku", "cn_name": "初音未来", "en_name": "Hatsune Miku", "source_cn": "Vocaloid", "source_en": "Vocaloid"}}
]
"""
    
    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # 测试1: 使用 json_object 格式（当前配置）
    print("=" * 60)
    print("测试1: 使用 response_format={type: json_object}")
    print("=" * 60)
    
    data_json_object = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": "You are a JSON generator helper."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"}
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(LLM_API_URL, headers=headers, json=data_json_object) as response:
            if response.status == 200:
                result = await response.json()
                content = result['choices'][0]['message']['content']
                print(f"\n原始返回内容:\n{content}\n")
                
                # 尝试解析
                try:
                    clean_content = content.replace("```json", "").replace("```", "").strip()
                    parsed = json.loads(clean_content)
                    print(f"解析后类型: {type(parsed)}")
                    print(f"解析后内容: {json.dumps(parsed, ensure_ascii=False, indent=2)}\n")
                    
                    # 检查是否是数组
                    if isinstance(parsed, list):
                        print("✅ 返回的是数组，可以直接使用")
                    elif isinstance(parsed, dict):
                        print("⚠️ 返回的是对象，需要提取数组")
                        for key, value in parsed.items():
                            if isinstance(value, list):
                                print(f"   找到数组字段: '{key}'")
                except Exception as e:
                    print(f"❌ 解析失败: {e}")
            else:
                print(f"请求失败: {response.status}")
                print(await response.text())
    
    # 测试2: 不使用 response_format
    print("\n" + "=" * 60)
    print("测试2: 不使用 response_format（让LLM自由返回）")
    print("=" * 60)
    
    data_no_format = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": "You are a JSON generator helper."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.1
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(LLM_API_URL, headers=headers, json=data_no_format) as response:
            if response.status == 200:
                result = await response.json()
                content = result['choices'][0]['message']['content']
                print(f"\n原始返回内容:\n{content}\n")
                
                # 尝试解析
                try:
                    clean_content = content.replace("```json", "").replace("```", "").strip()
                    parsed = json.loads(clean_content)
                    print(f"解析后类型: {type(parsed)}")
                    print(f"解析后内容: {json.dumps(parsed, ensure_ascii=False, indent=2)}\n")
                    
                    # 检查是否是数组
                    if isinstance(parsed, list):
                        print("✅ 返回的是数组，可以直接使用")
                    elif isinstance(parsed, dict):
                        print("⚠️ 返回的是对象，需要提取数组")
                except Exception as e:
                    print(f"❌ 解析失败: {e}")
            else:
                print(f"请求失败: {response.status}")
                print(await response.text())

if __name__ == "__main__":
    asyncio.run(test_llm_response())
