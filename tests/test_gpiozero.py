from gpiozero import DigitalOutputDevice
from time import sleep

led = DigitalOutputDevice(20)       # 26 20 21


led.on()            # 点亮
sleep(1)
led.off()           # 熄灭

# 按钮按下就点亮 LED，按住就保持亮，松开就灭
while True:
    led.on()
    sleep(0.2)
    led.off()
    sleep(0.2)
    