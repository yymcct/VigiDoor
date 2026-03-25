"""
WS2812B LED 灯带设备实现
"""

from pathlib import Path
from typing import Tuple, Optional, Dict, Any
from ..base import OutputDevice
from ...effects.base import EffectBase
from utils.logger import setup_logger

logger = setup_logger('led_strip')


DEFAULT_SPI_FREQUENCY = 6_400_000
SPI_BUFFER_PATH = Path("/sys/module/spidev/parameters/bufsiz")
SPI_BYTES_PER_LED = 3 * 8
MAX_HARDWARE_BRIGHTNESS = 0.99


class LEDStripDevice(OutputDevice):
    """
    WS2812B LED 灯带设备
    
    支持硬件模式和模拟模式
    """
    
    def __init__(
        self,
        pin: int,
        count: int,
        brightness: int | float = 255,
        simulate: bool = False,
        spi_frequency: int = DEFAULT_SPI_FREQUENCY,
    ):
        """
        初始化 LED 灯带
        
        Args:
            pin: GPIO 引脚号
            count: LED 数量
            brightness: 亮度 (0-255 或 0.0-1.0)
            simulate: 是否使用模拟模式
            spi_frequency: SPI 回退模式频率
        """
        super().__init__(
            device_id=f"led_strip_{pin}",
            device_type="led_strip",
            name=f"WS2812B LED Strip (GPIO{pin})"
        )
        
        self.pin = pin
        self.count = count
        self.brightness = brightness
        self.simulate = simulate
        self.spi_frequency = spi_frequency
        
        self._pixels = None
        self._current_effect: Optional[EffectBase] = None
        self._current_color = (0, 0, 0)
        self._sim_state = None  # 模拟模式状态
        self._backend = 'simulation' if simulate else None
    
    def initialize(self) -> bool:
        """
        初始化 LED 灯带
        
        Returns:
            是否初始化成功
        """
        try:
            if self.simulate:
                self._enable_simulation_mode()
                self._log_initialization_success()
                return True

            try:
                import board
            except ImportError:
                logger.warning("board 库未安装，切换到模拟模式")
                self._enable_simulation_mode()
                self._log_initialization_success()
                return True

            brightness = self._normalize_brightness(self.brightness)

            native_error = None
            try:
                self._pixels = self._create_native_pixels(board, brightness)
                self._backend = 'native'
                self._initialized = True
                self._log_initialization_success()
                return True
            except ImportError as exc:
                native_error = exc
                logger.warning(f"原生 NeoPixel 后端不可用，回退 SPI: {exc}")
            except Exception as exc:
                native_error = exc
                logger.warning(f"原生 NeoPixel 后端初始化失败，回退 SPI: {exc}")

            try:
                self._pixels = self._create_spi_pixels(board, brightness)
                self._backend = 'spi'
                self._initialized = True
                self._warn_if_spi_buffer_is_too_small()
                self._log_initialization_success(previous_error=native_error)
                return True
            except ImportError:
                logger.warning("neopixel/neopixel_spi 库未安装，切换到模拟模式")
                self._enable_simulation_mode()
                self._log_initialization_success(previous_error=native_error)
                return True
            except Exception as e:
                logger.error(f"LED 灯带硬件初始化失败: {e}")
                self._initialized = False
                self._pixels = None
                return False
                
        except Exception as e:
            logger.error(f"LED 灯带初始化失败: {e}")
            self._initialized = False
            return False
    
    def cleanup(self):
        """清理资源，关闭所有 LED"""
        try:
            if self._current_effect:
                self._current_effect.stop()
            
            # 关闭所有 LED
            self.write((0, 0, 0))
            
            if self._pixels:
                self._pixels.fill((0, 0, 0))
                self._pixels.show()
                if hasattr(self._pixels, 'deinit'):
                    self._pixels.deinit()
                self._pixels = None
            
            logger.info("LED 灯带已关闭")
            
        except Exception as e:
            logger.error(f"LED 灯带清理失败: {e}")
    
    def write(self, data: Tuple[int, int, int]) -> bool:
        """
        设置纯色
        
        Args:
            data: RGB 颜色值 (0-255, 0-255, 0-255)
            
        Returns:
            是否设置成功
        """
        if not self._initialized:
            logger.warning("LED 灯带未初始化，忽略写入")
            return False
        
        try:
            color = self._sanitize_color(data)
            self._current_color = color
            
            # 停止当前效果
            if self._current_effect and self._current_effect.is_running():
                self._current_effect.stop()
                self._current_effect = None
            
            if self.simulate:
                # 模拟模式
                logger.info(f"  [模拟] 设置颜色: RGB{color}")
                return True
            
            # 真实硬件
            if self._pixels:
                self._pixels.fill(color)
                self._pixels.show()
                return True
            
            logger.warning("硬件像素对象未就绪，写入失败")
            return False
            
        except Exception as e:
            logger.error(f"设置 LED 颜色失败: {e}")
            return False
    
    def update(self):
        """
        更新效果动画（需要在主循环中定期调用）
        
        如果有活跃的效果，更新并应用到硬件
        """
        if not self._initialized or not self._current_effect:
            return
        
        try:
            if self._current_effect.is_running():
                result = self._current_effect.update()
                if result is None:
                    return
                if isinstance(result, list):
                    self._apply_pixels(result)
                else:
                    self._apply_color(result)
            
        except Exception as e:
            logger.error(f"更新 LED 效果失败: {e}")
    
    def set_effect(self, effect: EffectBase):
        """
        设置动画效果
        
        Args:
            effect: 效果对象
        """
        # 停止当前效果
        if self._current_effect and self._current_effect.is_running():
            self._current_effect.stop()
        
        # 启动新效果
        self._current_effect = effect
        self._current_effect.start()
    
    def stop_effect(self):
        """停止当前效果"""
        if self._current_effect:
            self._current_effect.stop()
            self._current_effect = None
    
    def _apply_color(self, color: Tuple[int, int, int]):
        """
        内部方法：直接应用颜色到硬件（不影响效果状态）
        
        Args:
            color: RGB 颜色值
        """
        color = self._sanitize_color(color)

        if self.simulate:
            # 模拟模式：根据颜色判断状态
            if color == (0, 0, 0):
                if self._sim_state != 'off':
                    logger.debug("  [模拟] 灯灭")
                    self._sim_state = 'off'
            else:
                if self._sim_state != color:
                    logger.debug(f"  [模拟] 灯亮: RGB{color}")
                    self._sim_state = color
            return
        
        # 真实硬件
        if self._pixels:
            self._pixels.fill(color)
            self._pixels.show()
            self._current_color = color
        else:
            logger.warning("硬件像素对象未就绪，无法应用颜色")

    def _apply_pixels(self, colors: list):
        """内部方法：将逐像素颜色列表写入硬件"""
        if self.simulate:
            return
        if self._pixels:
            self._pixels[:] = colors
            self._pixels.show()
        else:
            logger.warning("硬件像素对象未就绪，无法应用逐像素颜色")

    def _enable_simulation_mode(self) -> None:
        self.simulate = True
        self._backend = 'simulation'
        self._sim_state = 'off'
        self._pixels = None
        self._initialized = True

    def _create_native_pixels(self, board_module, brightness: float):
        import neopixel

        pixel_pin = getattr(board_module, f"D{self.pin}", None)
        if pixel_pin is None:
            raise ValueError(f"board 模块未提供 GPIO{self.pin} 对应的 D{self.pin} 引脚")

        return neopixel.NeoPixel(
            pixel_pin,
            self.count,
            brightness=brightness,
            pixel_order=neopixel.GRB,
            auto_write=False,
        )

    def _create_spi_pixels(self, board_module, brightness: float):
        import neopixel_spi

        spi = board_module.SPI()
        return neopixel_spi.NeoPixel_SPI(
            spi,
            self.count,
            brightness=brightness,
            pixel_order=neopixel_spi.GRB,
            auto_write=False,
            frequency=self.spi_frequency,
        )

    def _normalize_brightness(self, brightness: int | float) -> float:
        if not isinstance(brightness, (int, float)):
            return MAX_HARDWARE_BRIGHTNESS

        normalized = float(brightness)
        if normalized > 1.0:
            normalized = normalized / 255.0

        return max(0.0, min(normalized, MAX_HARDWARE_BRIGHTNESS))

    def _sanitize_color(self, color: Tuple[int, int, int]) -> Tuple[int, int, int]:
        if len(color) != 3:
            raise ValueError("LED 颜色必须是 3 通道 RGB 元组")

        return tuple(max(0, min(int(channel), 255)) for channel in color)

    def _read_spi_buffer_size(self) -> Optional[int]:
        try:
            return int(SPI_BUFFER_PATH.read_text(encoding='utf-8').strip())
        except (OSError, ValueError):
            return None

    def _warn_if_spi_buffer_is_too_small(self) -> None:
        if self._backend != 'spi':
            return

        bufsize = self._read_spi_buffer_size()
        if bufsize is None:
            logger.warning("无法读取 spidev buffer size，SPI 模式下流畅度可能受限")
            return

        frame_bytes = self.count * SPI_BYTES_PER_LED
        if frame_bytes > bufsize:
            logger.warning(
                "SPI buffer 偏小，当前帧大小 %s bytes 超过 spidev.bufsiz=%s；"
                "建议在 /boot/firmware/cmdline.txt 中设置 spidev.bufsiz=32768",
                frame_bytes,
                bufsize,
            )

    def _log_initialization_success(self, previous_error: Optional[Exception] = None) -> None:
        logger.info("LED 灯带初始化成功")
        logger.info(f"  引脚: GPIO {self.pin}")
        logger.info(f"  数量: {self.count}")
        logger.info(f"  亮度: {self._normalize_brightness(self.brightness):.3f}")
        logger.info(f"  模式: {self._backend}")
        if previous_error is not None:
            logger.debug(f"  回退原因: {previous_error}")
    
    def get_info(self) -> Dict[str, Any]:
        """
        获取设备信息
        
        Returns:
            设备信息字典
        """
        info = super().get_info()
        info.update({
            'pin': self.pin,
            'count': self.count,
            'brightness': self.brightness,
            'simulate': self.simulate,
            'backend': self._backend,
            'spi_frequency': self.spi_frequency,
            'current_color': self._current_color,
            'current_effect': self._current_effect.name if self._current_effect else None
        })
        return info
