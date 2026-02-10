import random
import time
import signal
import board

import adafruit_dotstar as dotstar

class AlexaLedPattern(object):
    def __init__(self, show=None, number=12):
        self.pixels_number = number
        self.pixels = [0] * 4 * number

        if not show or not callable(show):
            def dummy(data):
                pass
            show = dummy

        self.show = show
        self.stop = False

    def wakeup(self, direction=0, delay=0.4):
        # 依次绿色亮1颗、2颗、3颗灯，最后全白
        green = (0,255,0,255)
        white = (255,255,255,255)
        off = (0,0,0,0)
        seq = [
            [off, off, green],
            [off, green, green],
            [green, green, green],
            [white, white, white]
        ]
        for pixels in seq:
            flat = []
            for pix in pixels:
                flat += list(pix)
            self.show(flat)
            time.sleep(delay)

    def listen(self):
        pixels = [0, 0, 255, 255] * self.pixels_number
        self.show(pixels)

    def think(self):
        pixels  = [0, 0, 255, 255, 0, 0, 0, 255] * self.pixels_number

        while not self.stop:
            self.show(pixels)
            time.sleep(0.2)
            pixels = pixels[-4:] + pixels[:-4]

    def speak(self):
        step = 1
        position = 255
        while not self.stop:
            pixels  = [0, 0, position, 255 - position] * self.pixels_number
            self.show(pixels)
            time.sleep(0.01)
            if position <= 0:
                step = 1
                time.sleep(0.4)
            elif position >= 255:
                step = -1
                time.sleep(0.4)

            position += step

    def off(self):
        self.show([0] * 4 * self.pixels_number)

def dotstar_show(pixels):
    # pixels: [R, G, B, brightness] * n
    for i in range(n_dots):
        r = pixels[i*4]
        g = pixels[i*4+1]
        b = pixels[i*4+2]
        brightness = pixels[i*4+3] / 48.0  # 归一化，最大亮度为1
        dots.brightness = min(max(brightness, 0.05), 0.6)  # 防止太暗
        dots[i] = (r, g, b)

# Using a DotStar Digital LED Strip with 30 LEDs connected to digital pins
dots = dotstar.DotStar(board.D6, board.D5, 3, brightness=0.8)
pattern = AlexaLedPattern(show=dotstar_show, number=3)
# pattern.wakeup(direction=90)

# MAIN LOOP
n_dots = len(dots)

def handle_ctrl_c(signal_num, frame):
    for dot in range(n_dots):
        dots[dot] = (0, 0, 0)
    exit(0)  # 正常退出程序

# 注册信号处理函数，捕获SIGINT信号（即Ctrl+C）
signal.signal(signal.SIGINT, handle_ctrl_c)

def random_color():
    return random.randrange(0, 7) * 32

if __name__ == '__main__':
    while True:
        try:
            print("Waking up...")
            pattern.wakeup()
            time.sleep(3)
            print("think...")
            pattern.think()
            time.sleep(3)
            print("speak...")
            pattern.speak()
            time.sleep(6)
            print("off...")
            pattern.off()
            time.sleep(3)
        except KeyboardInterrupt:
            break


    pattern.off()
    time.sleep(1)

