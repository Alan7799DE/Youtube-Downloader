import os
from typing import Callable

from yt_dlp import YoutubeDL

from app.models import DownloadRequest, VideoInfo

ProgressHook = Callable[[dict], None]


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
        "noplaylist": False,
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
    opts = {"quiet": True, "no_warnings": True, "skip_download": True}
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
