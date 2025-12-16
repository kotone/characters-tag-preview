"""
角色卡片数据生成主程序 - 模块化版本

异步批量处理动漫角色数据：LLM翻译 + 图片搜索
"""

import asyncio
import argparse
import os
import sys
import aiohttp
from dotenv import load_dotenv
from tqdm.asyncio import tqdm

# 导入自定义模块
from card_generator.config import Config
from card_generator.stats import Stats
from card_generator.file_utils import save_data, load_history_data
from card_generator.llm import load_source_name_mapping
from card_generator.data_processor import (
    load_tags_from_file,
    fetch_tags_from_url,
    apply_debug_filter,
    pipeline_batch
)

# 加载环境变量
load_dotenv()

# 获取脚本基础目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def parse_args(config: Config):
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
    parser.add_argument('--llm-concurrency', type=int, default=config.llm_concurrency,
                        help=f'LLM 并发数（默认: {config.llm_concurrency}）')
    parser.add_argument('--img-concurrency', type=int, default=config.img_concurrency,
                        help=f'图片搜索并发数（默认: {config.img_concurrency}）')
    
    # 批处理配置
    parser.add_argument('--batch-size', type=int, default=config.batch_size,
                        help=f'批处理大小（默认: {config.batch_size}）')
    
    return parser.parse_args()


async def main():
    """主函数"""
    # 初始化配置和统计
    config = Config(BASE_DIR)
    stats = Stats()
    
    # 解析命令行参数
    args = parse_args(config)
    
    # 检查 LLM 配置
    config.check_llm_config()
    
    # 加载作品名称映射表
    source_name_mapping = load_source_name_mapping(config.mapping_file)
    
    # 初始化信号量
    sem_llm = asyncio.Semaphore(args.llm_concurrency)
    sem_img = asyncio.Semaphore(args.img_concurrency)
    
    # 1. 读取输入数据（优先使用缓存，除非强制更新）
    tags_dict = {}
    
    if not args.force_update and os.path.exists(config.cached_source_file):
        # 优先从缓存读取
        print(f"📂 发现本地缓存文件: {config.cached_source_file}")
        tags_dict = load_tags_from_file(config.cached_source_file)
        
        if not tags_dict:
            print("⚠️ 缓存文件无效，尝试从 URL 获取数据")
            tags_dict = await fetch_tags_from_url(config.input_url, config.cached_source_file)
    else:
        # 从 URL 获取数据并缓存
        if args.force_update:
            print("🔄 强制更新模式：从 URL 重新拉取数据")
        else:
            print("📥 本地缓存不存在，从 URL 获取数据")
        tags_dict = await fetch_tags_from_url(config.input_url, config.cached_source_file)
    
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
    print(f"🔄 重试配置: LLM {config.llm_retry_times}次 | Image {config.img_retry_times}次")

    # 2. 读取历史数据
    complete_data, incomplete_tags, existing_tags = load_history_data(
        config.output_file, args.debug
    )

    # 构建待处理的数据列表
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
    timeout = aiohttp.ClientTimeout(total=90)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        
        # 将所有待处理数据分组
        batches = [data_to_process[i : i + args.batch_size] for i in range(0, len(data_to_process), args.batch_size)]
        
        tasks = []
        for batch in batches:
            # 创建所有批次的协程任务
            task = asyncio.create_task(
                pipeline_batch(session, batch, config, sem_llm, sem_img, stats, source_name_mapping)
            )
            tasks.append(task)
        
        # 4. 异步执行并显示进度
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
            if finished_batches % config.save_interval_batches == 0:
                output_file = config.debug_output_file if args.debug else config.output_file
                save_data(current_data, output_file)
        
        pbar.close()
        
        # 最后再一次性保存，确保数据完整
        output_file = config.debug_output_file if args.debug else config.output_file
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
