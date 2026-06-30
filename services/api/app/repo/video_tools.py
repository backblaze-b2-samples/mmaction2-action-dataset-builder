"""Local video segmentation + clip trimming for the action-dataset builder.

Confined to repo/ alongside b2_client.py / mmaction_engine.py so the heavy
media stack (scenedetect, imageio-ffmpeg) never leaks into higher layers,
mirroring the boto3-only-in-repo invariant.

Two responsibilities:

- `segment_video(...)`  — produce candidate action intervals from a source
  video, either by fixed-stride windowing (default, pure-ffprobe duration math)
  or content-aware scene detection (PySceneDetect).
- `trim_clip(...)`      — cut one interval to a short, browser-playable H.264
  mp4 (yuv420p, +faststart) using the imageio-ffmpeg BUNDLED ffmpeg binary, so
  there is no system-ffmpeg dependency and no libass/slim-build gotcha (we do
  no subtitle/text burning).

All heavy imports are LAZY (inside functions), so importing this module is free
and the API boots + tests pass without requirements-ml.txt installed. The module
returns plain Python data + clip bytes; the service layer persists them via the
repo's builds_store. No boto3 here.
"""

import logging
import os
import subprocess
import tempfile

logger = logging.getLogger(__name__)


class MissingMediaDependencies(RuntimeError):
    """Raised when the local media stack (requirements-ml.txt) is absent."""


def _ffmpeg_exe() -> str:
    """Path to the bundled libx264-capable ffmpeg binary (not system ffmpeg)."""
    try:
        import imageio_ffmpeg
    except ImportError as e:  # pragma: no cover - exercised only without ML deps
        raise MissingMediaDependencies(
            "imageio-ffmpeg is not installed. Install the media stack: "
            "`pip install -r requirements-ml.txt`"
        ) from e
    return imageio_ffmpeg.get_ffmpeg_exe()


def probe_duration(src_path: str) -> float:
    """Return a video's duration in seconds via the bundled ffprobe/ffmpeg.

    Uses ffmpeg (not ffprobe — the bundled wheel only ships ffmpeg) to read the
    container duration. Falls back to 0.0 if it cannot be determined.
    """
    exe = _ffmpeg_exe()
    proc = subprocess.run(
        [exe, "-i", src_path, "-hide_banner"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    stderr = (proc.stderr or b"").decode("utf-8", errors="replace")
    for line in stderr.splitlines():
        line = line.strip()
        if line.startswith("Duration:"):
            ts = line.split("Duration:", 1)[1].split(",", 1)[0].strip()
            try:
                h, m, s = ts.split(":")
                return int(h) * 3600 + int(m) * 60 + float(s)
            except ValueError:
                return 0.0
    return 0.0


def _stride_windows(
    duration: float, window: float, stride: float, max_clips: int
) -> list[tuple[float, float]]:
    """Fixed-stride candidate intervals clamped to the video duration."""
    if duration <= 0:
        return []
    window = max(0.5, window)
    stride = max(0.5, stride)
    intervals: list[tuple[float, float]] = []
    start = 0.0
    while start < duration and len(intervals) < max_clips:
        end = min(start + window, duration)
        if end - start >= 0.5:
            intervals.append((round(start, 3), round(end, 3)))
        start += stride
    return intervals


def _scene_intervals(
    src_path: str, duration: float, max_clips: int
) -> list[tuple[float, float]]:
    """Content-aware candidate intervals via PySceneDetect's ContentDetector."""
    try:
        from scenedetect import detect
        from scenedetect.detectors import ContentDetector
    except ImportError as e:  # pragma: no cover - exercised only without ML deps
        raise MissingMediaDependencies(
            "scenedetect is not installed. Install the media stack: "
            "`pip install -r requirements-ml.txt`"
        ) from e

    scene_list = detect(src_path, ContentDetector())
    intervals: list[tuple[float, float]] = []
    for start, end in scene_list:
        s = start.get_seconds()
        e = end.get_seconds()
        if e - s >= 0.5:
            intervals.append((round(s, 3), round(e, 3)))
        if len(intervals) >= max_clips:
            break
    # If the video is a single continuous shot, scene detection returns nothing
    # usable — fall back to one window over the whole clip so a build still runs.
    if not intervals and duration > 0:
        intervals.append((0.0, round(min(duration, 10.0), 3)))
    return intervals


def segment_video(
    src_path: str,
    *,
    strategy: str = "fixed-stride",
    window_seconds: float = 5.0,
    stride_seconds: float = 5.0,
    max_clips: int = 60,
) -> list[tuple[float, float]]:
    """Return candidate (start_s, end_s) action intervals for a source video.

    `fixed-stride` (default) slides a window of `window_seconds` every
    `stride_seconds`. `scene-detect` uses PySceneDetect's content-aware
    detector. Both are CPU-only compute. Capped at `max_clips`.
    """
    duration = probe_duration(src_path)
    if strategy == "scene-detect":
        return _scene_intervals(src_path, duration, max_clips)
    return _stride_windows(duration, window_seconds, stride_seconds, max_clips)


def trim_clip(src_path: str, start: float, end: float) -> bytes | None:
    """Trim [start, end) to a browser-playable H.264 mp4 and return its bytes.

    Re-encodes with libx264 / yuv420p / +faststart so the clip plays inline in a
    `<video>` element (and in the verify/screenshot steps). Returns None if the
    interval is empty. Raises RuntimeError on an ffmpeg failure.
    """
    if end <= start:
        return None
    exe = _ffmpeg_exe()
    out_fd, out_path = tempfile.mkstemp(suffix=".mp4")
    os.close(out_fd)
    cmd = [
        exe, "-y",
        "-ss", f"{start:.3f}",
        "-to", f"{end:.3f}",
        "-i", src_path,
        "-an",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        out_path,
    ]
    proc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        if os.path.exists(out_path):
            os.unlink(out_path)
        raise RuntimeError(
            f"ffmpeg clip trim failed: {(proc.stderr or b'')[-400:]!r}"
        )
    with open(out_path, "rb") as f:
        data = f.read()
    os.unlink(out_path)
    return data or None
