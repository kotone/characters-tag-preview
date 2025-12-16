"""
配置管理模块 - 配置加载和环境变量管理
"""

import json
import os
import sys
from typing import Optional, Dict


class Config:
    """配置管理类"""
    
    def __init__(self, base_dir: str):
        """
        初始化配置
        
        Args:
            base_dir: 脚本基础目录
        """
        self.base_dir = base_dir
        self.config_data = self._load_config()
        self._init_from_config()
        self._load_env_vars()
    
    def _load_config(self) -> Optional[Dict]:
        """加载配置文件"""
        config_file = os.path.join(self.base_dir, 'config.json')
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            return config
        except FileNotFoundError:
            print(f"⚠️ 警告: 配置文件不存在 {config_file}，使用默认配置")
            return None
        except Exception as e:
            print(f"⚠️ 警告: 加载配置文件失败: {e}，使用默认配置")
            return None
    
    def _init_from_config(self):
        """从配置数据初始化参数"""
        if self.config_data:
            # LLM 配置
            self.batch_size = self.config_data['llm'].get('batch_size', 10)
            self.llm_concurrency = self.config_data['llm'].get('concurrency', 5)
            self.llm_retry_times = self.config_data['llm'].get('retry_times', 3)
            self.llm_retry_delay = self.config_data['llm'].get('retry_delay', 2)
            
            # 图片配置
            self.img_concurrency = self.config_data['image'].get('concurrency', 10)
            self.img_retry_times = self.config_data['image'].get('retry_times', 2)
            self.img_retry_delay = self.config_data['image'].get('retry_delay', 1)
            
            # 处理配置
            self.save_interval_batches = self.config_data['processing'].get('save_interval_batches', 5)
            
            # 路径配置
            self.input_url = self.config_data['paths'].get('input_url')
            self.output_file = os.path.join(self.base_dir, self.config_data['paths'].get('output_file'))
            self.debug_output_file = os.path.join(self.base_dir, self.config_data['paths'].get('debug_output_file'))
            self.data_dir = os.path.join(self.base_dir, self.config_data['paths'].get('data_dir'))
            self.cached_source_file = os.path.join(self.base_dir, self.config_data['paths'].get('cached_source_file'))
            self.mapping_file = os.path.join(self.base_dir, self.config_data['paths'].get('mapping_file'))
        else:
            # 默认配置
            self.batch_size = 10
            self.llm_concurrency = 5
            self.llm_retry_times = 3
            self.llm_retry_delay = 2
            self.img_concurrency = 10
            self.img_retry_times = 2
            self.img_retry_delay = 1
            self.save_interval_batches = 5
            
            self.input_url = "https://raw.githubusercontent.com/DominikDoom/a1111-sd-webui-tagcomplete/refs/heads/main/tags/noob_characters-chants.json"
            self.output_file = os.path.join(self.base_dir, '..', 'output', 'noob_characters-chants-en-cn.json')
            self.debug_output_file = os.path.join(self.base_dir, '..', 'output', 'debug_output.json')
            self.data_dir = os.path.join(self.base_dir, '..', 'data')
            self.cached_source_file = os.path.join(self.data_dir, 'noob_characters-chants.json')
            self.mapping_file = os.path.join(self.base_dir, 'source_name_mapping.json')
    
    def _load_env_vars(self):
        """加载环境变量"""
        self.llm_api_url = os.getenv("LLM_API_URL")
        self.llm_api_key = os.getenv("LLM_API_KEY")
        self.llm_model = os.getenv("LLM_MODEL")
    
    def check_llm_config(self):
        """检查 LLM 配置完整性"""
        # 检查 URL 是否为空
        if not self.llm_api_url or not self.llm_api_url.strip():
            print("\n❌ 错误：环境变量 LLM_API_URL 未配置！")
            print("💡 提示：请设置系统环境变量，或使用 .env 文件。")
            sys.exit(1)

        # 检查 Key 是否为空
        if not self.llm_api_key or not self.llm_api_key.strip():
            print("\n❌ 错误：环境变量 LLM_API_KEY 未配置！")
            print("💡 提示：请设置系统环境变量 LLM_API_KEY。")
            sys.exit(1)
