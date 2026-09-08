import json
import os

class ConfigLoader:
    """加载并管理系统配置"""
    def __init__(self, config_file="config.json"):
        # 假设配置文件位于 simulation 目录下
        self.config_path = os.path.join(os.path.dirname(__file__), "..", config_file)
        self.config = self._load_config()

    def _load_config(self):
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"无法加载配置文件: {e}")
            # 返回默认配置以防崩溃
            return {
                "server": {"ip": "127.0.0.1", "port": 4001},
                "database": {"filename": "orienteering.db"},
                "system": {"polling_interval": 0.3}
            }

    def get(self, key, default=None):
        keys = key.split('.')
        val = self.config
        for k in keys:
            if isinstance(val, dict):
                val = val.get(k)
            else:
                return default
        return val if val is not None else default
