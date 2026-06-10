from app.downloader import build_format_selector, build_ydl_opts
from app.models import DownloadRequest


def test_video_format_selector_with_resolution():
    req = DownloadRequest(url="u", kind="video", resolution=720)
    selector = build_format_selector(req)
    assert selector == "bestvideo[height<=720]+bestaudio/best[height<=720]/best"


def test_video_format_selector_without_resolution_uses_best():
    req = DownloadRequest(url="u", kind="video")
    selector = build_format_selector(req)
    assert selector == "bestvideo+bestaudio/best"


def test_audio_format_selector_is_bestaudio():
    req = DownloadRequest(url="u", kind="audio", bitrate=192)
    selector = build_format_selector(req)
    assert selector == "bestaudio/best"


def test_ydl_opts_audio_has_extract_postprocessor():
    req = DownloadRequest(url="u", kind="audio", bitrate=192, audio_format="mp3")
    opts = build_ydl_opts(req, outdir="/tmp/out", progress_hook=lambda d: None)
    pps = opts["postprocessors"]
    assert any(p["key"] == "FFmpegExtractAudio" for p in pps)
    extract = next(p for p in pps if p["key"] == "FFmpegExtractAudio")
    assert extract["preferredcodec"] == "mp3"
    assert extract["preferredquality"] == "192"


def test_ydl_opts_video_merges_to_mp4():
    req = DownloadRequest(url="u", kind="video", resolution=1080)
    opts = build_ydl_opts(req, outdir="/tmp/out", progress_hook=lambda d: None)
    assert opts["merge_output_format"] == "mp4"
    assert opts["format"] == "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best"


def test_ydl_opts_subtitles_enabled():
    req = DownloadRequest(url="u", kind="video", subtitles=True, sub_lang="es")
    opts = build_ydl_opts(req, outdir="/tmp/out", progress_hook=lambda d: None)
    assert opts["writesubtitles"] is True
    assert opts["writeautomaticsub"] is True
    assert opts["subtitleslangs"] == ["es"]


def test_ydl_opts_outdir_in_template():
    req = DownloadRequest(url="u", kind="video")
    opts = build_ydl_opts(req, outdir="/tmp/out", progress_hook=lambda d: None)
    assert opts["outtmpl"].startswith("/tmp/out/")
