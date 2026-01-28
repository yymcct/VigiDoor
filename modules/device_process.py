"""
硬件控制进程
负责控制 WS2812B LED 灯带
"""

import time
from utils.logger import setup_logger
from core.ipc import IPCClient, MessageType
from core.ipc.registry import ProcessName

logger = setup_logger('device_controller')


class DeviceControllerProcess:
    """
    硬件控制进程 - 负责控制 WS2812B LED 灯带
    
    功能：
    1. 控制 LED 灯带显示不同状态（绿/黄/红闪烁）
    2. 响应状态切换指令
    """
    
    # 状态模式
    MODE_SAFE = "safe"      # 绿色
    MODE_ALERT = "alert"    # 黄色
    MODE_ALARM = "alarm"    # 红色闪烁
    
    def __init__(self, ipc_client: IPCClient, shared_state, config):
        self.ipc = ipc_client
        self.state = shared_state
        self.config = config
        self.running = True
        
        # LED 配置
        self.led_config = config['hardware']['led_strip']
        self.colors = self.led_config['colors']
        
        # 当前模式
        self.current_mode = self.MODE_SAFE
        
        logger.info(f"硬件控制进程初始化完成")
        logger.info(f"  LED 引脚: GPIO {self.led_config['pin']}")
        logger.info(f"  LED 数量: {self.led_config['count']}")
    
    def run(self):
        """主循环"""
        logger.info("💡 硬件控制进程启动")
        
        # 初始化 LED 灯带
        strip = self._init_led_strip()
        
        # 设置初始状态（绿色）
        self._set_mode(strip, self.MODE_SAFE)
        
        last_heartbeat = time.time()
        
        try:
            while self.running:
                # 检查状态变化
                msg = self.ipc.receive(timeout=0.1)
                if msg:
                    msg_dict = msg.to_dict() if hasattr(msg, 'to_dict') else msg
                    msg_type = msg_dict.get('type')
                    
                    if msg_type in ['set_light', MessageType.CMD_SET_LIGHT.value]:
                        mode = msg_dict.get('mode') or msg_dict.get('data', {}).get('mode')
                        if mode:
                            self._set_mode(strip, mode)
                    
                    elif msg_type in ['shutdown', MessageType.SHUTDOWN.value]:
                        logger.info("收到关闭信号")
                        break
                
                # 如果是闪烁模式，需要持续更新
                if self.current_mode == self.MODE_ALARM:
                    self._update_alarm_animation(strip)
                
                # 定期发送心跳
                if time.time() - last_heartbeat > 10:
                    self.ipc.send_heartbeat()
                    last_heartbeat = time.time()
                
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            logger.info("检测到中断信号")
        finally:
            self._cleanup(strip)
            logger.info("硬件控制进程退出")
    
    def _init_led_strip(self):
        """初始化 LED 灯带"""
        try:
            # 尝试初始化真实硬件
            # from rpi_ws281x import PixelStrip, Color
            # strip = PixelStrip(
            #     num=self.led_config['count'],
            #     pin=self.led_config['pin'],
            #     brightness=self.led_config['brightness']
            # )
            # strip.begin()
            # logger.info("✅ LED 灯带初始化成功")
            # return strip
            
            # 初版返回模拟对象
            logger.info("✅ LED 灯带初始化成功（模拟模式）")
            return {'mode': 'simulation', 'state': None}
            
        except Exception as e:
            logger.error(f"LED 灯带初始化失败: {e}")
            return None
    
    def _set_mode(self, strip, mode: str):
        """设置 LED 模式"""
        if mode == self.current_mode:
            return
        
        self.current_mode = mode
        logger.info(f"💡 切换 LED 模式: {mode}")
        
        if mode == self.MODE_SAFE:
            self._set_solid_color(strip, self.colors['safe'])
        elif mode == self.MODE_ALERT:
            self._set_solid_color(strip, self.colors['alert'])
        elif mode == self.MODE_ALARM:
            # 报警模式使用动画，在主循环中更新
            pass
    
    def _set_solid_color(self, strip, color):
        """设置纯色"""
        if not strip or strip.get('mode') == 'simulation':
            logger.info(f"  [模拟] 设置颜色: RGB{color}")
            return
        
        # 真实硬件实现
        # from rpi_ws281x import Color
        # r, g, b = color
        # for i in range(strip.numPixels()):
        #     strip.setPixelColor(i, Color(r, g, b))
        # strip.show()
    
    def _update_alarm_animation(self, strip):
        """更新报警动画（红色闪烁）"""
        if not strip or strip.get('mode') == 'simulation':
            # 模拟模式：每秒打印一次
            if int(time.time()) % 2 == 0:
                if strip.get('state') != 'on':
                    logger.info("  [模拟] 红灯亮")
                    strip['state'] = 'on'
            else:
                if strip.get('state') != 'off':
                    logger.info("  [模拟] 红灯灭")
                    strip['state'] = 'off'
            return
        
        # 真实硬件实现
        # if int(time.time() * 2) % 2 == 0:
        #     self._set_solid_color(strip, self.colors['alarm'])
        # else:
        #     self._set_solid_color(strip, [0, 0, 0])  # 关闭
    
    def _cleanup(self, strip):
        """清理资源"""
        try:
            # 关闭所有 LED
            if strip and strip.get('mode') != 'simulation':
                # self._set_solid_color(strip, [0, 0, 0])
                pass
            logger.info("LED 灯带已关闭")
        except:
            pass
