"""
LED 灯效实现 - 四场景逐像素动画
"""

import math
import time
from typing import List, Tuple
from .base import EffectBase

# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

_MASTER_BRIGHTNESS = 0.99


def _ease_in_out(value: float) -> float:
    return value * value * (3.0 - 2.0 * value)


def _scale_color(color: Tuple[int, int, int], level: float = 1.0) -> Tuple[int, int, int]:
    intensity = max(0.0, min(1.0, _MASTER_BRIGHTNESS * level))
    return tuple(int(channel * intensity + 0.5) for channel in color)


def _blend_color(
    start: Tuple[int, int, int],
    end: Tuple[int, int, int],
    amount: float,
) -> Tuple[int, int, int]:
    ratio = max(0.0, min(1.0, amount))
    return tuple(
        int(start[i] + (end[i] - start[i]) * ratio + 0.5)
        for i in range(3)
    )


def _add_color(base: Tuple[int, int, int], extra: Tuple[int, int, int]) -> Tuple[int, int, int]:
    return tuple(min(255, base[i] + extra[i]) for i in range(3))


# ---------------------------------------------------------------------------
# 场景效果类
# ---------------------------------------------------------------------------

class BusinessHoursEffect(EffectBase):
    """撤防 / 日常经营 — 极光调色板 + 双彗星流光 + 随机闪烁"""

    _PALETTE = [
        (0, 210, 255),
        (80, 60, 255),
        (180, 0, 255),
        (255, 160, 0),
        (0, 255, 160),
        (0, 210, 255),
    ]
    _STOPS = len(_PALETTE) - 1

    def __init__(self, pixel_count: int):
        super().__init__("BusinessHours")
        self._n = pixel_count
        self._start_time = 0.0
        self._sparkle: List[float] = []

    def _sample_palette(self, t: float) -> Tuple[int, int, int]:
        t = t % 1.0
        pos = t * self._STOPS
        idx = int(pos)
        frac = pos - idx
        return _blend_color(self._PALETTE[idx], self._PALETTE[min(idx + 1, self._STOPS)], frac)

    def start(self):
        self._is_running = True
        self._start_time = time.time()
        self._sparkle = [0.0] * self._n

    def update(self) -> List[Tuple[int, int, int]]:
        if not self._is_running:
            return [(0, 0, 0)] * self._n

        frame = (time.time() - self._start_time) * 60.0
        n = self._n

        if int(frame) % 5 == 0:
            spark_idx = (int(frame) * 73 + (int(frame) // 5) * 137) % n
            self._sparkle[spark_idx] = 1.0
        self._sparkle = [max(0.0, s - 0.07) for s in self._sparkle]

        breath = 0.55 + 0.45 * math.sin(frame * 0.014)
        comet_a = frame * 1.2 % n
        comet_b = (frame * 0.6 + n * 0.55) % n

        result = []
        for index in range(n):
            palette_t = (index / n + frame * 0.0008) % 1.0
            color = self._sample_palette(palette_t)

            wave = 0.5 + 0.5 * math.sin(index * 0.06 - frame * 0.04)
            level = 0.08 + 0.18 * breath * wave

            dist_a = min(abs(index - comet_a), n - abs(index - comet_a))
            glow_a = _ease_in_out(max(0.0, 1.0 - dist_a / 18.0))
            color = _blend_color(color, (220, 255, 255), glow_a * 0.75)
            level += 0.45 * glow_a

            dist_b = min(abs(index - comet_b), n - abs(index - comet_b))
            glow_b = _ease_in_out(max(0.0, 1.0 - dist_b / 30.0))
            color = _blend_color(color, (255, 200, 60), glow_b * 0.65)
            level += 0.36 * glow_b

            if self._sparkle[index] > 0.0:
                s = _ease_in_out(self._sparkle[index])
                color = _blend_color(color, (255, 255, 255), s * 0.9)
                level += 0.40 * s

            result.append(_scale_color(color, min(0.94, level)))

        return result

    def stop(self):
        self._is_running = False


class GuardIdleEffect(EffectBase):
    """布防 / 守卫中 — 深蓝青色底 + 来回巡逻扫光"""

    def __init__(self, pixel_count: int):
        super().__init__("GuardIdle")
        self._n = pixel_count
        self._start_time = 0.0

    def start(self):
        self._is_running = True
        self._start_time = time.time()

    def update(self) -> List[Tuple[int, int, int]]:
        if not self._is_running:
            return [(0, 0, 0)] * self._n

        frame = (time.time() - self._start_time) * 60.0
        n = self._n
        max_pos = max(1, n - 1)

        breathe = 0.5 + 0.5 * math.sin(frame * 0.05)
        patrol_phase = (frame * 1.3) % (max_pos * 2)
        patrol_pos = patrol_phase if patrol_phase <= max_pos else 2 * max_pos - patrol_phase

        result = []
        for index in range(n):
            base_mix = 0.5 + 0.5 * math.sin(index * 0.08 + frame * 0.03)
            base_color = _blend_color((0, 28, 88), (0, 135, 165), base_mix)
            distance = abs(index - patrol_pos)
            patrol_glow = _ease_in_out(max(0.0, 1.0 - distance / 22.0))
            color = _blend_color(base_color, (170, 255, 255), patrol_glow)
            level = 0.06 + 0.08 * breathe + 0.56 * patrol_glow
            result.append(_scale_color(color, min(0.85, level)))

        return result

    def stop(self):
        self._is_running = False


class AlertGuardEffect(EffectBase):
    """布防 / 警戒状态 — 纯琥珀色扫描 + 脉冲呼吸"""

    _AMBER = (255, 140, 0)
    _BRIGHT = (255, 210, 80)

    def __init__(self, pixel_count: int):
        super().__init__("AlertGuard")
        self._n = pixel_count
        self._start_time = 0.0

    def start(self):
        self._is_running = True
        self._start_time = time.time()

    def update(self) -> List[Tuple[int, int, int]]:
        if not self._is_running:
            return [(0, 0, 0)] * self._n

        frame = (time.time() - self._start_time) * 60.0
        n = self._n
        max_pos = max(1, n - 1)

        pulse = _ease_in_out(0.5 + 0.5 * math.sin(frame * 0.45))
        sweep_phase = (frame * 2.2) % (max_pos * 2)
        sweep = sweep_phase if sweep_phase <= max_pos else 2 * max_pos - sweep_phase

        result = []
        for index in range(n):
            distance = abs(index - sweep)
            sweep_glow = _ease_in_out(max(0.0, 1.0 - distance / 22.0))
            color = _blend_color(self._AMBER, self._BRIGHT, sweep_glow)
            level = 0.03 + 0.62 * pulse + 0.35 * sweep_glow
            result.append(_scale_color(color, min(0.98, level)))

        return result

    def stop(self):
        self._is_running = False


class AlarmEffect(EffectBase):
    """布防 / 异常告警 — 警察频闪（左红右蓝交替）"""

    _RED = (255, 0, 0)
    _BLUE = (0, 0, 255)
    _BLACK = (0, 0, 0)
    _CYCLE = 32  # ≈ 0.53 s per full cycle at 60 FPS

    def __init__(self, pixel_count: int):
        super().__init__("Alarm")
        self._n = pixel_count
        self._start_time = 0.0

    def start(self):
        self._is_running = True
        self._start_time = time.time()

    def update(self) -> List[Tuple[int, int, int]]:
        if not self._is_running:
            return [(0, 0, 0)] * self._n

        frame = (time.time() - self._start_time) * 60.0
        n = self._n
        split = n // 2

        tick = int(frame) % self._CYCLE
        phase_a = tick < 5 or 8 <= tick < 13
        phase_b = 18 <= tick < 23 or 26 <= tick < 31

        result = []
        for index in range(n):
            if phase_a:
                color = self._RED if index < split else self._BLUE
            elif phase_b:
                color = self._BLUE if index < split else self._RED
            else:
                color = self._BLACK
            result.append(_scale_color(color))

        return result

    def stop(self):
        self._is_running = False
