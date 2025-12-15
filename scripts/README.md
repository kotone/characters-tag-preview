# generate_cards_data_async.py 使用指南

## 📖 目录

- [功能概述](#功能概述)
- [环境配置](#环境配置)
- [快速开始](#快速开始)
- [命令行参数](#命令行参数)
- [使用示例](#使用示例)
- [故障排查](#故障排查)

---

## 📝 功能概述

`generate_cards_data_async.py` 是一个高性能的异步批量角色数据处理脚本，主要功能包括：

- 🌐 **数据获取**：从 GitHub URL 获取角色标签数据（支持本地缓存）
- 🤖 **智能翻译**：使用 LLM API 翻译角色名和作品名（中英双语）
- 📋 **名称规范化**：基于映射表自动统一作品名称
- 🖼️ **图片搜索**：从 Safebooru 自动搜索角色图片
- 💾 **增量保存**：支持断点续传，已处理数据自动跳过
- ⚡ **高并发处理**：异步并发处理，速度快、效率高

---

## 🛠️ 环境配置

### 必需的环境变量

在项目根目录创建 `.env` 文件：

```env
LLM_API_URL=https://api.openai.com/v1/chat/completions
LLM_API_KEY=your_api_key_here
LLM_MODEL=model_name_here
```

### 目录结构

```
characters-tag-preview-1.1/
├── data/                                    # 数据缓存目录（自动创建）
│   └── noob_characters-chants.json         # 缓存的源数据文件
├── output/                                  # 输出目录
│   └── noob_characters-chants-en-cn.json   # 处理后的输出文件
└── scripts/                                 # 脚本目录
    ├── generate_cards_data_async.py        # 主脚本
    ├── analyze_source_mapping.py           # 映射分析工具
    └── source_name_mapping.json            # 作品名称映射表
```




---

## ⚙️ 命令行参数

### 数据处理选项

| 参数 | 类型 | 说明 | 默认值 |
|------|------|------|--------|
| `--limit N` | int | 限制处理的数据量（0 表示不限制） | 0 |
| `--random` | flag | 随机抽取数据（否则按顺序） | False |
| `--force-update` | flag | 强制从 URL 重新拉取源数据 | False |
| `--debug` | flag | 调试模式，输出单独的调试结果文件 | False |

### 并发控制选项

| 参数 | 类型 | 说明 | 默认值 |
|------|------|------|--------|
| `--llm-concurrency N` | int | LLM 并发请求数 | 5 |
| `--img-concurrency N` | int | 图片搜索并发数 | 10 |
| `--batch-size N` | int | 批处理大小 | 10 |

---

## 📊 使用示例

### 1. 开发测试（debug 模式）
```bash
python generate_cards_data_async.py --debug --limit 20
```
✅ 快速启动，节省时间  
✅ 不影响正式产物

### 2. 生产环境完整运行

```bash
# 处理所有数据（耗时较长）
python generate_cards_data_async.py

# 支持断点续传，中断后重新运行会自动跳过已处理数据
```

### 3. 高性能处理

```bash
# 提高并发数，加快处理速度（注意 API 限流）
python generate_cards_data_async.py --llm-concurrency 10 --img-concurrency 20

# 适合有高并发配额的 API
```

### 4. 强制更新数据

```bash
# 获取最新的上游数据
python generate_cards_data_async.py --force-update --limit 100

# 输出示例：
# 🔄 强制更新模式：从 URL 重新拉取数据
# 📥 正在从 URL 获取数据: https://...
# 💾 原始数据已缓存至: E:\...\data\noob_characters-chants.json
```


### 重试机制

脚本内置自动重试功能，提高成功率：

- **LLM 翻译**：失败后重试 3 次，间隔 2 秒（指数退避）
- **图片搜索**：失败后重试 2 次，间隔 1 秒

### 断点续传

- 已处理的完整数据会自动保存
- 重新运行时自动跳过已处理的角色
- 只处理新增或不完整的数据

### 定期存盘

- 每处理 5 个批次自动保存一次
- 减少内存占用
- 防止数据丢失

---


### 输出文件格式

`output/noob_characters-chants-en-cn.json`:

```json
[
  {
    "tag": "hakurei_reimu",
    "cn_name": "博丽灵梦",
    "cn_name_status": "官方译名",
    "en_name": "Hakurei Reimu",
    "source_cn": "东方Project",
    "source_en": "Touhou Project",
    "cn_source_status": "官方译名",
    "color": 4,
    "content": "hakurei reimu, ...",
    "image_url": "https://safebooru.org/images/..."
  }
]
```

## 🐛 故障排查

### LLM 翻译失败率高

**可能原因：**
- ❌ API Key 错误或过期
- ❌ 触发 API 限流
- ❌ 网络不稳定

**解决方法：**
```bash
# 1. 检查 .env 文件中的 API Key
cat ../.env

# 2. 降低并发数避免限流
python generate_cards_data_async.py --llm-concurrency 3 --limit 50

# 3. 查看详细错误日志
# 脚本会输出具体的错误信息
```

### 图片搜索失败率高

**正常情况：**
- ✅ 15-30% 的失败率是正常的
- ✅ Safebooru 并非所有角色都有图片

**异常情况（失败率 > 50%）：**
```bash
# 降低图片搜索并发，避免被封禁
python generate_cards_data_async.py --img-concurrency 5
```

### 程序中断

**解决方法：**
```bash
# 直接重新运行即可，已处理的数据会自动跳过
python generate_cards_data_async.py

# 检查输出文件确认进度
cat ../output/noob_characters-chants-en-cn.json | jq length
```

### 缓存文件损坏

**症状：**
```
⚠️ 警告: 缓存文件格式不正确
⚠️ 缓存文件无效，尝试从 URL 获取数据
```

**解决方法：**
```bash
# 强制重新下载
python generate_cards_data_async.py --force-update
```

### 环境变量未配置

**症状：**
```
❌ 错误：环境变量 LLM_API_URL 未配置！
💡 提示：请设置系统环境变量，或使用 .env 文件。
```

**解决方法：**
1. 检查 `.env` 文件是否存在于项目根目录
2. 确认 `.env` 文件包含必需的配置项
3. 重新运行脚本

---

## 📚 相关工具

### analyze_source_mapping.py

分析 LLM 翻译的作品名称一致性，帮助完善映射表：

```bash
# 运行分析
python analyze_source_mapping.py

# 查看不一致的映射
# 根据建议完善 source_name_mapping.json
```
---

