#!/usr/bin/env python3
"""StreamAudioPlayer Opus playback validation.

This script:
1. Reads assets/audio/bgm.wav
2. Converts audio to 16kHz mono PCM16
3. Encodes PCM frames into Opus packets
4. Feeds packets to StreamAudioPlayer in real-time pace

Usage:
  python3 tests/test_stream_player_opus.py
  python3 tests/test_stream_player_opus.py --wav /path/to/file.wav
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import wave
from pathlib import Path

import numpy as np
import opuslib

# Ensure project root is importable when running from tests/ directly.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.audio.stream_player import StreamAudioPlayer


TARGET_SAMPLE_RATE = 16000
TARGET_CHANNELS = 1
FRAME_SAMPLES = 320  # 20ms at 16kHz


def load_wav_as_mono_float32(path: Path) -> tuple[np.ndarray, int]:
    """Load PCM WAV and return mono float32 audio in [-1, 1], plus source sample rate."""
    with wave.open(str(path), "rb") as wf:
        channels = wf.getnchannels()
        sample_width = wf.getsampwidth()
        sample_rate = wf.getframerate()
        nframes = wf.getnframes()
        raw = wf.readframes(nframes)

    if sample_width == 1:
        data = np.frombuffer(raw, dtype=np.uint8).astype(np.float32)
        data = (data - 128.0) / 128.0
    elif sample_width == 2:
        data = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    elif sample_width == 4:
        data = np.frombuffer(raw, dtype=np.int32).astype(np.float32) / 2147483648.0
    else:
        raise ValueError(f"Unsupported WAV sample width: {sample_width} bytes")

    if channels > 1:
        data = data.reshape(-1, channels).mean(axis=1)

    return data, sample_rate


def resample_linear(audio: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
    """Resample audio with linear interpolation to avoid extra dependencies."""
    if src_rate == dst_rate:
        return audio
    if len(audio) == 0:
        return audio

    src_len = len(audio)
    dst_len = int(round(src_len * dst_rate / src_rate))
    src_x = np.linspace(0.0, 1.0, num=src_len, endpoint=False)
    dst_x = np.linspace(0.0, 1.0, num=dst_len, endpoint=False)
    return np.interp(dst_x, src_x, audio).astype(np.float32)


def float32_to_pcm16_bytes(audio: np.ndarray) -> bytes:
    clipped = np.clip(audio, -1.0, 1.0)
    pcm = (clipped * 32767.0).astype(np.int16)
    return pcm.tobytes()


def encode_opus_packets(pcm16: bytes, frame_samples: int = FRAME_SAMPLES) -> list[bytes]:
    encoder = opuslib.Encoder(TARGET_SAMPLE_RATE, TARGET_CHANNELS, opuslib.APPLICATION_AUDIO)
    packets: list[bytes] = []

    bytes_per_sample = 2
    frame_bytes = frame_samples * TARGET_CHANNELS * bytes_per_sample

    for offset in range(0, len(pcm16), frame_bytes):
        chunk = pcm16[offset : offset + frame_bytes]
        if len(chunk) < frame_bytes:
            chunk = chunk + b"\x00" * (frame_bytes - len(chunk))
        packets.append(encoder.encode(chunk, frame_samples))

    return packets


def run_test(wav_path: Path) -> int:
    if not wav_path.exists():
        print(f"[ERROR] WAV file not found: {wav_path}")
        return 1

    print(f"[INFO] Loading WAV: {wav_path}")
    audio, src_rate = load_wav_as_mono_float32(wav_path)
    print(f"[INFO] Source sample rate: {src_rate} Hz, samples: {len(audio)}")
    #Source sample rate: 44100 Hz, samples: 6386443

    audio_16k = resample_linear(audio, src_rate, TARGET_SAMPLE_RATE)
    pcm16 = float32_to_pcm16_bytes(audio_16k)
    packets = encode_opus_packets(pcm16)

    duration_sec = len(audio_16k) / TARGET_SAMPLE_RATE
    print(f"[INFO] Converted to 16k mono. Duration: {duration_sec:.2f}s, Opus packets: {len(packets)}")

    player = StreamAudioPlayer(
        sample_rate=TARGET_SAMPLE_RATE,
        channels=TARGET_CHANNELS,
        max_frame_size=FRAME_SAMPLES,
    )

    if not player.start():
        print("[ERROR] Failed to start StreamAudioPlayer")
        return 2

    print("[INFO] Feeding Opus packets to StreamAudioPlayer...")
    frame_interval = FRAME_SAMPLES / TARGET_SAMPLE_RATE

    start_t = time.time()
    try:
        for packet in packets:
            player.enqueue_opus(packet)
            # Keep approximate real-time pacing.
            time.sleep(frame_interval)

        time.sleep(1.0)
    finally:
        player.stop()

    elapsed = time.time() - start_t
    print(f"[OK] Playback test completed. Elapsed: {elapsed:.2f}s")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Test StreamAudioPlayer with WAV->Opus stream")
    parser.add_argument(
        "--wav",
        type=str,
        default=str(PROJECT_ROOT / "assets" / "audio" / "bgm.wav"),
        help="Path to source WAV file",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    wav_path = Path(args.wav).expanduser().resolve()
    return run_test(wav_path)


if __name__ == "__main__":
    raise SystemExit(main())
