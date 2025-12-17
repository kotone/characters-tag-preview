"""
测试 Character Tag Selector 节点
"""

import sys
import os

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(__file__))

from character_tag_selector import CharacterTagSelector

def test_node():
    """测试节点功能"""
    print("=" * 60)
    print("🧪 测试 Character Tag Selector 节点")
    print("=" * 60)
    
    # 创建节点实例
    node = CharacterTagSelector()
    
    print(f"\n📊 已加载数据源: {list(node.all_data.keys())}")
    
    # 显示每个数据源的角色数量
    for source, characters in node.all_data.items():
        print(f"  - {source}: {len(characters)} 个角色")
    
    # 测试所有输出格式
    print("\n" + "=" * 60)
    print("🏷️  测试所有输出格式")
    print("=" * 60)
    
    test_character = ("崩坏：星穹铁道", "大丽花 (The Dahlia)")
    
    for output_type in node.OUTPUT_TYPES_MAP.keys():
        result = node.generate_tag(test_character[0], test_character[1], output_type)
        print(f"\n✅ {output_type}")
        print(f"   结果: {result[0]}")
    
    # 测试不同游戏的标签生成
    print("\n" + "=" * 60)
    print("� 测试不同游戏的Danbooru标签")
    print("=" * 60)
    
    test_cases = [
        ("原神", "雅珂达 (Jahoda)"),
        ("崩坏：星穹铁道", "大丽花 (The Dahlia)"),
        ("绝区零", "艾莲·乔 (Ellen Joe)"),
        ("鸣潮", "千咲 (Chisa)"),
    ]
    
    for test_case in test_cases:
        if test_case:
            source, character = test_case
            result = node.generate_tag(source, character, "Danbooru标签 (推荐)")
            print(f"\n✅ {source} - {character}")
            print(f"   标签: {result[0]}")
    
    print("\n" + "=" * 60)
    print("✅ 测试完成！")
    print("=" * 60)


if __name__ == '__main__':
    test_node()
