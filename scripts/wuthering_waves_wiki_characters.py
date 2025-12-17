"""
鸣潮（Wuthering Waves）- 获取角色列表（中英文合并）
从 mc.appfeng.com API 获取鸣潮所有角色的中英文信息
"""

import requests
import json
import os
from typing import List, Dict


class WutheringWavesAPI:
    """鸣潮 API 客户端"""
    
    BASE_URL = "https://mc.appfeng.com/json/avatar.json"
    
    # 请求头配置
    DEFAULT_HEADERS = {
        "accept": "*/*",
        "accept-language": "zh-CN,zh;q=0.9,en;q=0.8,en-US;q=0.7",
        "sec-ch-ua": "\"Chromium\";v=\"136\", \"Google Chrome\";v=\"136\", \"Not.A/Brand\";v=\"99\"",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "\"Windows\"",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "Referer": "https://mc.appfeng.com/avatar",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
    }
    
    def __init__(self, timeout: int = 10):
        self.timeout = timeout
    
    def get_character_list(self) -> List[Dict]:
        """
        获取角色列表
        
        Returns:
            角色列表（已包含中英文数据）
        """
        # 添加版本参数（可能用于缓存控制）
        params = {"v": "10075"}
        
        try:
            response = requests.get(
                self.BASE_URL,
                params=params,
                headers=self.DEFAULT_HEADERS,
                timeout=self.timeout
            )
            
            if response.status_code != 200:
                print(f"❌ HTTP 错误: {response.status_code}")
                return []
            
            data = response.json()
            
            if not isinstance(data, list):
                print(f"❌ 返回数据格式错误: 期望数组，得到 {type(data)}")
                return []
            
            print(f"📥 已获取 {len(data)} 个角色")
            
            return data
            
        except Exception as e:
            print(f"❌ 请求失败: {e}")
            return []
    
    def transform_character_data(self, raw_list: List[Dict]) -> List[Dict]:
        """
        转换角色数据为统一格式
        
        Args:
            raw_list: 原始角色列表
        
        Returns:
            转换后的角色列表
        """
        transformed = []
        
        for char in raw_list:
            # 获取英文名并生成tag
            name_en = char.get('en', '')
            name_cn = char.get('name', '')
            
            # 将英文名转为tag格式：小写，空格和特殊字符转为下划线
            tag_name = name_en.lower().replace(' ', '_').replace('-', '_').replace('•', '_').replace(':', '')
            # 移除多余下划线
            tag_name = '_'.join(filter(None, tag_name.split('_')))
            
            # 构建icon_url: https://mc.appfeng.com/ui/avatar/ + iconhalf + .png
            icon_half = char.get('iconhalf', '')
            icon_url = f"https://mc.appfeng.com/ui/avatar/{icon_half}.png" if icon_half else ''
            
            # 只保留必要字段，与星铁格式保持一致
            transformed_char = {
                'name_cn': name_cn,
                'name_en': name_en,
                'tag': f"{tag_name}_(wuthering_waves)" if tag_name else '',
                'source': 'wuthering_waves',
                'source_cn': '鸣潮',
                'icon_url': icon_url,
                'header_img_url': ''
            }
            
            transformed.append(transformed_char)
        
        return transformed
    
    def get_transformed_character_list(self) -> List[Dict]:
        """
        获取并转换角色列表
        
        Returns:
            转换后的角色列表
        """
        print("=" * 60)
        print("📚 开始获取鸣潮角色列表...")
        print("=" * 60)
        
        # 获取原始数据
        print("\n1️⃣ 获取角色数据...")
        raw_list = self.get_character_list()
        
        # 转换数据格式
        print("\n2️⃣ 转换数据格式...")
        transformed = self.transform_character_data(raw_list)
        
        print(f"\n✅ 转换完成！共 {len(transformed)} 个角色")
        
        return transformed


def main():
    """主函数"""
    
    # 创建 API 客户端
    api = WutheringWavesAPI()
    
    # 获取脚本所在目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # 项目根目录：向上一级到 characters-tag-preview/
    project_root = os.path.normpath(os.path.join(script_dir, '..'))
    # output 文件夹在项目根目录下
    output_dir = os.path.join(project_root, 'output')
    
    # 确保 output 目录存在
    os.makedirs(output_dir, exist_ok=True)
    
    print("=" * 60)
    print("📚 开始获取鸣潮角色列表...")
    print("=" * 60)
    
    # 获取原始数据
    print("\n1️⃣ 获取角色数据...")
    raw_list = api.get_character_list()
    
    if not raw_list:
        print("❌ 未能获取到角色数据")
        return
    
    # 转换数据格式
    print("\n2️⃣ 转换数据格式...")
    transformed_list = api.transform_character_data(raw_list)
    
    print(f"\n✅ 转换完成！共 {len(transformed_list)} 个角色")
    
    # 保存转换后的数据到 output 文件夹
    print("\n💾 保存数据...")
    
    output_file = os.path.join(output_dir, 'wuthering_waves_characters-en-cn.json')
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(transformed_list, f, ensure_ascii=False, indent=2)
    print(f"✅ 已保存: {os.path.basename(output_file)} ({len(transformed_list)} 个角色)")
    
    # 显示部分数据示例
    print("\n" + "=" * 60)
    print("📊 角色列表示例（前 5 个）:")
    print("=" * 60)
    
    for i, char in enumerate(transformed_list[:5], 1):
        print(f"\n【{i}】 {char['name_cn']} ({char['name_en']})")
        print(f"  标签: {char['tag']}")
        if char.get('icon_url'):
            print(f"  图标: {char['icon_url']}")
    
    print("\n" + "=" * 60)
    print(f"✨ 完成！数据已保存至: {output_file}")
    print("=" * 60)


if __name__ == '__main__':
    main()
