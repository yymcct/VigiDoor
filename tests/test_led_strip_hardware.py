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
	frames = max(1, int(duration * TARGET_FPS))
	for frame in range(frames):
		frame_buffer = []
		lead_wave = (frame * 1.8) % max(1, pixels.n)
		trail_wave = (frame * 1.1 + pixels.n * 0.42) % max(1, pixels.n)
		breath = 0.5 + 0.5 * math.sin(frame * 0.04)
		for index in range(pixels.n):
			base_wave = 0.5 + 0.5 * math.sin(index * 0.08 - frame * 0.08)
			cross_wave = 0.5 + 0.5 * math.sin(index * 0.21 + frame * 0.16)
			color = blend_color((198, 218, 238), (240, 247, 255), base_wave)
			level = 0.05 + 0.10 * base_wave + 0.10 * cross_wave + 0.10 * breath

			lead_glow = max(0.0, 1.0 - abs(index - lead_wave) / 14.0)
			trail_glow = max(0.0, 1.0 - abs(index - trail_wave) / 24.0)
			travel_glow = max(ease_in_out(lead_glow), ease_in_out(trail_glow) * 0.8)

			wave_front = 0.5 + 0.5 * math.sin((index - frame * 1.35) * 0.16)
			wave_back = 0.5 + 0.5 * math.sin((index + frame * 0.9) * 0.09)
			wave_energy = max(0.0, wave_front - 0.45) * 0.9 + max(0.0, wave_back - 0.62) * 0.45

			if index % 24 in {0, 1}:
				color = blend_color(color, (120, 220, 255), 0.18)
				level += 0.05

			color = blend_color(color, (138, 228, 255), min(1.0, wave_energy) * 0.28)
			color = blend_color(color, (188, 250, 255), travel_glow * 0.82)
			level += 0.18 * min(1.0, wave_energy) + 0.34 * travel_glow

			frame_buffer.append(scale_color(color, min(0.72, level)))

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
			base_color = blend_color((0, 28, 88), (0, 135, 165), base_mix)
			distance = abs(index - patrol_position)
			patrol_glow = max(0.0, 1.0 - distance / 22.0)
			patrol_glow = ease_in_out(patrol_glow)
			color = blend_color(base_color, (170, 255, 255), patrol_glow)
			level = 0.08 + 0.10 * breathe + 0.52 * patrol_glow
			frame_buffer.append(scale_color(color, min(0.82, level)))

		pixels[:] = frame_buffer
		pixels.show()
		clock.wait_frames()


def alert_guard_effect(pixels, clock: FrameClock, duration: float) -> None:
	frames = max(1, int(duration * TARGET_FPS))
	for frame in range(frames):
		pulse = 0.5 + 0.5 * math.sin(frame * 0.18)
		sweep = (frame * 2.4) % max(1, pixels.n)
		frame_buffer = []
		for index in range(pixels.n):
			bar_on = ((index // 16) + (frame // 10)) % 2 == 0
			base_color = (255, 108, 0) if bar_on else (38, 8, 0)
			base_level = 0.30 if bar_on else 0.03

			distance = abs(index - sweep)
			sweep_glow = max(0.0, 1.0 - distance / 24.0)
			sweep_glow = ease_in_out(sweep_glow)
			color = blend_color(base_color, (255, 214, 120), sweep_glow)
			level = base_level + 0.18 * pulse + 0.42 * sweep_glow
			frame_buffer.append(scale_color(color, min(0.92, level)))

		pixels[:] = frame_buffer
		pixels.show()
		clock.wait_frames()


def alarm_effect(pixels, clock: FrameClock, duration: float) -> None:
	frames = max(1, int(duration * TARGET_FPS))
	for frame in range(frames):
		cycle = frame % 24
		left_active = cycle < 8 or 16 <= cycle < 18
		right_active = 8 <= cycle < 16 or 18 <= cycle < 20
		white_flash = cycle in {0, 8, 16, 17, 18, 19}
		split = pixels.n // 2
		frame_buffer = []
		for index in range(pixels.n):
			if index < split:
				color = (255, 0, 0) if left_active else (32, 0, 0)
				level = 1.0 if left_active else 0.05
			else:
				color = (0, 60, 255) if right_active else (0, 0, 32)
				level = 1.0 if right_active else 0.05

			edge_flash = max(0.0, 1.0 - min(index, pixels.n - 1 - index) / 18.0)
			edge_flash = ease_in_out(edge_flash)
			level += 0.10 * edge_flash

			if white_flash:
				color = add_color(color, (255, 255, 255))
				level = 1.0

			frame_buffer.append(scale_color(color, min(1.0, level)))

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