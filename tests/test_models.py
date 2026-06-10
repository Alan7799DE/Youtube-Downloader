import pytest
from pydantic import ValidationError

from app.models import InfoRequest, DownloadRequest, VideoInfo


def test_info_request_requires_url():
    req = InfoRequest(url="https://youtu.be/abc")
    assert req.url == "https://youtu.be/abc"


def test_download_request_video_defaults():
    req = DownloadRequest(url="https://youtu.be/abc", kind="video", resolution=1080)
    assert req.kind == "video"
    assert req.resolution == 1080
    assert req.subtitles is False
    assert req.sub_lang == "en"


def test_download_request_audio_with_bitrate():
    req = DownloadRequest(url="https://youtu.be/abc", kind="audio", bitrate=320)
    assert req.kind == "audio"
    assert req.bitrate == 320


def test_download_request_rejects_unknown_kind():
    with pytest.raises(ValidationError):
        DownloadRequest(url="https://youtu.be/abc", kind="hologram")


def test_video_info_shape():
    info = VideoInfo(
        title="Demo",
        thumbnail="http://img",
        duration=120,
        is_playlist=False,
        entries_count=None,
        available_heights=[1080, 720, 480],
    )
    assert info.available_heights == [1080, 720, 480]
