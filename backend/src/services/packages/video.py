"""
A TikTok video from the package's frames, only when `ffmpeg` is on the
PATH: each frame held SECONDS_PER_FRAME, H.264 in yuv420p at 30 fps,
1080x1920, no sound (a person adds the sound in TikTok's own editor,
where its licensed library is). Without ffmpeg the package is a photo
post and its manifest says the video was left out: ffmpeg is not a
dependency of the image or the app, by request.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

SECONDS_PER_FRAME = 4

# A few frames at 1080x1920 encode in seconds; this is a stuck process.
TIMEOUT_SECONDS = 120


def available() -> bool:

    return shutil.which("ffmpeg") is not None


def slideshow(frames: list[Path], out: Path) -> Path | None:
    """The video at `out`, or None when ffmpeg is missing or failed (the photos still stand)."""

    if not frames or not available():
        return None

    listing = out.with_suffix(".txt")

    # The concat demuxer's list: every frame for its duration, the last
    # named twice, which is how that demuxer holds the final frame.
    lines = []
    for frame in frames:
        lines.append(f"file '{frame.resolve().as_posix()}'")
        lines.append(f"duration {SECONDS_PER_FRAME}")
    lines.append(f"file '{frames[-1].resolve().as_posix()}'")

    listing.write_text("\n".join(lines) + "\n", encoding="utf-8")

    command = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "concat", "-safe", "0", "-i", str(listing),
        "-vf", "scale=1080:1920,format=yuv420p,fps=30",
        "-c:v", "libx264", "-preset", "veryfast", "-movflags", "+faststart",
        "-an", str(out),
    ]

    try:
        subprocess.run(command, check=True, timeout=TIMEOUT_SECONDS, capture_output=True)
    except (subprocess.SubprocessError, OSError):
        out.unlink(missing_ok=True)
        return None
    finally:
        listing.unlink(missing_ok=True)

    return out if out.exists() else None
