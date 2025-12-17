"""
绝区零 Wiki API - 获取角色列表（中英文合并）
从 HoYoLAB Wiki API 获取绝区零所有角色的中英文信息
"""

import requests
import json
import time
import os
from typing import List, Dict, Optional


class ZZZWikiAPI:
    """绝区零 Wiki API 客户端"""
    
    BASE_URL = "https://sg-wiki-api.hoyolab.com/hoyowiki/zzz/wapi"
    
    # 精简的请求头配置
    DEFAULT_HEADERS = {
        "accept": "application/json, text/plain, */*",
        "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
        "content-type": "application/json;charset=UTF-8",
        "referer": "https://wiki.hoyolab.com/",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
        # HoYoLAB API 必需的header
        "x-rpc-language": "zh-cn",
        "x-rpc-wiki_app": "zzz"
    }
    
    def __init__(self, timeout: int = 10):
        self.timeout = timeout
    
    def get_character_list(self, language: str = "zh-cn", page_size: int = 30) -> List[Dict]:
        """
        获取角色列表
        
        Args:
            language: 语言代码 ("zh-cn" 中文, "en-us" 英文)
            page_size: 每页数量
        
        Returns:
            角色列表
        """
        url = f"{self.BASE_URL}/get_entry_page_list"
        
        # 更新语言 header
        headers = self.DEFAULT_HEADERS.copy()
        headers["x-rpc-language"] = language
        
        all_characters = []
        page_num = 1
        
        while True:
            payload = {
                "filters": [],
                "menu_id": "8",  # 绝区零角色菜单ID
                "page_num": page_num,
                "page_size": page_size,
                "use_es": True
            }
            
            try:
                response = requests.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=self.timeout
                )
                
                if response.status_code != 200:
                    print(f"❌ HTTP 错误: {response.status_code}")
                    break
                
                data = response.json()
                
                if data.get('retcode') != 0:
                    print(f"❌ API 返回错误: retcode={data.get('retcode')}, message={data.get('message')}")
                    break
                
                # 提取角色列表
                page_data = data.get('data', {})
                characters = page_data.get('list', [])
                total = int(page_data.get('total', 0))  # 确保是整数
                
                if not characters:
                    break
                
                all_characters.extend(characters)
                
                print(f"📥 已获取 {len(all_characters)}/{total} 个角色 (语言: {language})")
                
                # 检查是否还有更多数据
                if len(all_characters) >= total:
                    break
                
                page_num += 1
                time.sleep(0.5)  # 避免请求过快
                
            except Exception as e:
                print(f"❌ 请求失败: {e}")
                break
        
        return all_characters
    
    def merge_character_data(self, cn_list: List[Dict], en_list: List[Dict]) -> List[Dict]:
        """
        合并中英文角色数据
        
        Args:
            cn_list: 中文角色列表
            en_list: 英文角色列表
        
        Returns:
            合并后的角色列表，只包含关键字段
        """
        # 使用 entry_page_id 作为唯一标识建立映射
        en_map = {char.get('entry_page_id'): char for char in en_list}
        
        merged = []
        
        for cn_char in cn_list:
            entry_id = cn_char.get('entry_page_id')
            en_char = en_map.get(entry_id, {})
            
            # 获取英文名并生成tag
            name_en = en_char.get('name', '')
            # 将英文名转为tag格式：小写，空格和特殊字符转为下划线
            tag_name = name_en.lower().replace(' ', '_').replace('-', '_').replace('•', '_')
            # 移除多余下划线
            tag_name = '_'.join(filter(None, tag_name.split('_')))
            
            # 只保留必要字段
            merged_char = {
                'entry_page_id': entry_id,
                'name_cn': cn_char.get('name', ''),
                'name_en': name_en,
                'tag': f"{tag_name}_(zenless_zone_zero)" if tag_name else '',
                'source': 'zenless_zone_zero',
                'source_cn': '绝区零',
                'icon_url': cn_char.get('icon_url', ''),
                'header_img_url': cn_char.get('header_img_url', '')
            }
            
            merged.append(merged_char)
        
        return merged
    
    def get_merged_character_list(self) -> List[Dict]:
        """
        获取中英文合并的角色列表
        
        Returns:
            合并后的角色列表
        """
        print("=" * 60)
        print("📚 开始获取绝区零角色列表...")
        print("=" * 60)
        
        # 获取中文列表
        print("\n1️⃣ 获取中文角色列表...")
        cn_list = self.get_character_list(language="zh-cn")
        
        # 获取英文列表
        print("\n2️⃣ 获取英文角色列表...")
        en_list = self.get_character_list(language="en-us")
        
        # 合并数据
        print("\n3️⃣ 合并中英文数据...")
        merged = self.merge_character_data(cn_list, en_list)
        
        print(f"\n✅ 合并完成！共 {len(merged)} 个角色")
        
        return merged


def main():
    """主函数"""
    
    # 创建 API 客户端
    api = ZZZWikiAPI()
    
    # 获取脚本所在目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # 项目根目录：向上一级到 characters-tag-preview/
    project_root = os.path.normpath(os.path.join(script_dir, '..'))
    # output 文件夹在项目根目录下
    output_dir = os.path.join(project_root, 'output')
    
    # 确保 output 目录存在
    os.makedirs(output_dir, exist_ok=True)
    
    print("=" * 60)
    print("📚 开始获取绝区零角色列表...")
    print("=" * 60)
    
    # 获取中文列表
    print("\n1️⃣ 获取中文角色列表...")
    cn_list = api.get_character_list(language="zh-cn")
    
    # 获取英文列表
    print("\n2️⃣ 获取英文角色列表...")
    en_list = api.get_character_list(language="en-us")
    
    # 合并数据
    print("\n3️⃣ 合并中英文数据...")
    merged_list = api.merge_character_data(cn_list, en_list)
    
    print(f"\n✅ 合并完成！共 {len(merged_list)} 个角色")
    
    # 保存合并数据到 output 文件夹
    print("\n💾 保存数据...")
    
    output_file = os.path.join(output_dir, 'zzz_characters-en-cn.json')
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(merged_list, f, ensure_ascii=False, indent=2)
    print(f"✅ 已保存: {os.path.basename(output_file)} ({len(merged_list)} 个角色)")
    
    # 显示部分数据示例
    print("\n" + "=" * 60)
    print("📊 角色列表示例（前 5 个）:")
    print("=" * 60)
    
    for i, char in enumerate(merged_list[:5], 1):
        print(f"\n【{i}】 {char['name_cn']} ({char['name_en']})")
        print(f"  ID: {char['entry_page_id']}")
        print(f"  Tag: {char['tag']}")
        if char.get('icon_url'):
            print(f"  头像: {char['icon_url'][:60]}...")
    
    print("\n" + "=" * 60)
    print(f"✨ 完成！数据已保存至: {output_file}")
    print("=" * 60)


if __name__ == '__main__':
    main()
