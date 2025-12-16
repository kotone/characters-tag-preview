"""
统计模块 - 性能统计和报告生成
"""

import time


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
        """打印统计摘要报告"""
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
