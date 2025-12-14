#!/usr/bin/env python3
"""
测试 LLM prompt 在空 copyright 情况下的表现
"""
import json

# 模拟数据
batch_data_with_empty_copyright = [
    {"tag": "aaron_wei", "copyrights": []},
    {"tag": "aarontsay", "copyrights": []},
    {"tag": "aatrox", "copyrights": []},
    {"tag": "aayla_secura", "copyrights": []},
    {"tag": "abarai_renji", "copyrights": []},
    {"tag": "abby_(toshizou)", "copyrights": []},
    {"tag": "abe_nana", "copyrights": []},
    {"tag": "abe_no_seimei_(onmyoji)", "copyrights": []},
    {"tag": "abe_takakazu", "copyrights": []},
    {"tag": "abel_(street_fighter)", "copyrights": []}
]

# 构建tags_with_copyright
tags_with_copyright = [
    {
        "tag": item['tag'],
        "copyrights": item.get('copyrights', [])
    }
    for item in batch_data_with_empty_copyright
]

print("当所有 copyrights 都为空时，发送给 LLM 的数据：")
print(json.dumps(tags_with_copyright, ensure_ascii=False, indent=2))

print("\n" + "="*60)
print("问题分析：")
print("="*60)
print("1. 每个角色的 copyrights 都是 []")
print("2. prompt 说'请优先使用提供的 copyrights 信息'")
print("3. 但所有 copyrights 都是空的！")
print("4. LLM 可能会困惑：既然要求优先使用，但所有都是空的...")
print("5. 这可能导致 LLM:")
print("   - 返回空的 source_en/source_cn (80%+ 的情况)")
print("   - 或者直接返回错误格式")
print("\n💡 解决方案：")
print("当使用 --skip-copyright 时，应该修改 prompt")
print("告诉 LLM '没有版权信息，请根据角色名推断'")
print("而不是说'请优先使用提供的 copyrights 信息'")
