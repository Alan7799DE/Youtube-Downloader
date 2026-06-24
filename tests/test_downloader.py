import os
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.downloader import build_format_selector, build_ydl_opts, cleanup_expired, extract_info, run_download
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


SINGLE_VIDEO_INFO = {
    "title": "Demo Video",
    "thumbnail": "http://img/thumb.jpg",
    "duration": 213,
    "formats": [
        {"height": 1080}, {"height": 720}, {"height": 720}, {"height": None},
    ],
}

PLAYLIST_INFO = {
    "title": "My Playlist",
    "_type": "playlist",
    "entries": [{"id": "a"}, {"id": "b"}, {"id": "c"}],
}


def test_extract_info_single_video():
    fake_ydl = MagicMock()
    fake_ydl.extract_info.return_value = SINGLE_VIDEO_INFO
    with patch("app.downloader.YoutubeDL") as YDL:
        YDL.return_value.__enter__.return_value = fake_ydl
        info = extract_info("https://youtu.be/abc")
    assert info.title == "Demo Video"
    assert info.is_playlist is False
    assert info.duration == 213
    assert info.available_heights == [1080, 720]  # deduped, descending


def test_extract_info_playlist():
    fake_ydl = MagicMock()
    fake_ydl.extract_info.return_value = PLAYLIST_INFO
    with patch("app.downloader.YoutubeDL") as YDL:
        YDL.return_value.__enter__.return_value = fake_ydl
        info = extract_info("https://youtu.be/list")
    assert info.is_playlist is True
    assert info.entries_count == 3
    assert info.title == "My Playlist"


def test_run_download_single_file_returned(tmp_path):
    req = DownloadRequest(url="u", kind="video", resolution=720)

    def fake_download(outdir):
        # Simulate yt-dlp writing one output file.
        f = Path(outdir) / "Demo Video.mp4"
        f.write_text("video-bytes")
        return [f]

    result = run_download(req, str(tmp_path), progress_hook=lambda d: None,
                          _writer=fake_download)
    assert result.name == "Demo Video.mp4"
    assert result.read_text() == "video-bytes"


def test_run_download_multiple_files_zipped(tmp_path):
    req = DownloadRequest(url="u", kind="audio", bitrate=192)

    def fake_download(outdir):
        files = []
        for name in ["a.mp3", "b.mp3"]:
            f = Path(outdir) / name
            f.write_text(name)
            files.append(f)
        return files

    result = run_download(req, str(tmp_path), progress_hook=lambda d: None,
                          _writer=fake_download)
    assert result.suffix == ".zip"
    with zipfile.ZipFile(result) as z:
        assert sorted(z.namelist()) == ["a.mp3", "b.mp3"]


import time as _time


def test_cleanup_removes_old_dirs(tmp_path):
    old = tmp_path / "oldjob"
    old.mkdir()
    (old / "f.mp4").write_text("x")
    # Backdate its modification time by 2 hours.
    two_hours_ago = _time.time() - 7200
    os.utime(old, (two_hours_ago, two_hours_ago))

    fresh = tmp_path / "freshjob"
    fresh.mkdir()
    (fresh / "f.mp4").write_text("x")

    cleanup_expired(str(tmp_path), ttl_seconds=3600)

    assert not old.exists()
    assert fresh.exists()


from app.downloader import is_radio_mix


def test_is_radio_mix_detects_rd_lists():
    assert is_radio_mix("https://youtu.be/abc?list=RDabc") is True
    assert is_radio_mix("https://www.youtube.com/watch?v=abc&list=RDMMxyz") is True


def test_is_radio_mix_false_for_real_playlists_and_plain_videos():
    assert is_radio_mix("https://youtu.be/abc?list=PLxyz") is False
    assert is_radio_mix("https://youtu.be/abc") is False


def test_ydl_opts_noplaylist_true_for_radio_mix():
    req = DownloadRequest(url="https://youtu.be/abc?list=RDabc", kind="video")
    opts = build_ydl_opts(req, outdir="/tmp/out", progress_hook=lambda d: None)
    assert opts["noplaylist"] is True


def test_ydl_opts_noplaylist_false_for_real_playlist():
    req = DownloadRequest(url="https://youtu.be/abc?list=PLabc", kind="video")
    opts = build_ydl_opts(req, outdir="/tmp/out", progress_hook=lambda d: None)
    assert opts["noplaylist"] is False
