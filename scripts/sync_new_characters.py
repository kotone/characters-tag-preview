"""
同步新角色数据
将 Wiki 获取的最新角色数据同步到主数据文件中
"""

import json
import os
import sys
from typing import List, Dict, Set

import json
import os
import sys
from typing import List, Dict, Set


def normalize_name(name: str) -> str:
    """标准化名称"""
    return name.strip().lower()


def load_json(path: str) -> List[Dict]:
    """加载 JSON 文件"""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"⚠️ 文件未找到: {path}")
        return []
    except Exception as e:
        print(f"❌ 加载失败 {path}: {e}")
        return []


def save_json(path: str, data: List[Dict]):
    """保存 JSON 文件"""
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"✅ 已保存: {path}")
    except Exception as e:
        print(f"❌ 保存失败 {path}: {e}")


def main():
    print("=" * 60)
    print("🔄 开始同步新角色数据...")
    print("=" * 60)
    
    # 路径配置
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.normpath(os.path.join(script_dir, '..'))
    output_dir = os.path.join(project_root, 'output')
    
    main_data_file = os.path.join(output_dir, 'noob_characters-chants-en-cn.json')
    genshin_file = os.path.join(output_dir, 'genshin_characters-en-cn.json')
    starrail_file = os.path.join(output_dir, 'honkai_starrail_characters-en-cn.json')
    
    # 1. 加载主数据
    main_data = load_json(main_data_file)
    print(f"📊 主数据包含 {len(main_data)} 条记录")
    
    # 建立现有标签集合（用于去重）
    existing_tags = set()
    for item in main_data:
        tag = item.get('tag', '')
        if tag:
            existing_tags.add(tag.lower())
    
    # 2. 同步原神数据
    print("\n🔍 检查原神新角色...")
    genshin_data = load_json(genshin_file)
    new_genshin_count = 0
    
    for char in genshin_data:
        tag = char.get('tag', '')
        if not tag:
            continue
            
        if tag.lower() not in existing_tags:
            # 发现新角色
            new_item = {
                "tag": tag,
                "tag_cn": char.get('name_cn', ''),
                "tag_en": char.get('name_en', ''),
                "source": char.get('source', 'genshin_impact'),
                "source_cn": char.get('source_cn', '原神'),
                "image_url": char.get('icon_url', ''),
                "character_id": char.get('entry_page_id', ''),
                # 添加默认空字段以保持格式一致
                "desc": "",
                "desc_cn": "",
                "chant": "",
                "chant_cn": ""
            }
            main_data.append(new_item)
            existing_tags.add(tag.lower())
            new_genshin_count += 1
            print(f"  ✨ 添加: {char['name_cn']} ({tag})")
    
    print(f"  ✅ 新增 {new_genshin_count} 个原神角色")
    
    # 3. 同步星铁数据
    print("\n🔍 检查星铁新角色...")
    starrail_data = load_json(starrail_file)
    new_starrail_count = 0
    
    for char in starrail_data:
        tag = char.get('tag', '')
        if not tag:
            continue
            
        if tag.lower() not in existing_tags:
            # 发现新角色
            new_item = {
                "tag": tag,
                "tag_cn": char.get('name_cn', ''),
                "tag_en": char.get('name_en', ''),
                "source": char.get('source', 'honkai_starrail'),
                "source_cn": char.get('source_cn', '崩坏：星穹铁道'),
                "image_url": char.get('icon_url', ''),
                "character_id": char.get('entry_page_id', ''),
                # 添加默认空字段
                "desc": "",
                "desc_cn": "",
                "chant": "",
                "chant_cn": ""
            }
            main_data.append(new_item)
            existing_tags.add(tag.lower())
            new_starrail_count += 1
            print(f"  ✨ 添加: {char['name_cn']} ({tag})")
    
    print(f"  ✅ 新增 {new_starrail_count} 个星铁角色")
    
    # 4. 保存结果
    if new_genshin_count > 0 or new_starrail_count > 0:
        print("\n💾 保存更新后的数据...")
        save_json(main_data_file, main_data)
        print(f"🎉 同步完成！共新增 {new_genshin_count + new_starrail_count} 个角色")
    else:
        print("\n✨ 数据已是最新，无需更新")


if __name__ == '__main__':
    main()
