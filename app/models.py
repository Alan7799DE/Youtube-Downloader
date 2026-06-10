from typing import Literal, Optional

from pydantic import BaseModel


class InfoRequest(BaseModel):
    url: str


class DownloadRequest(BaseModel):
    url: str
    kind: Literal["video", "audio"]
    resolution: Optional[int] = None   # e.g. 1080, 720; used when kind == "video"
    bitrate: Optional[int] = None      # e.g. 128, 192, 256, 320; used when kind == "audio"
    audio_format: Literal["mp3", "m4a"] = "mp3"
    subtitles: bool = False
    sub_lang: str = "en"


class VideoInfo(BaseModel):
    title: str
    thumbnail: Optional[str] = None
    duration: Optional[int] = None
    is_playlist: bool = False
    entries_count: Optional[int] = None
    available_heights: list[int] = []


class JobCreated(BaseModel):
    job_id: str
