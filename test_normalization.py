#!/usr/bin/env python3
"""
测试作品名称规范化功能
"""
import json
import sys
import os

# 添加 scripts 目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'scripts'))

# 导入映射文件路径
MAPPING_FILE = os.path.join(os.path.dirname(__file__), 'scripts', 'source_name_mapping.json')

def load_mapping():
    with open(MAPPING_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def normalize_source_names(mapping, source_en, source_cn):
    """简化版的规范化函数用于测试"""
    mappings = mapping.get('mappings', {})
    en_rules = mappings.get('english_normalization', {}).get('rules', {})
    cn_rules = mappings.get('chinese_normalization', {}).get('rules', {})
    standard_pairs = mappings.get('standard_pairs', {}).get('pairs', {})
    
    normalized_en = source_en
    normalized_cn = source_cn
    
    # 规范化英文名
    for standard_en, variants in en_rules.items():
        if source_en in variants:
            normalized_en = standard_en
            break
    
    # 规范化中文名
    for standard_cn, variants in cn_rules.items():
        if source_cn in variants:
            normalized_cn = standard_cn
            break
    
    # 使用标准配对
    if normalized_en in standard_pairs and (not normalized_cn or normalized_cn != standard_pairs[normalized_en]):
        normalized_cn = standard_pairs[normalized_en]
    
    if normalized_cn:
        for std_en, std_cn in standard_pairs.items():
            if normalized_cn == std_cn and (not normalized_en or normalized_en != std_en):
                normalized_en = std_en
                break
    
    return normalized_en, normalized_cn

def test_normalization():
    """测试规范化功能"""
    mapping = load_mapping()
    
    # 测试用例
    test_cases = [
        ("Fate", "命运系列", "Fate/Grand Order", "命运/冠位指定"),
        ("Fate series", "Fate系列", "Fate/Grand Order", "命运/冠位指定"),
        ("fate", "命运冠位指定", "Fate/Grand Order", "命运/冠位指定"),
        ("Blue Archive", "碧蓝档案", "Blue Archive", "蔚蓝档案"),
        ("Uma Musume", "赛马娘", "Uma Musume Pretty Derby", "赛马娘 Pretty Derby"),
        ("Kancolle", "舰队Collection", "Kantai Collection", "舰队Collection"),
        ("Pokemon", "神奇宝贝", "Pokémon", "宝可梦"),
        ("Vocaloid", "初音未来", "Vocaloid", "Vocaloid"),
    ]
    
    print("=" * 80)
    print("🧪 作品名称规范化测试")
    print("=" * 80)
    
    success_count = 0
    for input_en, input_cn, expected_en, expected_cn in test_cases:
        result_en, result_cn = normalize_source_names(mapping, input_en, input_cn)
        
        is_success = (result_en == expected_en and result_cn == expected_cn)
        status = "✅" if is_success else "❌"
        
        print(f"\n{status} 测试用例:")
        print(f"  输入: ({input_en}, {input_cn})")
        print(f"  期望: ({expected_en}, {expected_cn})")
        print(f"  结果: ({result_en}, {result_cn})")
        
        if is_success:
            success_count += 1
        else:
            if result_en != expected_en:
                print(f"  ⚠️  英文名不匹配: {result_en} != {expected_en}")
            if result_cn != expected_cn:
                print(f"  ⚠️  中文名不匹配: {result_cn} != {expected_cn}")
    
    print("\n" + "=" * 80)
    print(f"📊 测试结果: {success_count}/{len(test_cases)} 通过")
    print("=" * 80)
    
    return success_count == len(test_cases)

if __name__ == '__main__':
    success = test_normalization()
    sys.exit(0 if success else 1)
