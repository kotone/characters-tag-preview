# cn_name_status 字段说明文档

## 字段定义

`cn_name_status` 字段用于标注中文名称的翻译状态，方便后续数据质量控制和筛选修复。

## 状态值

| 状态值 | 说明 | 示例 |
|--------|------|------|
| `""` (空字符串) | 成功翻译或官方译名 | `"cn_name": "初音未来"`, `"cn_name_status": true` |
| `""` (空字符串) | LLM接口错误导致的空值 | `"cn_name": ""`, `"cn_name_status": ""` |
| `"音译"` | 日文/英文角色名的合理音译 | `"cn_name": "リン（凛）"`, `"cn_name_status": "音译"` |
| `"未知"` | 完全不知道或无法推断 | `"cn_name": ""`, `"cn_name_status": "未知"` |

## 使用场景

### 1. 筛选需要修复的数据

```python
import json

data = json.load(open('output/noob_characters-chants-en-cn.json'))

# 筛选出"未知"状态的数据
unknown_items = [item for item in data if item.get('cn_name_status') == '未知']
print(f"需要人工补充的角色: {len(unknown_items)}个")

# 筛选出可能是LLM错误的数据 (cn_name和cn_name_status都为空)
llm_error_items = [
    item for item in data 
    if not item.get('cn_name') and not item.get('cn_name_status')
]
print(f"可能是LLM错误的条目: {len(llm_error_items)}个")
```

### 2. 按状态分类导出

```python
# 导出需要人工审核的音译数据
transliteration_items = [item for item in data if item.get('cn_name_status') == '音译']
with open('to_review_transliteration.json', 'w', encoding='utf-8') as f:
    json.dump(transliteration_items, f, ensure_ascii=False, indent=2)
```

### 3. 数据质量报告

```python
from collections import Counter

statuses = [item.get('cn_name_status', '成功') or '成功' for item in data]
status_counts = Counter(statuses)

print("数据质量报告:")
for status, count in status_counts.most_common():
    print(f"{status}: {count} ({count/len(data)*100:.1f}%)")
```

## 与其他字段的关系

- 当 `cn_name_status == "未知"` 时，`cn_name` 应该为空
- 当 `cn_name_status == "音译"` 时，`cn_name` 应该包含音译内容
- 当 `cn_name_status == ""` 且 `cn_name != ""` 时，表示成功翻译
- 当两者都为空时，可能是LLM接口错误

## LLM Prompt 规则

在生成时，LLM 会根据以下规则填写此字段：

1. **官方译名**: 如果是知名角色且有官方中文译名 → `cn_name_status: ""`
2. **音译**: 如果是日文/英文角色名但无官方中文名 → `cn_name_status: "音译"`  
3. **未知**: 如果完全无法推断角色来源 → `cn_name_status: "未知"`
4. **LLM错误**: 如果LLM调用失败 → 两个字段都为空 `""`

这种设计使得可以区分"真正的未知"和"LLM错误导致的空值"。
