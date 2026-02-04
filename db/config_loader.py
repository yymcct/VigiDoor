"""
配置加载器 - 合并 YAML 和 SQLite 配置

实现配置分层策略：
- L1: YAML 文件（静态配置，系统默认值）
- L2: SQLite 数据库（动态配置，运行时可更新）
- 优先级: DB > YAML

使用场景：
1. 系统启动时，Supervisor 加载合并后的配置
2. 运行时，云端可通过 MQTT 更新配置到 DB
3. 重启后，DB 中的配置自动生效
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

#TODO 和utils/config_loader.py合并
class ConfigLoader:
    """
    配置加载器 - 合并多个配置源
    
    配置优先级（从高到低）：
    1. SQLite 数据库（动态配置）
    2. YAML 文件（静态配置）
    """
    
    def __init__(self, yaml_config: Dict[str, Any], db_path: Optional[Path] = None):
        """
        初始化配置加载器
        
        Args:
            yaml_config: 已加载的 YAML 配置字典
            db_path: 数据库目录路径（默认为 ./data）
        """
        self.yaml_config = yaml_config
        self.db_path = db_path or Path("./data")
    
    def load_merged_config(self) -> Dict[str, Any]:
        """
        加载并合并配置
        
        Returns:
            合并后的配置字典
        """
        logger.info("开始加载配置...")
        
        # 1. 复制 YAML 配置作为基础
        merged = self._deep_copy(self.yaml_config)
        
        # 2. 从数据库加载动态配置
        db_configs = self._load_db_configs()
        
        # 3. 合并配置（DB 优先级更高）
        merged = self._merge_configs(merged, db_configs)
        
        logger.info(f"配置加载完成，共 {len(db_configs)} 项来自数据库")
        return merged
    
    def _load_db_configs(self) -> Dict[str, str]:
        """
        从数据库加载动态配置
        
        Returns:
            配置字典 {key: value}
        """
        try:
            from db import DBReader
            
            # 检查数据库是否存在
            config_db = self.db_path / "config.db"
            if not config_db.exists():
                logger.info("配置数据库不存在，跳过 DB 配置加载")
                return {}
            
            # 读取所有配置
            reader = DBReader()
            configs = reader.get_all_configs()
            reader.close()
            
            logger.info(f"从数据库加载了 {len(configs)} 项配置")
            return configs
        except Exception as e:
            logger.warning(f"加载数据库配置失败，将使用 YAML 默认值: {e}")
            return {}
    
    def _merge_configs(self, base: Dict[str, Any], db_configs: Dict[str, str]) -> Dict[str, Any]:
        """
        将数据库配置合并到基础配置
        
        Args:
            base: 基础配置（YAML）
            db_configs: 数据库配置 (点号分隔的键)
            
        Returns:
            合并后的配置
        """
        for key, value in db_configs.items():
            # 将点号分隔的键转换为嵌套字典路径
            # 例如: "audio.volume_threshold_db" -> ["audio", "volume_threshold_db"]
            keys = key.split(".")
            
            # 类型转换
            typed_value = self._convert_value_type(value, base, keys)
            
            # 设置到嵌套字典
            self._set_nested_value(base, keys, typed_value)
            
            logger.debug(f"配置覆盖: {key} = {typed_value} (来自DB)")
        
        return base
    
    def _set_nested_value(self, config: Dict[str, Any], keys: list, value: Any) -> None:
        """
        设置嵌套字典的值
        
        Args:
            config: 配置字典
            keys: 键路径列表
            value: 要设置的值
        """
        current = config
        
        # 遍历到倒数第二层
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            elif not isinstance(current[key], dict):
                # 如果中间节点不是字典，创建新字典
                current[key] = {}
            current = current[key]
        
        # 设置最后一层的值
        current[keys[-1]] = value
    
    def _convert_value_type(
        self,
        value: str,
        base_config: Dict[str, Any],
        keys: list
    ) -> Any:
        """
        根据 YAML 中的原始类型，转换数据库字符串值
        
        Args:
            value: 数据库中的字符串值
            base_config: 基础配置（用于推断类型）
            keys: 键路径
            
        Returns:
            转换后的值
        """
        # 尝试从 YAML 获取原始类型
        try:
            current = base_config
            for key in keys[:-1]:
                current = current.get(key, {})
            
            original_value = current.get(keys[-1])
            
            if original_value is not None:
                # 根据原始类型转换
                if isinstance(original_value, bool):
                    return value.lower() in ("true", "1", "yes")
                elif isinstance(original_value, int):
                    return int(value)
                elif isinstance(original_value, float):
                    return float(value)
        except Exception as e:
            logger.debug(f"类型推断失败，使用字符串: {e}")
        
        # 默认返回字符串
        return value
    
    def _deep_copy(self, obj: Any) -> Any:
        """深拷贝对象"""
        import copy
        return copy.deepcopy(obj)


def load_config_with_db(yaml_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    便捷函数：加载合并 YAML 和 DB 配置
    
    Args:
        yaml_config: 已加载的 YAML 配置
        
    Returns:
        合并后的配置
    """
    loader = ConfigLoader(yaml_config)
    return loader.load_merged_config()


if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 模拟 YAML 配置
    yaml_config = {
        "audio": {
            "volume_threshold_db": 50.0,
            "sample_rate": 16000
        },
        "detector": {
            "confidence": 0.5
        }
    }
    
    print("=== 原始 YAML 配置 ===")
    print(yaml_config)
    
    # 加载合并配置
    loader = ConfigLoader(yaml_config)
    merged = loader.load_merged_config()
    
    print("\n=== 合并后配置 ===")
    print(merged)
    
    print("\n测试完成")
