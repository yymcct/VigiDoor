"""
摄像头传感器型号检测工具
提供统一的传感器识别接口，供各驱动及上层模块复用
"""

from utils.logger import setup_logger

logger = setup_logger('sensor_detect')

# 已知传感器型号标识（与 camera_properties["Model"] 子串匹配，大小写不敏感）
SENSOR_OV5647 = "ov5647"   # Camera Module V1，500 万像素
SENSOR_IMX708 = "imx708"   # Camera Module V3，1200 万像素
SENSOR_UNKNOWN = ""


def detect_sensor_model(camera) -> str:
    """
    通过 Picamera2 实例的 camera_properties 检测传感器型号。

    Args:
        camera: 已实例化的 Picamera2 对象（无需 start）

    Returns:
        传感器型号的小写字符串（如 "ov5647"、"imx708"）；
        无法识别时返回空字符串。
    """
    try:
        props = camera.camera_properties
        model: str = props.get("Model", "").lower()
        if model:
            logger.debug(f"检测到传感器型号: '{model}'")
        else:
            logger.warning("camera_properties 中未包含 Model 字段")
        return model
    except Exception as e:
        logger.error(f"读取传感器型号失败: {e}")
        return SENSOR_UNKNOWN


def is_imx708(camera) -> bool:
    """判断当前摄像头是否为 IMX708 传感器"""
    return SENSOR_IMX708 in detect_sensor_model(camera)


def is_ov5647(camera) -> bool:
    """判断当前摄像头是否为 OV5647 传感器"""
    return SENSOR_OV5647 in detect_sensor_model(camera)
