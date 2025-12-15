import json
import os
from collections import defaultdict

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, '..', 'output', 'noob_characters-chants-en-cn.json')
MAPPING_FILE = os.path.join(BASE_DIR, 'source_name_mapping.json')

def analyze_source_mappings():
    """分析作品名称的映射关系，找出不一致的情况，并生成建议的规范化规则"""
    
    # 读取数据
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"❌ 错误: 找不到数据文件 {DATA_FILE}")
        print("💡 提示: 请先运行 generate_cards_data_async.py 生成数据")
        return
    
    # 读取现有的映射规则
    existing_mappings = {}
    try:
        with open(MAPPING_FILE, 'r', encoding='utf-8') as f:
            mapping_data = json.load(f)
            existing_mappings = mapping_data.get('mappings', {})
    except FileNotFoundError:
        print(f"⚠️ 警告: 映射表文件不存在: {MAPPING_FILE}")
    
    # 统计不同的映射关系
    # 1. source_en -> set of source_cn (一个英文名对应多个中文名)
    en_to_cn = defaultdict(set)
    # 2. source_cn -> set of source_en (一个中文名对应多个英文名)
    cn_to_en = defaultdict(set)
    # 3. (source_en, source_cn) 组合的角色数量
    pair_count = defaultdict(int)
    # 4. 空值统计
    empty_en_count = 0
    empty_cn_count = 0
    both_empty_count = 0
    
    for item in data:
        source_en = item.get('source_en', '').strip()
        source_cn = item.get('source_cn', '').strip()
        
        # 统计空值
        if not source_en and not source_cn:
            both_empty_count += 1
            continue
        elif not source_en:
            empty_en_count += 1
        elif not source_cn:
            empty_cn_count += 1
        
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
    
    # 0. 数据质量统计
    print(f"\n📈 数据质量统计")
    print(f"  总角色数: {len(data)}")
    print(f"  英文名为空: {empty_en_count} 个 ({empty_en_count/len(data)*100:.1f}%)")
    print(f"  中文名为空: {empty_cn_count} 个 ({empty_cn_count/len(data)*100:.1f}%)")
    print(f"  英文+中文均为空: {both_empty_count} 个 ({both_empty_count/len(data)*100:.1f}%)")
    
    # 1. 一个英文名对应多个中文名的情况
    inconsistent_en = {en: cns for en, cns in en_to_cn.items() if len(cns) > 1}
    print(f"\n🔴 一个英文作品名对应多个中文名的情况: {len(inconsistent_en)} 个\n")
    
    if inconsistent_en:
        # 按不一致程度排序（中文名数量越多越严重）
        sorted_inconsistent = sorted(inconsistent_en.items(), key=lambda x: len(x[1]), reverse=True)
        
        for en, cns in sorted_inconsistent[:20]:
            # 计算总角色数
            total_chars = sum(pair_count[(en, cn)] for cn in cns)
            print(f"  【{en}】{len(cns)} 个中文名，共 {total_chars} 个角色:")
            
            # 按角色数量排序，显示哪个是最常用的
            cn_with_count = [(cn, pair_count[(en, cn)]) for cn in cns]
            cn_with_count.sort(key=lambda x: x[1], reverse=True)
            
            for cn, count in cn_with_count:
                display_cn = f'"{cn}"' if cn else '(空)'
                percentage = count / total_chars * 100
                marker = "👑" if count == cn_with_count[0][1] else "  "
                print(f"     {marker} {display_cn}: {count} 个角色 ({percentage:.1f}%)")
            print()
    
    # 2. 一个中文名对应多个英文名的情况
    inconsistent_cn = {cn: ens for cn, ens in cn_to_en.items() if len(ens) > 1 and cn}
    print(f"\n🟡 一个中文作品名对应多个英文名的情况: {len(inconsistent_cn)} 个\n")
    
    if inconsistent_cn:
        sorted_inconsistent = sorted(inconsistent_cn.items(), key=lambda x: len(x[1]), reverse=True)
        
        for cn, ens in sorted_inconsistent[:20]:
            total_chars = sum(pair_count[(en, cn)] for en in ens)
            print(f"  【{cn}】{len(ens)} 个英文名，共 {total_chars} 个角色:")
            
            en_with_count = [(en, pair_count[(en, cn)]) for en in ens]
            en_with_count.sort(key=lambda x: x[1], reverse=True)
            
            for en, count in en_with_count:
                display_en = f'"{en}"' if en else '(空)'
                percentage = count / total_chars * 100
                marker = "👑" if count == en_with_count[0][1] else "  "
                print(f"     {marker} {display_en}: {count} 个角色 ({percentage:.1f}%)")
            print()
    
    # 3. 检查哪些不一致的映射还没有被规范化规则覆盖
    print(f"\n🔍 未被映射表覆盖的不一致情况\n")
    
    en_rules = existing_mappings.get('english_normalization', {}).get('rules', {})
    cn_rules = existing_mappings.get('chinese_normalization', {}).get('rules', {})
    standard_pairs = existing_mappings.get('standard_pairs', {}).get('pairs', {})
    
    uncovered_en = []
    uncovered_cn = []
    
    # 检查英文名不一致且未被覆盖
    for en, cns in inconsistent_en.items():
        # 检查这个英文名是否在任何规则中
        is_covered = False
        for standard_name, variants in en_rules.items():
            if en in variants or en == standard_name:
                is_covered = True
                break
        
        if not is_covered:
            total_chars = sum(pair_count[(en, cn)] for cn in cns)
            uncovered_en.append((en, cns, total_chars))
    
    # 检查中文名不一致且未被覆盖
    for cn, ens in inconsistent_cn.items():
        is_covered = False
        for standard_name, variants in cn_rules.items():
            if cn in variants or cn == standard_name:
                is_covered = True
                break
        
        if not is_covered:
            total_chars = sum(pair_count[(en, cn)] for en in ens)
            uncovered_cn.append((cn, ens, total_chars))
    
    # 按影响角色数排序
    uncovered_en.sort(key=lambda x: x[2], reverse=True)
    uncovered_cn.sort(key=lambda x: x[2], reverse=True)
    
    if uncovered_en:
        print(f"  ⚠️ 英文名未覆盖: {len(uncovered_en)} 个\n")
        for en, cns, total_chars in uncovered_en[:10]:
            print(f"    【{en}】影响 {total_chars} 个角色")
            for cn in sorted(cns):
                count = pair_count[(en, cn)]
                display_cn = f'"{cn}"' if cn else '(空)'
                print(f"       -> {display_cn} ({count})")
            print()
    else:
        print("  ✅ 所有英文名不一致问题均已被映射表覆盖")
    
    if uncovered_cn:
        print(f"  ⚠️ 中文名未覆盖: {len(uncovered_cn)} 个\n")
        for cn, ens, total_chars in uncovered_cn[:10]:
            print(f"    【{cn}】影响 {total_chars} 个角色")
            for en in sorted(ens):
                count = pair_count[(en, cn)]
                display_en = f'"{en}"' if en else '(空)'
                print(f"       -> {display_en} ({count})")
            print()
    else:
        print("  ✅ 所有中文名不一致问题均已被映射表覆盖")
    
    # 4. 总体统计
    print("\n" + "=" * 80)
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
    print(f"\n映射表覆盖情况:")
    print(f"  - 英文规则数: {len(en_rules)}")
    print(f"  - 中文规则数: {len(cn_rules)}")
    print(f"  - 标准配对数: {len(standard_pairs)}")
    print(f"  - 未覆盖的英文不一致: {len(uncovered_en)} 个")
    print(f"  - 未覆盖的中文不一致: {len(uncovered_cn)} 个")
    
    coverage_rate = (1 - (len(uncovered_en) + len(uncovered_cn)) / (len(inconsistent_en) + len(inconsistent_cn))) * 100 if (len(inconsistent_en) + len(inconsistent_cn)) > 0 else 100
    print(f"  - 覆盖率: {coverage_rate:.1f}%")
    print("=" * 80)
    
    # 5. 生成建议的映射规则（如果有未覆盖的）
    if uncovered_en or uncovered_cn:
        print(f"\n💡 建议添加到 source_name_mapping.json 的规则:\n")
        
        if uncovered_en:
            print("  英文规范化建议（添加到 english_normalization.rules）:")
            for en, cns, total_chars in uncovered_en[:5]:
                print(f"    \"{en}\": [")
                print(f"        \"{en}\"")
                print(f"    ],")
            print()
        
        if uncovered_cn:
            print("  中文规范化建议（添加到 chinese_normalization.rules）:")
            for cn, ens, total_chars in uncovered_cn[:5]:
                print(f"    \"{cn}\": [")
                print(f"        \"{cn}\"")
                print(f"    ],")
            print()

if __name__ == '__main__':
    analyze_source_mappings()
