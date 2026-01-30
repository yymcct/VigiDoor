import time

import board
import neopixel_spi as neopixel


LED_COUNT = 30
BRIGHTNESS = 0.2


def wheel(pos: int) -> tuple[int, int, int]:
	if pos < 0 or pos > 255:
		return 0, 0, 0
	if pos < 85:
		return 255 - pos * 3, pos * 3, 0
	if pos < 170:
		pos -= 85
		return 0, 255 - pos * 3, pos * 3
	pos -= 170
	return pos * 3, 0, 255 - pos * 3


def color_wipe(pixels, color, wait=0.02):
	for i in range(pixels.n):
		pixels[i] = color
		pixels.show()
		time.sleep(wait)


def blink(pixels, color, times=3, wait=0.3):
	for _ in range(times):
		pixels.fill(color)
		pixels.show()
		time.sleep(wait)
		pixels.fill((0, 0, 0))
		pixels.show()
		time.sleep(wait)


def strobe(pixels, color, flashes=10, on=0.03, off=0.03):
	for _ in range(flashes):
		pixels.fill(color)
		pixels.show()
		time.sleep(on)
		pixels.fill((0, 0, 0))
		pixels.show()
		time.sleep(off)


def rainbow_cycle(pixels, wait=0.01, cycles=1):
	for j in range(255 * cycles):
		for i in range(pixels.n):
			pixel_index = (i * 256 // pixels.n) + j
			pixels[i] = wheel(pixel_index & 255)
		pixels.show()
		time.sleep(wait)


def main():
	# 在 Pi 5 上使用 SPI 驱动
	# 这里的 board.SPI() 会自动寻找 MOSI (GPIO 10)
	spi = board.SPI()
	pixels = neopixel.NeoPixel_SPI(
		spi,
		LED_COUNT,
		brightness=BRIGHTNESS,
		pixel_order=neopixel.GRB,
		auto_write=False,
	)

	try:
		while True:
			color_wipe(pixels, (255, 0, 0))
			color_wipe(pixels, (0, 255, 0))
			color_wipe(pixels, (0, 0, 255))
			blink(pixels, (255, 255, 255), times=2)
			strobe(pixels, (255, 255, 255), flashes=12, on=0.02, off=0.02)
			strobe(pixels, (255, 0, 0), flashes=12, on=0.02, off=0.02)
			strobe(pixels, (0, 0, 255), flashes=12, on=0.02, off=0.02)
			rainbow_cycle(pixels, wait=0.01, cycles=2)
	except KeyboardInterrupt:
		pass
	finally:
		pixels.fill((0, 0, 0))
		pixels.show()


if __name__ == "__main__":
	main()