#!/usr/bin/env python3
"""WM8960 Audio HAT speaker & dual-mic test for Raspberry Pi 5.

Usage examples:
  python3 tests/test_audio_io.py --list
  python3 tests/test_audio_io.py --play
  python3 tests/test_audio_io.py --record 5
  python3 tests/test_audio_io.py --record 5 --play-record

Notes:
- This script uses ALSA tools (aplay/arecord). Make sure alsa-utils is installed.
- If your device card name is not default, use --card to specify it.
"""

from __future__ import annotations

import argparse
import math
import os
import subprocess
import sys
import tempfile
import wave
from dataclasses import dataclass
from typing import Optional


@dataclass
class AudioParams:
    rate: int = 16000
    channels: int = 2
    width: int = 2  # bytes per sample
    duration: float = 2.0
    frequency: float = 440.0


def _run(cmd: list[str]) -> int:
    try:
        return subprocess.call(cmd)
    except FileNotFoundError:
        print(f"Command not found: {cmd[0]}. Please install alsa-utils.")
        return 127


def list_devices() -> int:
    print("=== aplay -l ===")
    _run(["aplay", "-l"])
    print("\n=== arecord -l ===")
    return _run(["arecord", "-l"])


def generate_sine_wav(path: str, params: AudioParams) -> None:
    frames = int(params.rate * params.duration)
    amplitude = 0.3

    with wave.open(path, "wb") as wf:
        wf.setnchannels(params.channels)
        wf.setsampwidth(params.width)
        wf.setframerate(params.rate)

        for i in range(frames):
            sample = amplitude * math.sin(2 * math.pi * params.frequency * (i / params.rate))
            value = int(sample * ((2 ** (params.width * 8 - 1)) - 1))
            # stereo: duplicate sample
            frame = value.to_bytes(params.width, byteorder="little", signed=True) * params.channels
            wf.writeframesraw(frame)


def play_wav(path: str, card: Optional[str]) -> int:
    cmd = ["aplay", "-q"]
    if card:
        cmd += ["-D", card]
    cmd.append(path)
    return _run(cmd)


def record_wav(path: str, seconds: int, params: AudioParams, card: Optional[str]) -> int:
    cmd = [
        "arecord",
        "-q",
        "-f",
        "S16_LE",
        "-r",
        str(params.rate),
        "-c",
        str(params.channels),
        "-d",
        str(seconds),
    ]
    if card:
        cmd += ["-D", card]
    cmd.append(path)
    return _run(cmd)


def detect_wm8960_card() -> Optional[str]:
    """Return an ALSA device string like plughw:2,0 if WM8960 is found."""
    cards_path = "/proc/asound/cards"
    try:
        with open(cards_path, "r", encoding="utf-8") as f:
            data = f.read()
    except OSError:
        return None

    # Example line: " 2 [seeed2micvoicec ]: ..."
    for line in data.splitlines():
        if "seeed-2mic-voicecard" in line or "seeed2micvoicec" in line:
            parts = line.strip().split(" ")
            if parts and parts[0].isdigit():
                return f"plughw:{parts[0]},0"
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="WM8960 speaker & dual-mic test")
    parser.add_argument("--list", action="store_true", help="List ALSA capture/playback devices")
    parser.add_argument("--play", action="store_true", help="Play a test tone")
    parser.add_argument("--record", type=int, default=0, help="Record N seconds to a WAV file")
    parser.add_argument("--play-record", action="store_true", help="Play back the recorded WAV")
    parser.add_argument("--card", type=str, default=None, help="ALSA device name, e.g. 'plughw:0,0' or 'default'")
    parser.add_argument("--rate", type=int, default=16000, help="Sample rate for record/play")
    parser.add_argument("--channels", type=int, default=2, help="Number of channels (2 for dual mic)")
    args = parser.parse_args()

    if args.list:
        return list_devices()

    auto_card = detect_wm8960_card()
    chosen_card = args.card or auto_card

    params = AudioParams(rate=args.rate, channels=args.channels)

    tmp_dir = tempfile.mkdtemp(prefix="vigidoor_audio_")
    tone_path = os.path.join(tmp_dir, "test_tone.wav")
    rec_path = os.path.join(tmp_dir, "recorded.wav")

    if args.play:
        print("Generating test tone...")
        generate_sine_wav(tone_path, params)
        print(f"Playing test tone via {chosen_card or 'default'}...")
        ret = play_wav(tone_path, chosen_card)
        if ret != 0:
            return ret

    if args.record > 0:
        print(f"Recording {args.record}s to {rec_path} via {chosen_card or 'default'}...")
        ret = record_wav(rec_path, args.record, params, chosen_card)
        if ret != 0:
            return ret
        print("Recording saved:", rec_path)

        if args.play_record:
            print("Playing back recording...")
            return play_wav(rec_path, chosen_card)

    if not (args.list or args.play or args.record > 0):
        parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
