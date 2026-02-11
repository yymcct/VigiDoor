"""
测试继电器在 SAFE 模式下是否正确停止
用于验证竞态条件修复
"""

import time
import sys
sys.path.insert(0, '/home/ubuntu/VigiDoor')

from modules.device.devices.output.relay import RelayDevice
from modules.device.effects.relay_effects import RelayBlinkEffect
from utils.logger import setup_logger

logger = setup_logger('test_relay')


def test_relay_stop_in_safe_mode():
    """
    测试场景：
    1. 启动继电器闪烁效果（模拟 ALARM 模式）
    2. 快速切换到 SAFE 模式（停止效果并关闭继电器）
    3. 验证继电器是否正确停止
    """
    logger.info("=" * 60)
    logger.info("测试：继电器在 SAFE 模式下停止")
    logger.info("=" * 60)
    
    # 创建继电器（模拟模式，避免影响真实硬件）
    relay = RelayDevice(
        pin=26,
        normally_open=False,
        name="测试警示灯",
        simulate=True
    )
    
    # 初始化
    if not relay.initialize():
        logger.error("继电器初始化失败")
        return False
    
    try:
        # 场景 1：启动闪烁效果（ALARM 模式）
        logger.info("\n【场景 1】启动 ALARM 模式闪烁效果")
        blink_effect = RelayBlinkEffect(interval=0.2)
        relay.set_effect(blink_effect)
        
        # 模拟更新循环（2 秒）
        logger.info("模拟闪烁 2 秒...")
        start_time = time.time()
        blink_count = 0
        last_state = False
        
        while time.time() - start_time < 2.0:
            relay.update()
            current_state = relay.is_on()
            if current_state != last_state:
                blink_count += 1
                last_state = current_state
            time.sleep(0.05)
        
        logger.info(f"✅ 闪烁次数: {blink_count}")
        
        # 场景 2：切换到 SAFE 模式（关闭继电器）
        logger.info("\n【场景 2】切换到 SAFE 模式")
        logger.info("调用 turn_off()...")
        relay.turn_off()
        
        # 验证状态
        logger.info(f"继电器状态: {relay.is_on()}")
        logger.info(f"效果是否存在: {relay._current_effect is not None}")
        
        if relay.is_on():
            logger.error("❌ 失败：继电器应该关闭但仍在开启状态")
            return False
        
        if relay._current_effect is not None:
            logger.error("❌ 失败：效果应该被清空但仍然存在")
            return False
        
        logger.info("✅ 继电器已正确关闭，效果已清空")
        
        # 场景 3：继续调用 update()，验证不会重新开启
        logger.info("\n【场景 3】验证后续 update() 不会重新开启继电器")
        logger.info("继续调用 update() 1 秒...")
        
        start_time = time.time()
        unexpected_change = False
        
        while time.time() - start_time < 1.0:
            relay.update()
            if relay.is_on():
                logger.error("❌ 失败：继电器在 SAFE 模式下被 update() 重新开启")
                unexpected_change = True
                break
            time.sleep(0.05)
        
        if not unexpected_change:
            logger.info("✅ 继电器保持关闭状态")
        else:
            return False
        
        # 场景 4：多次快速切换模式
        logger.info("\n【场景 4】快速切换 ALARM -> SAFE 多次")
        
        for i in range(5):
            logger.info(f"\n  第 {i+1} 次切换:")
            
            # 启动 ALARM
            logger.info("    -> ALARM 模式")
            relay.set_effect(RelayBlinkEffect(interval=0.1))
            
            # 短暂运行
            for _ in range(3):
                relay.update()
                time.sleep(0.05)
            
            # 切换到 SAFE
            logger.info("    -> SAFE 模式")
            relay.turn_off()
            
            # 验证
            if relay.is_on():
                logger.error(f"    ❌ 第 {i+1} 次切换失败：继电器未关闭")
                return False
            
            if relay._current_effect is not None:
                logger.error(f"    ❌ 第 {i+1} 次切换失败：效果未清空")
                return False
            
            logger.info(f"    ✅ 第 {i+1} 次切换成功")
            
            # 验证后续更新不会重新开启
            for _ in range(5):
                relay.update()
                time.sleep(0.05)
                if relay.is_on():
                    logger.error(f"    ❌ 第 {i+1} 次：update() 重新开启了继电器")
                    return False
        
        logger.info("\n✅ 所有快速切换测试通过")
        
        logger.info("\n" + "=" * 60)
        logger.info("🎉 测试通过：继电器在 SAFE 模式下正确停止")
        logger.info("=" * 60)
        return True
        
    finally:
        # 清理
        relay.cleanup()


def test_relay_effect_lifecycle():
    """测试效果的生命周期管理"""
    logger.info("\n" + "=" * 60)
    logger.info("测试：效果生命周期管理")
    logger.info("=" * 60)
    
    relay = RelayDevice(pin=26, name="测试继电器", simulate=True)
    
    if not relay.initialize():
        return False
    
    try:
        # 测试 1：set_effect 应该停止旧效果
        logger.info("\n【测试 1】set_effect 停止旧效果")
        effect1 = RelayBlinkEffect(interval=0.2)
        relay.set_effect(effect1)
        logger.info(f"效果 1 运行中: {effect1.is_running()}")
        
        effect2 = RelayBlinkEffect(interval=0.5)
        relay.set_effect(effect2)
        logger.info(f"效果 1 运行中: {effect1.is_running()}")
        logger.info(f"效果 2 运行中: {effect2.is_running()}")
        
        if effect1.is_running():
            logger.error("❌ 失败：旧效果应该被停止")
            return False
        
        logger.info("✅ 旧效果已正确停止")
        
        # 测试 2：turn_off 应该停止效果
        logger.info("\n【测试 2】turn_off 停止效果")
        relay.turn_off()
        logger.info(f"效果 2 运行中: {effect2.is_running()}")
        
        if effect2.is_running():
            logger.error("❌ 失败：turn_off 应该停止效果")
            return False
        
        logger.info("✅ turn_off 正确停止效果")
        
        # 测试 3：stop_effect 应该停止效果并关闭继电器
        logger.info("\n【测试 3】stop_effect 功能")
        effect3 = RelayBlinkEffect(interval=0.1)
        relay.set_effect(effect3)
        
        # 运行几帧
        for _ in range(5):
            relay.update()
            time.sleep(0.05)
        
        relay.stop_effect()
        
        if effect3.is_running():
            logger.error("❌ 失败：stop_effect 应该停止效果")
            return False
        
        if relay.is_on():
            logger.error("❌ 失败：stop_effect 应该关闭继电器")
            return False
        
        logger.info("✅ stop_effect 正确工作")
        
        logger.info("\n🎉 效果生命周期测试通过")
        return True
        
    finally:
        relay.cleanup()


if __name__ == '__main__':
    print("\n" + "🔧 开始测试继电器 SAFE 模式修复" + "\n")
    
    success = True
    
    # 运行测试
    if not test_relay_stop_in_safe_mode():
        success = False
    
    if not test_relay_effect_lifecycle():
        success = False
    
    print("\n" + "=" * 60)
    if success:
        print("✅ 所有测试通过")
    else:
        print("❌ 部分测试失败")
    print("=" * 60 + "\n")
    
    sys.exit(0 if success else 1)
