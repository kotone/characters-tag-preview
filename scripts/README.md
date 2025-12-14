# 角色数据处理脚本使用指南

## 📝 功能说明

`generate_cards_data_async.py` - 异步批量处理动漫角色数据：
- 🌐 从 GitHub URL 获取角色标签数据
- 🤖 使用 LLM 翻译角色名和作品名
- 🖼️ 从 Safebooru 搜索角色图片
- 💾 增量保存，断点续传

## 🚀 快速开始

### 基本用法

```bash
# 生产模式：处理所有数据
python generate_cards_data_async.py

# 调试模式：随机处理10个角色（快速测试）
python generate_cards_data_async.py --debug --limit 10 --random

# 调试模式：按顺序处理前20个
python generate_cards_data_async.py --debug --limit 20
```

## ⚙️ 命令行参数

### 调试选项

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--debug` | 启用调试模式（只处理部分数据） | False |
| `--limit N` | 调试模式下处理的数据量 | 10 |
| `--random` | 随机抽取数据（否则按顺序） | False |

### 并发控制

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--llm-concurrency N` | LLM 并发请求数 | 5 |
| `--img-concurrency N` | 图片搜索并发数 | 10 |
| `--batch-size N` | 批处理大小 | 10 |

## 📊 使用示例

### 1. 开发测试（推荐）
```bash

# 随机测试10个角色，快速验证功能
python generate_cards_data_async.py --debug --limit 10 --random
```

### 2. 小规模验证
```bash
# 处理前100个角色，验证质量
python generate_cards_data_async.py --debug --limit 100
```

### 3. 高性能处理
```bash
# 提高并发数，加快处理速度
python generate_cards_data_async.py --llm-concurrency 10 --img-concurrency 20
```

### 4. 生产环境
```bash
# 跳过版权信息获取 初始化建议使用
python generate_cards_data_async.py --skip-copyright

# 适合正式环境使用
python generate_cards_data_async.py
```

## 🔄 重试机制

脚本内置自动重试功能：
- **LLM 翻译**：失败后重试 3 次，间隔 2 秒（指数退避）
- **图片搜索**：失败后重试 2 次，间隔 1 秒

## 📈 性能统计

运行结束后会显示详细统计报告：

```
==================================================
📊 处理统计报告
==================================================
⏱️  总耗时: 45.23 秒
🎯 总处理: 100 个角色
⚡ 平均速度: 2.21 个/秒

🤖 LLM 翻译:
   ✅ 成功: 98/100 (98.0%)
   ❌ 失败: 2/100 (2.0%)

🖼️  图片搜索:
   ✅ 成功: 85/100 (85.0%)
   ❌ 失败: 15/100 (15.0%)
==================================================
```

## 🛠️ 配置文件

需要设置环境变量（使用 `.env` 文件）：

```env
LLM_API_URL=https://api.deepseek.com/v1/chat/completions
LLM_API_KEY=your_api_key_here
LLM_MODEL=deepseek-chat
```

## 💡 最佳实践

1. **首次运行**：使用 `--debug --limit 10 --random` 快速测试
2. **调整参数**：根据 API 限制调整并发数
3. **观察统计**：关注成功率，失败率过高需检查配置
4. **断点续传**：脚本会自动跳过已处理的数据

## 🐛 故障排查

### LLM 失败率高
- 检查 API Key 是否正确
- 降低 `--llm-concurrency` 避免触发限流
- 查看错误日志确认问题

### 图片搜索失败率高
- Safebooru 可能没有该角色图片（正常现象）
- 降低 `--img-concurrency` 避免被封禁
- 可以稍后手动补充图片

### 程序中断
- 重新运行即可，已处理的数据会自动跳过
- 检查输出文件 `output/character_data.json`
