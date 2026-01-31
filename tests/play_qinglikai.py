#!/usr/bin/env python3
"""Play assets/audio/qinglikai.mp3 using an available system player.

Usage:
  python3 scripts/play_qinglikai.py
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def _find_player() -> list[str] | None:
    candidates: list[list[str]] = [
        ["ffplay", "-nodisp", "-autoexit", "-loglevel", "error"],
        ["mpg123", "-q"],
        ["cvlc", "--play-and-exit"],
        ["play", "-q"],
    ]
    for cmd in candidates:
        if shutil.which(cmd[0]):
            return cmd
    return None


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    audio_path = project_root / "assets" / "audio" / "qinglikai.mp3"

    if not audio_path.exists():
        print(f"Audio file not found: {audio_path}")
        return 1

    player = _find_player()
    if not player:
        print("No audio player found. Install one of: ffmpeg (ffplay), mpg123, vlc, or sox.")
        return 2

    cmd = player + [str(audio_path)]
    try:
        return subprocess.call(cmd)
    except FileNotFoundError:
        print(f"Player not found: {player[0]}")
        return 127


if __name__ == "__main__":
    raise SystemExit(main())
