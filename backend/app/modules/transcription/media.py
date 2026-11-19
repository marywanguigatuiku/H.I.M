"""ffmpeg helpers: read the length of a recording and cut a piece of it for the engine."""
import json
import shutil
import subprocess
from pathlib import Path


class MediaError(Exception):
    pass


def tools_available() -> bool:
    return bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def probe_duration(path: Path) -> float:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
            capture_output=True, text=True, timeout=180,
        )
    except FileNotFoundError:
        raise MediaError("ffmpeg is not installed on the server")
    except subprocess.TimeoutExpired:
        raise MediaError("Reading the recording took too long")
    if out.returncode != 0:
        raise MediaError("This file could not be read as audio or video")
    try:
        duration = float(json.loads(out.stdout)["format"]["duration"])
    except (KeyError, ValueError, TypeError):
        raise MediaError("This file does not seem to contain audio")
    if duration <= 0:
        raise MediaError("This recording is empty")
    return duration


def make_chunk(src: Path, dst: Path, start: float, length: float) -> None:
    """Cuts [start, start+length] and converts it to small mono speech audio (Opus 32 kbps, 16 kHz)."""
    cmd = [
        "ffmpeg", "-nostdin", "-y", "-v", "error",
        "-ss", f"{start:.3f}", "-t", f"{length:.3f}", "-i", str(src),
        "-vn", "-ac", "1", "-ar", "16000", "-c:a", "libopus", "-b:a", "32k", "-application", "voip", str(dst),
    ]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=1200)
    except FileNotFoundError:
        raise MediaError("ffmpeg is not installed on the server")
    except subprocess.TimeoutExpired:
        raise MediaError("Preparing the audio took too long")
    if out.returncode != 0 or not dst.exists() or dst.stat().st_size == 0:
        raise MediaError("The audio could not be prepared: " + (out.stderr or "unknown error")[-200:])
