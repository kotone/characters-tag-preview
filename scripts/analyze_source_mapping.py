import json
import os
from collections import defaultdict

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, '..', 'output', 'character_data.json')

def analyze_source_mappings():
    """分析作品名称的映射关系，找出不一致的情况"""
    
    # 读取数据
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 统计不同的映射关系
    # 1. source_en -> set of source_cn (一个英文名对应多个中文名)
    en_to_cn = defaultdict(set)
    # 2. source_cn -> set of source_en (一个中文名对应多个英文名)
    cn_to_en = defaultdict(set)
    # 3. (source_en, source_cn) 组合的角色数量
    pair_count = defaultdict(int)
    
    for item in data:
        source_en = item.get('source_en', '').strip()
        source_cn = item.get('source_cn', '').strip()
        
        # 跳过空值
        if not source_en and not source_cn:
            continue
        
        if source_en:
            en_to_cn[source_en].add(source_cn)
        if source_cn:
            cn_to_en[source_cn].add(source_en)
        
        if source_en or source_cn:
            pair_count[(source_en, source_cn)] += 1
    
    # 找出不一致的映射
    print("=" * 80)
    print("📊 作品名称映射分析报告")
    print("=" * 80)
    
    # 1. 一个英文名对应多个中文名的情况
    inconsistent_en = {en: cns for en, cns in en_to_cn.items() if len(cns) > 1}
    print(f"\n🔴 一个英文作品名对应多个中文名的情况: {len(inconsistent_en)} 个\n")
    
    if inconsistent_en:
        for en, cns in sorted(inconsistent_en.items(), key=lambda x: len(x[1]), reverse=True)[:20]:
            print(f"  【{en}】 -> {len(cns)} 个中文名:")
            for cn in sorted(cns):
                count = sum(pair_count[(en, c)] for c in [cn])
                display_cn = f'"{cn}"' if cn else '(空)'
                print(f"     - {display_cn} ({count} 个角色)")
            print()
    
    # 2. 一个中文名对应多个英文名的情况
    inconsistent_cn = {cn: ens for cn, ens in cn_to_en.items() if len(ens) > 1 and cn}
    print(f"\n🟡 一个中文作品名对应多个英文名的情况: {len(inconsistent_cn)} 个\n")
    
    if inconsistent_cn:
        for cn, ens in sorted(inconsistent_cn.items(), key=lambda x: len(x[1]), reverse=True)[:20]:
            print(f"  【{cn}】 -> {len(ens)} 个英文名:")
            for en in sorted(ens):
                count = sum(pair_count[(e, cn)] for e in [en])
                display_en = f'"{en}"' if en else '(空)'
                print(f"     - {display_en} ({count} 个角色)")
            print()
    
    # 3. 总体统计
    print("=" * 80)
    print("📈 总体统计")
    print("=" * 80)
    print(f"总角色数: {len(data)}")
    print(f"不同的英文作品名: {len(en_to_cn)}")
    print(f"不同的中文作品名: {len([cn for cn in cn_to_en.keys() if cn])}")
    print(f"不同的(英文,中文)组合: {len(pair_count)}")
    print(f"\n需要规范化的映射:")
    print(f"  - 英文名不一致: {len(inconsistent_en)} 个")
    print(f"  - 中文名不一致: {len(inconsistent_cn)} 个")
    print(f"  - 总计需要处理: {len(inconsistent_en) + len(inconsistent_cn)} 个")
    print("=" * 80)
    
    # 4. 列出一些具体的 Fate 系列例子
    print("\n🎯 Fate 系列的映射情况:")
    fate_mappings = {}
    for (en, cn), count in pair_count.items():
        if 'fate' in en.lower() or 'fate' in cn.lower() or '命运' in cn:
            if en not in fate_mappings:
                fate_mappings[en] = []
            fate_mappings[en].append((cn, count))
    
    for en in sorted(fate_mappings.keys()):
        print(f"\n  {en}:")
        for cn, count in sorted(fate_mappings[en], key=lambda x: -x[1]):
            display_cn = f'"{cn}"' if cn else '(空)'
            print(f"    - {display_cn}: {count} 个角色")

if __name__ == '__main__':
    analyze_source_mappings()
