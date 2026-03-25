import argparse
import math
import time
from pathlib import Path

import board
import neopixel
import neopixel_spi


LED_PIN = board.D10
LED_COUNT = 291
MASTER_BRIGHTNESS = 0.99
TARGET_FPS = 60
SPI_FREQUENCY = 6_400_000
SPI_BUFFER_PATH = Path("/sys/module/spidev/parameters/bufsiz")
SPI_FRAME_BYTES = LED_COUNT * 3 * 8
BLACK = (0, 0, 0)


class FrameClock:
	def __init__(self, fps: int) -> None:
		self._frame_interval = 1.0 / fps
		self._next_tick = time.perf_counter()

	def wait_frames(self, frames: int = 1) -> None:
		self._next_tick += self._frame_interval * frames
		delay = self._next_tick - time.perf_counter()
		if delay > 0:
			time.sleep(delay)
		else:
			self._next_tick = time.perf_counter()


def ease_in_out(value: float) -> float:
	return value * value * (3.0 - 2.0 * value)


def scale_color(color: tuple[int, int, int], level: float = 1.0) -> tuple[int, int, int]:
	intensity = max(0.0, min(1.0, MASTER_BRIGHTNESS * level))
	return tuple(int(channel * intensity + 0.5) for channel in color)


def blend_color(
	start: tuple[int, int, int],
	end: tuple[int, int, int],
	amount: float,
) -> tuple[int, int, int]:
	ratio = max(0.0, min(1.0, amount))
	return tuple(
		int(start[index] + (end[index] - start[index]) * ratio + 0.5)
		for index in range(3)
	)


def add_color(base: tuple[int, int, int], extra: tuple[int, int, int]) -> tuple[int, int, int]:
	return tuple(min(255, base[index] + extra[index]) for index in range(3))


def wheel(pos: int) -> tuple[int, int, int]:
	if pos < 0 or pos > 255:
		return BLACK
	if pos < 85:
		return 255 - pos * 3, pos * 3, 0
	if pos < 170:
		pos -= 85
		return 0, 255 - pos * 3, pos * 3
	pos -= 170
	return pos * 3, 0, 255 - pos * 3


WHEEL_LUT = tuple(wheel(i) for i in range(256))


def read_spi_buffer_size() -> int | None:
	try:
		return int(SPI_BUFFER_PATH.read_text(encoding="utf-8").strip())
	except (OSError, ValueError):
		return None


def create_pixels():
	try:
		pixels = neopixel.NeoPixel(
			LED_PIN,
			LED_COUNT,
			brightness=1.0,
			pixel_order=neopixel.GRB,
			auto_write=False,
		)
		print(f"Using native Pi 5 NeoPixel backend on {LED_PIN}.")
		return pixels, "native"
	except Exception as exc:
		print(f"Native NeoPixel backend unavailable, falling back to SPI: {exc}")
		spi = board.SPI()
		pixels = neopixel_spi.NeoPixel_SPI(
			spi,
			LED_COUNT,
			brightness=1.0,
			pixel_order=neopixel_spi.GRB,
			auto_write=False,
			frequency=SPI_FREQUENCY,
		)
		return pixels, "spi"


def warn_if_spi_buffer_is_too_small(backend: str) -> None:
	if backend != "spi":
		return

	bufsize = read_spi_buffer_size()
	if bufsize is None:
		print("Could not read spidev buffer size; smoothness may still be limited on SPI.")
		return

	if SPI_FRAME_BYTES > bufsize:
		print(
			"SPI buffer is too small for this strip: "
			f"frame={SPI_FRAME_BYTES} bytes, spidev.bufsiz={bufsize}. "
			"Set spidev.bufsiz=32768 in /boot/firmware/cmdline.txt for stable output."
		)


def color_wipe(pixels, color: tuple[int, int, int], clock: FrameClock, chunk_size: int = 6) -> None:
	scaled = scale_color(color)
	for start in range(0, pixels.n, chunk_size):
		stop = min(start + chunk_size, pixels.n)
		pixels[start:stop] = [scaled] * (stop - start)
		pixels.show()
		clock.wait_frames()


def blink(
	pixels,
	color: tuple[int, int, int],
	clock: FrameClock,
	times: int = 3,
	fade_frames: int = 8,
	hold_frames: int = 4,
) -> None:
	for _ in range(times):
		for frame in range(1, fade_frames + 1):
			pixels.fill(scale_color(color, ease_in_out(frame / fade_frames)))
			pixels.show()
			clock.wait_frames()
		pixels.fill(scale_color(color))
		pixels.show()
		clock.wait_frames(hold_frames)
		for frame in range(fade_frames - 1, -1, -1):
			pixels.fill(scale_color(color, ease_in_out(frame / fade_frames)))
			pixels.show()
			clock.wait_frames()


def strobe(
	pixels,
	color: tuple[int, int, int],
	clock: FrameClock,
	flashes: int = 10,
	on_frames: int = 1,
	off_frames: int = 1,
) -> None:
	scaled = scale_color(color)
	for _ in range(flashes):
		pixels.fill(scaled)
		pixels.show()
		clock.wait_frames(on_frames)
		pixels.fill(BLACK)
		pixels.show()
		clock.wait_frames(off_frames)


def rainbow_cycle(pixels, clock: FrameClock, cycles: int = 1) -> None:
	for offset in range(256 * cycles):
		frame = [
			scale_color(WHEEL_LUT[((index * 256 // pixels.n) + offset) & 255])
			for index in range(pixels.n)
		]
		pixels[:] = frame
		pixels.show()
		clock.wait_frames()


def business_hours_effect(pixels, clock: FrameClock, duration: float) -> None:
	# Aurora palette: cyan -> blue-violet -> violet -> amber-gold -> teal -> cyan
	_PALETTE = [
		(0, 210, 255),
		(80, 60, 255),
		(180, 0, 255),
		(255, 160, 0),
		(0, 255, 160),
		(0, 210, 255),
	]
	_STOPS = len(_PALETTE) - 1

	def sample_palette(t: float) -> tuple[int, int, int]:
		t = t % 1.0
		pos = t * _STOPS
		idx = int(pos)
		frac = pos - idx
		return blend_color(_PALETTE[idx], _PALETTE[min(idx + 1, _STOPS)], frac)

	frames = max(1, int(duration * TARGET_FPS))
	n = pixels.n
	sparkle = [0.0] * n

	for frame in range(frames):
		if frame % 5 == 0:
			spark_idx = (frame * 73 + (frame // 5) * 137) % n
			sparkle[spark_idx] = 1.0
		sparkle = [max(0.0, s - 0.07) for s in sparkle]

		breath = 0.55 + 0.45 * math.sin(frame * 0.020)
		comet_a = (frame * 2.3) % n
		comet_b = (frame * 1.1 + n * 0.55) % n

		frame_buffer = []
		for index in range(n):
			palette_t = (index / n + frame * 0.0015) % 1.0
			color = sample_palette(palette_t)

			wave = 0.5 + 0.5 * math.sin(index * 0.06 - frame * 0.04)
			level = 0.08 + 0.18 * breath * wave

			dist_a = min(abs(index - comet_a), n - abs(index - comet_a))
			glow_a = ease_in_out(max(0.0, 1.0 - dist_a / 18.0))
			color = blend_color(color, (220, 255, 255), glow_a * 0.75)
			level += 0.45 * glow_a

			dist_b = min(abs(index - comet_b), n - abs(index - comet_b))
			glow_b = ease_in_out(max(0.0, 1.0 - dist_b / 30.0))
			color = blend_color(color, (255, 200, 60), glow_b * 0.65)
			level += 0.36 * glow_b

			if sparkle[index] > 0.0:
				s = ease_in_out(sparkle[index])
				color = blend_color(color, (255, 255, 255), s * 0.9)
				level += 0.40 * s

			frame_buffer.append(scale_color(color, min(0.94, level)))

		pixels[:] = frame_buffer
		pixels.show()
		clock.wait_frames()


def guard_idle_effect(pixels, clock: FrameClock, duration: float) -> None:
	frames = max(1, int(duration * TARGET_FPS))
	max_position = max(1, pixels.n - 1)
	for frame in range(frames):
		breathe = 0.5 + 0.5 * math.sin(frame * 0.05)
		patrol_phase = (frame * 1.3) % (max_position * 2)
		patrol_position = patrol_phase
		if patrol_position > max_position:
			patrol_position = 2 * max_position - patrol_position

		frame_buffer = []
		for index in range(pixels.n):
			base_mix = 0.5 + 0.5 * math.sin(index * 0.08 + frame * 0.03)
			base_color = blend_color((0, 35, 15), (20, 160, 70), base_mix)
			distance = abs(index - patrol_position)
			patrol_glow = max(0.0, 1.0 - distance / 22.0)
			patrol_glow = ease_in_out(patrol_glow)
			color = blend_color(base_color, (140, 255, 170), patrol_glow)
			level = 0.08 + 0.10 * breathe + 0.52 * patrol_glow
			frame_buffer.append(scale_color(color, min(0.82, level)))

		pixels[:] = frame_buffer
		pixels.show()
		clock.wait_frames()


def alert_guard_effect(pixels, clock: FrameClock, duration: float) -> None:
	# Pure amber warning — no mixed hues, back-and-forth scanner sweep
	_AMBER = (255, 140, 0)
	_BRIGHT = (255, 210, 80)
	frames = max(1, int(duration * TARGET_FPS))
	max_position = max(1, pixels.n - 1)
	for frame in range(frames):
		pulse = ease_in_out(0.5 + 0.5 * math.sin(frame * 0.28))
		sweep_phase = (frame * 1.6) % (max_position * 2)
		sweep = sweep_phase if sweep_phase <= max_position else 2 * max_position - sweep_phase
		frame_buffer = []
		for index in range(pixels.n):
			distance = abs(index - sweep)
			sweep_glow = ease_in_out(max(0.0, 1.0 - distance / 35.0))
			color = blend_color(_AMBER, _BRIGHT, sweep_glow)
			level = 0.18 + 0.45 * pulse + 0.37 * sweep_glow
			frame_buffer.append(scale_color(color, min(0.95, level)))

		pixels[:] = frame_buffer
		pixels.show()
		clock.wait_frames()


def alarm_effect(pixels, clock: FrameClock, duration: float) -> None:
	# Police strobe: left=red, right=blue, each side double-burst then swap
	_RED = (255, 0, 0)
	_BLUE = (0, 0, 255)
	_CYCLE = 32  # ≈ 0.53 s per full cycle at 60 FPS
	_LEFT_ON = frozenset({0, 1, 2, 3, 7, 8, 9, 10})
	_RIGHT_ON = frozenset({18, 19, 20, 21, 25, 26, 27, 28})
	frames = max(1, int(duration * TARGET_FPS))
	split = pixels.n // 2
	for frame in range(frames):
		tick = frame % _CYCLE
		left_active = tick in _LEFT_ON
		right_active = tick in _RIGHT_ON
		frame_buffer = []
		for index in range(pixels.n):
			if index < split:
				color = _RED if left_active else BLACK
			else:
				color = _BLUE if right_active else BLACK
			frame_buffer.append(scale_color(color))

		pixels[:] = frame_buffer
		pixels.show()
		clock.wait_frames()


SCENES = {
	"daily": ("撤防 / 日常经营", business_hours_effect),
	"guard": ("布防 / 守卫中", guard_idle_effect),
	"alert": ("布防 / 警戒状态", alert_guard_effect),
	"alarm": ("布防 / 异常告警", alarm_effect),
}


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description="VigiDoor LED scene tester")
	parser.add_argument(
		"--scene",
		choices=[*SCENES.keys(), "all"],
		default="all",
		help="Run a single scene or all scenes in sequence.",
	)
	parser.add_argument(
		"--duration",
		type=float,
		default=12.0,
		help="Seconds to run each scene.",
	)
	parser.add_argument(
		"--repeat",
		action="store_true",
		help="Loop the selected scenes until interrupted.",
	)
	args = parser.parse_args()
	if args.duration <= 0:
		parser.error("--duration must be greater than 0")
	return args


def main() -> None:
	args = parse_args()
	pixels, backend = create_pixels()
	warn_if_spi_buffer_is_too_small(backend)
	clock = FrameClock(TARGET_FPS)
	selected_scenes = list(SCENES) if args.scene == "all" else [args.scene]

	try:
		while True:
			for scene_name in selected_scenes:
				label, effect = SCENES[scene_name]
				print(f"Running scene: {label}")
				effect(pixels, clock, args.duration)
				pixels.fill(BLACK)
				pixels.show()
				clock.wait_frames(6)
			if not args.repeat:
				break
	except KeyboardInterrupt:
		pass
	finally:
		pixels.fill(BLACK)
		pixels.show()
		if hasattr(pixels, "deinit"):
			pixels.deinit()


if __name__ == "__main__":
	main()