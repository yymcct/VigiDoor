"""
摩西尔 OLED 屏幕硬件联通测试

用法:
    python tests/test_mosier_oled.py [IP] [PORT]

    IP   默认读取 config.yaml 中的 hardware.oled.ip（192.168.38.237）
    PORT 默认读取 config.yaml 中的 hardware.oled.port（8080）

示例:
    python tests/test_mosier_oled.py
    python tests/test_mosier_oled.py 192.168.1.100
    python tests/test_mosier_oled.py 192.168.1.100 8080
"""

import sys
import time

sys.path.insert(0, '/home/ubuntu/VigiDoor')

from modules.device.devices.output.mosier_oled import MosierOLEDDevice
from utils.logger import setup_logger

logger = setup_logger('test_mosier_oled')

# ─────────────────────────────────────────────
# 默认配置（从 config.yaml 读取）
# ─────────────────────────────────────────────
DEFAULT_IP = '192.168.38.237'
DEFAULT_PORT = 8080

# 测试用节目名称列表
PROGRAMS = ['daily', 'guard', 'alert', 'alarm']

# 每个节目播放后等待的秒数（方便观察屏幕效果）
PLAY_INTERVAL = 3


def get_device(ip: str, port: int) -> MosierOLEDDevice:
    return MosierOLEDDevice(ip=ip, port=port, timeout=5)


def test_connectivity(device: MosierOLEDDevice) -> bool:
    """测试设备是否可达，并列出当前节目"""
    logger.info('=' * 60)
    logger.info('【1】连通性测试')
    logger.info('=' * 60)

    ok = device.initialize()
    if not ok:
        logger.error('❌ 设备初始化失败，请检查 IP/端口及网络连接')
        return False

    logger.info('✅ 设备初始化成功')

    try:
        programs = device.get_all_programs()
        logger.info(f'当前设备节目列表（共 {len(programs)} 个）:')
        for p in programs:
            logger.info(f'  id={p.id}  name={p.name}  size={p.width}x{p.height}')
    except Exception as e:
        logger.warning(f'获取节目列表时出错: {e}')

    return True


def test_play_by_name(device: MosierOLEDDevice) -> None:
    """依次按名称播放各节目"""
    logger.info('')
    logger.info('=' * 60)
    logger.info('【2】按节目名播放测试')
    logger.info('=' * 60)

    for name in PROGRAMS:
        logger.info(f'▶ 播放节目: {name}')
        result = device.play_by_name(name)
        if result:
            logger.info(f'  ✅ 播放成功: {name}')
        else:
            logger.warning(f'  ⚠ 播放失败（节目不存在或请求错误）: {name}')

        logger.info(f'  等待 {PLAY_INTERVAL}s ...')
        time.sleep(PLAY_INTERVAL)


def test_stop(device: MosierOLEDDevice) -> None:
    """停止播放"""
    logger.info('')
    logger.info('=' * 60)
    logger.info('【3】停止播放测试')
    logger.info('=' * 60)

    result = device.stop()
    if result:
        logger.info('✅ 停止播放成功')
    else:
        logger.warning('⚠ 停止播放失败')


def main() -> None:
    # 解析命令行参数
    ip = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_IP
    port = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_PORT

    logger.info(f'目标设备: http://{ip}:{port}')

    device = get_device(ip, port)

    # 1. 连通性
    if not test_connectivity(device):
        sys.exit(1)

    # 2. 按名称播放
    test_play_by_name(device)

    # 3. 停止
    test_stop(device)

    logger.info('')
    logger.info('所有测试完成')


if __name__ == '__main__':
    main()
