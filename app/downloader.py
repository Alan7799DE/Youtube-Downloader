import glob
import os
import re
import shutil
import time
import zipfile
from pathlib import Path
from typing import Callable, Optional

from yt_dlp import YoutubeDL

from app.models import DownloadRequest, VideoInfo

ProgressHook = Callable[[dict], None]


def is_radio_mix(url: str) -> bool:
    """A YouTube auto-generated "Mix"/radio (list=RD...) is an endless feed, not a
    real playlist. Treat it as a single video instead of downloading hundreds of
    auto-picked tracks."""
    return bool(re.search(r"[?&]list=RD", url))


def build_format_selector(req: DownloadRequest) -> str:
    if req.kind == "audio":
        return "bestaudio/best"
    if req.resolution:
        h = req.resolution
        return f"bestvideo[height<={h}]+bestaudio/best[height<={h}]/best"
    return "bestvideo+bestaudio/best"


def build_ydl_opts(req: DownloadRequest, outdir: str, progress_hook: ProgressHook) -> dict:
    opts: dict = {
        "format": build_format_selector(req),
        "outtmpl": os.path.join(outdir, "%(title)s.%(ext)s"),
        "progress_hooks": [progress_hook],
        "noplaylist": is_radio_mix(req.url),
        "quiet": True,
        "no_warnings": True,
        "postprocessors": [],
    }

    if req.kind == "video":
        opts["merge_output_format"] = "mp4"
    else:  # audio
        opts["postprocessors"].append({
            "key": "FFmpegExtractAudio",
            "preferredcodec": req.audio_format,
            "preferredquality": str(req.bitrate or 192),
        })

    if req.subtitles:
        opts["writesubtitles"] = True
        opts["writeautomaticsub"] = True
        opts["subtitleslangs"] = [req.sub_lang]
        opts["subtitlesformat"] = "srt"

    return opts


def extract_info(url: str) -> VideoInfo:
    # extract_flat keeps playlist/mix lookups fast: entries are listed without
    # extracting full metadata for every video (a radio "mix" can be huge).
    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": "in_playlist",
        "noplaylist": is_radio_mix(url),
    }
    with YoutubeDL(opts) as ydl:
        data = ydl.extract_info(url, download=False)

    if data.get("_type") == "playlist" or "entries" in data:
        entries = data.get("entries") or []
        return VideoInfo(
            title=data.get("title", "Playlist"),
            thumbnail=data.get("thumbnail"),
            duration=None,
            is_playlist=True,
            entries_count=len(list(entries)),
            available_heights=[],
        )

    heights = sorted(
        {f["height"] for f in data.get("formats", []) if f.get("height")},
        reverse=True,
    )
    return VideoInfo(
        title=data.get("title", "video"),
        thumbnail=data.get("thumbnail"),
        duration=data.get("duration"),
        is_playlist=False,
        entries_count=None,
        available_heights=heights,
    )


def cleanup_expired(base_dir: str, ttl_seconds: int) -> None:
    if not os.path.isdir(base_dir):
        return
    now = time.time()
    for name in os.listdir(base_dir):
        path = os.path.join(base_dir, name)
        if not os.path.isdir(path):
            continue
        age = now - os.path.getmtime(path)
        if age > ttl_seconds:
            shutil.rmtree(path, ignore_errors=True)


def _default_writer(opts: dict, url: str, outdir: str) -> list[Path]:
    before = set(glob.glob(os.path.join(outdir, "*")))
    with YoutubeDL(opts) as ydl:
        ydl.download([url])
    after = set(glob.glob(os.path.join(outdir, "*")))
    new_files = [Path(p) for p in sorted(after - before)]
    return new_files


def run_download(
    req: DownloadRequest,
    outdir: str,
    progress_hook: ProgressHook,
    _writer: Optional[Callable[[str], list[Path]]] = None,
) -> Path:
    os.makedirs(outdir, exist_ok=True)

    if _writer is not None:
        files = _writer(outdir)
    else:
        opts = build_ydl_opts(req, outdir, progress_hook)
        files = _default_writer(opts, req.url, outdir)

    files = [f for f in files if f.is_file()]
    if not files:
        raise RuntimeError("No output file was produced")

    if len(files) == 1:
        return files[0]

    zip_path = Path(outdir) / "download.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            z.write(f, arcname=f.name)
    return zip_path
