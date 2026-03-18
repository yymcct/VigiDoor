"""
设备控制进程
负责管理所有 IO 设备
"""

import time
from typing import Dict, Any
from core.ipc import IPCClient, MessageType
from utils.logger import setup_logger
from .mode import DeviceMode, ModeManager
from .manager import DeviceManager
from .devices.output.led_strip import LEDStripDevice
from .devices.output.relay import RelayDevice
from .effects.led_effects import (
    SolidColorEffect,
    BlinkEffect,
    BreathEffect,
    RainbowEffect,
    PulseEffect
)
from .effects.relay_effects import RelayBlinkEffect

logger = setup_logger('device_controller')


class DeviceControllerProcess:
    """
    设备控制进程
    
    职责：
    1. 管理所有 IO 设备的生命周期
    2. 根据模式切换控制设备状态
    3. 响应 IPC 指令
    """
    
    def __init__(self, ctx: 'ProcessContext'):
        """
        初始化设备控制进程

        Args:
            ctx: 进程上下文（包含 ipc、shared_state、config、process_name）
        """
        self.ipc = ctx.ipc
        self.state = ctx.shared_state
        self.config = ctx.config.get_raw_dict()
        self.running = True
        
        # 初始化子模块
        self.mode_manager = ModeManager()
        self.device_manager = DeviceManager()
        
        # 注册模式切换回调
        self.mode_manager.add_callback(self._on_mode_changed)
        
        # LED 配置
        self.led_config = config['hardware']['led_strip']
        self.colors = self.led_config['colors']
        
        # LED 设备引用
        self._led_strip: LEDStripDevice = None
        
        # 警示灯继电器（GPIO 26，低电平触发）
        self._warning_light: RelayDevice = None
        
        logger.info("设备控制进程初始化完成")
    
    def run(self):
        """主循环"""
        logger.info("💡 设备控制进程启动")        
        # 初始化设备
        if not self._init_devices():
            logger.error("设备初始化失败")
            return
        
        # 设置初始模式
        self.mode_manager.set_mode(DeviceMode.SAFE)
        # 确保初始模式效果被应用
        self._apply_mode_effect(self.mode_manager.current_mode)
        
        last_heartbeat = time.time()
        
        try:
            while self.running:
                # 处理 IPC 消息
                self._process_messages()
                
                # 更新所有输出设备（驱动动画）
                self.device_manager.update_all_outputs()
                
                # 定期发送心跳
                if time.time() - last_heartbeat > 10:
                    self.ipc.send_heartbeat()
                    last_heartbeat = time.time()
                
                time.sleep(0.05)  # 20 FPS 更新频率
                
        except KeyboardInterrupt:
            logger.info("检测到中断信号")
        finally:
            self._cleanup()
            logger.info("设备控制进程退出")
    
    def _init_devices(self) -> bool:
        """
        初始化所有设备
        
        Returns:
            是否初始化成功
        """
        try:
            # 创建 LED 灯带设备
            self._led_strip = LEDStripDevice(
                pin=self.led_config['pin'],
                count=self.led_config['count'],
                brightness=self.led_config['brightness'],
                simulate=False  # TODO: 从配置读取
            )
            
            # 注册设备
            if not self.device_manager.register_device(self._led_strip):
                logger.error("LED 灯带注册失败")
                return False
            
            # 创建警示灯继电器（GPIO 26，低电平触发）
            self._warning_light = RelayDevice(
                pin=26,
                normally_open=False,  # 低电平触发：turn_on 输出 LOW
                name="警示灯",
                simulate=False
            )
            
            if not self.device_manager.register_device(self._warning_light):
                logger.error("警示灯继电器注册失败")
                return False
            
            logger.info("✅ 所有设备初始化成功")
            return True
            
        except Exception as e:
            logger.error(f"设备初始化失败: {e}")
            return False
    
    def _process_messages(self):
        """处理 IPC 消息"""
        msg = self.ipc.receive(timeout=0.01)
        if not msg:
            return
        
        try:
            msg_dict = msg.to_dict() if hasattr(msg, 'to_dict') else msg
            msg_type = msg_dict.get('type')
            
            # 处理设置灯光指令
            if msg_type in ['set_light', MessageType.CMD_SET_LIGHT.value]:
                mode_str = msg_dict.get('mode') or msg_dict.get('data', {}).get('mode')
                if mode_str:
                    self._handle_set_light(mode_str)
            
            # 处理关闭指令
            elif msg_type in ['shutdown', MessageType.SHUTDOWN.value]:
                logger.info("收到关闭信号")
                self.running = False
            
        except Exception as e:
            logger.error(f"处理消息失败: {e}")
    
    def _handle_set_light(self, mode_str: str):
        """
        处理设置灯光指令
        
        Args:
            mode_str: 模式字符串 ("safe", "alert", "alarm")
        """
        try:
            # 映射字符串到枚举
            mode_map = {
                'safe': DeviceMode.SAFE,
                'alert': DeviceMode.ALERT,
                'alarm': DeviceMode.ALARM
            }
            
            mode = mode_map.get(mode_str.lower())
            if mode:
                self.mode_manager.set_mode(mode)
            else:
                logger.warning(f"未知模式: {mode_str}")
                
        except Exception as e:
            logger.error(f"设置灯光失败: {e}")
    
    def _on_mode_changed(self, old_mode: DeviceMode, new_mode: DeviceMode):
        """
        模式切换回调
        
        Args:
            old_mode: 旧模式
            new_mode: 新模式
        """
        logger.info(f"💡 切换模式: {old_mode.value} -> {new_mode.value}")
        #self._apply_mode_effect(new_mode)

    def _apply_mode_effect(self, mode: DeviceMode):
        """根据模式应用 LED 效果（启动时也可复用）"""
        if not self._led_strip:
            return

        if mode == DeviceMode.SAFE:
            # 绿色纯色
            color = tuple(self.colors['safe'])
            effect = SolidColorEffect(color)
            self._led_strip.set_effect(effect)
            # 关闭警示灯（先停止效果）
            if self._warning_light:
                logger.info(f"🔴 SAFE 模式：关闭警示灯")
                self._warning_light.stop_effect()  # 显式停止效果
                result = self._warning_light.turn_off()
                if not result:
                    logger.error("警示灯关闭失败！")
                else:
                    logger.info(f"✅ 警示灯已关闭，当前状态: {self._warning_light.is_on()}")

        elif mode == DeviceMode.ALERT:
            # 黄色纯色
            color = tuple(self.colors['alert'])
            effect = SolidColorEffect(color)
            self._led_strip.set_effect(effect)
            # 打开警示灯
            if self._warning_light:
                logger.info(f"🟡 ALERT 模式：打开警示灯")
                self._warning_light.stop_effect()  # 先停止可能存在的闪烁效果
                result = self._warning_light.turn_on()
                if not result:
                    logger.error("警示灯打开失败！")
                else:
                    logger.info(f"✅ 警示灯已打开，当前状态: {self._warning_light.is_on()}")

        elif mode == DeviceMode.ALARM:
            # 红蓝黄暴闪
            effect = BlinkEffect(interval=0.1)
            self._led_strip.set_effect(effect)
            # 警示灯闪烁（使用 Effect 系统）
            if self._warning_light:
                logger.info(f"🔴 ALARM 模式：警示灯闪烁")
                relay_effect = RelayBlinkEffect(interval=0.5)
                self._warning_light.set_effect(relay_effect)
                logger.info(f"✅ 警示灯闪烁效果已启动")
    
    def _cleanup(self):
        """清理资源"""
        try:
            # 清理所有设备
            self.device_manager.cleanup_all()
            logger.info("所有设备已清理")
            
        except Exception as e:
            logger.error(f"清理资源失败: {e}")
