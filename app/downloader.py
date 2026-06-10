import os
from typing import Callable

from app.models import DownloadRequest

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
