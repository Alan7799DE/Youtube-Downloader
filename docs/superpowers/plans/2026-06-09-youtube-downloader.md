# YouTube Downloader Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a self-hosted web app that downloads YouTube videos (MP4 with selectable resolution), audio (MP3/M4A with selectable bitrate), whole playlists (as ZIP), and subtitles (.srt in ZIP), with a real-time progress bar.

**Architecture:** A single FastAPI app serves a lightweight HTML/JS frontend and a JSON+SSE API. It uses `yt-dlp` as a Python library and `ffmpeg` for muxing/extraction. Jobs are tracked in memory; downloads run in background tasks with a concurrency semaphore. The whole thing ships as one Docker image.

**Tech Stack:** Python 3.12, FastAPI, Uvicorn, yt-dlp, ffmpeg (system binary), pytest, vanilla HTML/CSS/JS.

---

## File Structure

```
youtube-downloader/
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI app, routes, static mount, lifespan
│   ├── config.py        # Settings from env vars (port, concurrency, TTL)
│   ├── models.py        # Pydantic request/response schemas
│   ├── jobs.py          # In-memory job registry (thread-safe)
│   └── downloader.py    # yt-dlp wrapper: info, format selection, download, zip
├── static/
│   ├── index.html       # UI (English)
│   ├── app.js           # Fetch info, start download, SSE progress, file download
│   └── style.css        # Simple styling
├── tests/
│   ├── __init__.py
│   ├── conftest.py      # Shared fixtures (TestClient, fake YoutubeDL)
│   ├── test_models.py
│   ├── test_jobs.py
│   ├── test_downloader.py
│   └── test_api.py
├── requirements.txt
├── requirements-dev.txt
├── Dockerfile
├── docker-compose.yml
├── .dockerignore
└── README.md
```

**Responsibilities:**
- `config.py` — single source of truth for tunables, read once from env.
- `models.py` — pure data shapes, no logic. Validates incoming requests.
- `jobs.py` — owns job lifecycle state. Knows nothing about yt-dlp or HTTP.
- `downloader.py` — owns everything yt-dlp/ffmpeg. Knows nothing about HTTP or jobs.
- `main.py` — wires HTTP routes to `jobs` + `downloader`. The only layer that knows about FastAPI.

This keeps `jobs` and `downloader` independently testable without a running server.

---

## Task 1: Project scaffolding + health endpoint

**Files:**
- Create: `requirements.txt`
- Create: `requirements-dev.txt`
- Create: `app/__init__.py` (empty)
- Create: `app/config.py`
- Create: `app/main.py`
- Create: `tests/__init__.py` (empty)
- Create: `tests/conftest.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: Create dependency files**

`requirements.txt`:
```
fastapi==0.115.6
uvicorn[standard]==0.34.0
yt-dlp==2025.5.22
```

`requirements-dev.txt`:
```
-r requirements.txt
pytest==8.3.4
httpx==0.28.1
```

- [ ] **Step 2: Create `app/config.py`**

```python
import os


class Settings:
    PORT: int = int(os.getenv("PORT", "8000"))
    MAX_CONCURRENT_DOWNLOADS: int = int(os.getenv("MAX_CONCURRENT_DOWNLOADS", "3"))
    FILE_TTL_SECONDS: int = int(os.getenv("FILE_TTL_SECONDS", "3600"))
    DOWNLOAD_DIR: str = os.getenv("DOWNLOAD_DIR", "/tmp/ytdl-downloads")


settings = Settings()
```

- [ ] **Step 3: Create empty `app/__init__.py` and `tests/__init__.py`**

```bash
touch app/__init__.py tests/__init__.py
```

- [ ] **Step 4: Create `tests/conftest.py`**

```python
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)
```

- [ ] **Step 5: Write the failing test in `tests/test_api.py`**

```python
def test_health_returns_ok(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
```

- [ ] **Step 6: Run test to verify it fails**

Run: `pytest tests/test_api.py::test_health_returns_ok -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.main'` (or ImportError).

- [ ] **Step 7: Create minimal `app/main.py`**

```python
from fastapi import FastAPI

app = FastAPI(title="YouTube Downloader")


@app.get("/api/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 8: Run test to verify it passes**

Run: `pytest tests/test_api.py::test_health_returns_ok -v`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add requirements.txt requirements-dev.txt app/ tests/
git commit -m "feat: project scaffolding with health endpoint"
```

---

## Task 2: Pydantic models

**Files:**
- Create: `app/models.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: Write the failing tests in `tests/test_models.py`**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.models'`.

- [ ] **Step 3: Create `app/models.py`**

```python
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


class JobStatusResponse(BaseModel):
    status: str
    progress: float
    filename: Optional[str] = None
    error: Optional[str] = None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_models.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add app/models.py tests/test_models.py
git commit -m "feat: add pydantic request/response models"
```

---

## Task 3: In-memory job registry

**Files:**
- Create: `app/jobs.py`
- Test: `tests/test_jobs.py`

- [ ] **Step 1: Write the failing tests in `tests/test_jobs.py`**

```python
from app.jobs import JobStore, JobState


def test_create_returns_unique_ids():
    store = JobStore()
    a = store.create()
    b = store.create()
    assert a != b
    assert store.get(a).status == "pending"


def test_update_progress():
    store = JobStore()
    job_id = store.create()
    store.update_progress(job_id, 42.5)
    assert store.get(job_id).progress == 42.5
    assert store.get(job_id).status == "downloading"


def test_set_done():
    store = JobStore()
    job_id = store.create()
    store.set_done(job_id, filepath="/tmp/x.mp4", filename="x.mp4")
    job = store.get(job_id)
    assert job.status == "done"
    assert job.progress == 100.0
    assert job.filepath == "/tmp/x.mp4"
    assert job.filename == "x.mp4"


def test_set_error():
    store = JobStore()
    job_id = store.create()
    store.set_error(job_id, "boom")
    job = store.get(job_id)
    assert job.status == "error"
    assert job.error == "boom"


def test_get_missing_returns_none():
    store = JobStore()
    assert store.get("nope") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_jobs.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.jobs'`.

- [ ] **Step 3: Create `app/jobs.py`**

```python
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class JobState:
    job_id: str
    status: str = "pending"       # pending | downloading | done | error
    progress: float = 0.0
    filename: Optional[str] = None
    filepath: Optional[str] = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, JobState] = {}
        self._lock = threading.Lock()

    def create(self) -> str:
        job_id = uuid.uuid4().hex
        with self._lock:
            self._jobs[job_id] = JobState(job_id=job_id)
        return job_id

    def get(self, job_id: str) -> Optional[JobState]:
        with self._lock:
            return self._jobs.get(job_id)

    def update_progress(self, job_id: str, progress: float) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.status = "downloading"
                job.progress = progress

    def set_done(self, job_id: str, filepath: str, filename: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.status = "done"
                job.progress = 100.0
                job.filepath = filepath
                job.filename = filename

    def set_error(self, job_id: str, message: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.status = "error"
                job.error = message

    def all_jobs(self) -> list[JobState]:
        with self._lock:
            return list(self._jobs.values())

    def remove(self, job_id: str) -> None:
        with self._lock:
            self._jobs.pop(job_id, None)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_jobs.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add app/jobs.py tests/test_jobs.py
git commit -m "feat: add thread-safe in-memory job registry"
```

---

## Task 4: Format selection logic (pure functions)

**Files:**
- Create: `app/downloader.py`
- Test: `tests/test_downloader.py`

- [ ] **Step 1: Write the failing tests in `tests/test_downloader.py`**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_downloader.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.downloader'`.

- [ ] **Step 3: Create `app/downloader.py` with the pure functions only**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_downloader.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: Commit**

```bash
git add app/downloader.py tests/test_downloader.py
git commit -m "feat: add yt-dlp format selection logic"
```

---

## Task 5: Info extraction (mocked yt-dlp)

**Files:**
- Modify: `app/downloader.py`
- Test: `tests/test_downloader.py` (append)

- [ ] **Step 1: Append failing tests to `tests/test_downloader.py`**

```python
from unittest.mock import MagicMock, patch

from app.downloader import extract_info


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_downloader.py -k extract_info -v`
Expected: FAIL — `ImportError: cannot import name 'extract_info'`.

- [ ] **Step 3: Add `extract_info` and the import to `app/downloader.py`**

At the top, add the import:
```python
from yt_dlp import YoutubeDL
```

Add the import for the model:
```python
from app.models import DownloadRequest, VideoInfo
```
(replace the existing `from app.models import DownloadRequest` line with this combined import)

Add the function:
```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_downloader.py -k extract_info -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add app/downloader.py tests/test_downloader.py
git commit -m "feat: extract video/playlist metadata via yt-dlp"
```

---

## Task 6: Download + ZIP packaging (mocked yt-dlp)

**Files:**
- Modify: `app/downloader.py`
- Test: `tests/test_downloader.py` (append)

- [ ] **Step 1: Append failing tests to `tests/test_downloader.py`**

```python
import zipfile
from pathlib import Path

from app.downloader import run_download


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_downloader.py -k run_download -v`
Expected: FAIL — `ImportError: cannot import name 'run_download'`.

- [ ] **Step 3: Add `run_download` and helpers to `app/downloader.py`**

Add imports at the top:
```python
import glob
import zipfile
from pathlib import Path
from typing import Optional
```

Add the functions:
```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_downloader.py -k run_download -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Run the full downloader test file**

Run: `pytest tests/test_downloader.py -v`
Expected: PASS (all)

- [ ] **Step 6: Commit**

```bash
git add app/downloader.py tests/test_downloader.py
git commit -m "feat: run download and zip multi-file outputs"
```

---

## Task 7: `/api/info` endpoint

**Files:**
- Modify: `app/main.py`
- Test: `tests/test_api.py` (append)

- [ ] **Step 1: Append failing tests to `tests/test_api.py`**

```python
from unittest.mock import patch

from app.models import VideoInfo


def test_info_endpoint_returns_metadata(client):
    fake = VideoInfo(title="Demo", thumbnail="http://img", duration=120,
                     is_playlist=False, entries_count=None,
                     available_heights=[1080, 720])
    with patch("app.main.extract_info", return_value=fake):
        resp = client.post("/api/info", json={"url": "https://youtu.be/abc"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "Demo"
    assert body["available_heights"] == [1080, 720]


def test_info_endpoint_handles_errors(client):
    with patch("app.main.extract_info", side_effect=Exception("Video unavailable")):
        resp = client.post("/api/info", json={"url": "https://youtu.be/bad"})
    assert resp.status_code == 400
    assert "unavailable" in resp.json()["detail"].lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_api.py -k info_endpoint -v`
Expected: FAIL — 404 Not Found (route doesn't exist yet).

- [ ] **Step 3: Add the route to `app/main.py`**

Replace the contents of `app/main.py` with:
```python
from fastapi import FastAPI, HTTPException

from app.downloader import extract_info
from app.models import InfoRequest, VideoInfo

app = FastAPI(title="YouTube Downloader")


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/info", response_model=VideoInfo)
def info(req: InfoRequest):
    try:
        return extract_info(req.url)
    except Exception as exc:  # surface a clean message to the UI
        raise HTTPException(status_code=400, detail=str(exc))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_api.py -k info_endpoint -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add app/main.py tests/test_api.py
git commit -m "feat: add /api/info endpoint"
```

---

## Task 8: `/api/download` endpoint + background worker

**Files:**
- Modify: `app/main.py`
- Test: `tests/test_api.py` (append)

- [ ] **Step 1: Append failing tests to `tests/test_api.py`**

```python
import time
from pathlib import Path


def test_download_endpoint_returns_job_id_and_completes(client, tmp_path):
    produced = tmp_path / "out.mp4"

    def fake_run_download(req, outdir, progress_hook, _writer=None):
        progress_hook({"status": "downloading", "downloaded_bytes": 5,
                       "total_bytes": 10})
        produced.write_text("data")
        return produced

    with patch("app.main.run_download", side_effect=fake_run_download):
        resp = client.post("/api/download", json={
            "url": "https://youtu.be/abc", "kind": "video", "resolution": 720,
        })
        assert resp.status_code == 200
        job_id = resp.json()["job_id"]
        assert job_id

        # Worker runs in a background thread; poll the job store briefly.
        from app.main import store
        for _ in range(50):
            job = store.get(job_id)
            if job and job.status in ("done", "error"):
                break
            time.sleep(0.02)
        assert store.get(job_id).status == "done"


def test_download_endpoint_records_error(client):
    def boom(req, outdir, progress_hook, _writer=None):
        raise RuntimeError("nope")

    with patch("app.main.run_download", side_effect=boom):
        resp = client.post("/api/download", json={
            "url": "https://youtu.be/abc", "kind": "audio", "bitrate": 192,
        })
        job_id = resp.json()["job_id"]
        from app.main import store
        for _ in range(50):
            job = store.get(job_id)
            if job and job.status in ("done", "error"):
                break
            time.sleep(0.02)
        job = store.get(job_id)
        assert job.status == "error"
        assert "nope" in job.error
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_api.py -k download_endpoint -v`
Expected: FAIL — 404 (route missing) / ImportError on `store`.

- [ ] **Step 3: Update `app/main.py` to add the job store, worker, and route**

Replace `app/main.py` with:
```python
import os
import threading

from fastapi import FastAPI, HTTPException

from app.config import settings
from app.downloader import extract_info, run_download
from app.jobs import JobStore
from app.models import DownloadRequest, InfoRequest, JobCreated, VideoInfo

app = FastAPI(title="YouTube Downloader")
store = JobStore()
_semaphore = threading.Semaphore(settings.MAX_CONCURRENT_DOWNLOADS)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/info", response_model=VideoInfo)
def info(req: InfoRequest):
    try:
        return extract_info(req.url)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


def _make_progress_hook(job_id: str):
    def hook(d: dict) -> None:
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            done = d.get("downloaded_bytes", 0)
            if total:
                store.update_progress(job_id, round(done / total * 100, 1))
    return hook


def _worker(job_id: str, req: DownloadRequest) -> None:
    outdir = os.path.join(settings.DOWNLOAD_DIR, job_id)
    with _semaphore:
        try:
            result = run_download(req, outdir, _make_progress_hook(job_id))
            store.set_done(job_id, filepath=str(result), filename=result.name)
        except Exception as exc:
            store.set_error(job_id, str(exc))


@app.post("/api/download", response_model=JobCreated)
def download(req: DownloadRequest):
    job_id = store.create()
    threading.Thread(target=_worker, args=(job_id, req), daemon=True).start()
    return JobCreated(job_id=job_id)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_api.py -k download_endpoint -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add app/main.py tests/test_api.py
git commit -m "feat: add /api/download endpoint with background worker"
```

---

## Task 9: `/api/progress/{job_id}` SSE endpoint

**Files:**
- Modify: `app/main.py`
- Test: `tests/test_api.py` (append)

- [ ] **Step 1: Append failing test to `tests/test_api.py`**

```python
def test_progress_stream_emits_status(client):
    job_id = store.create()
    store.update_progress(job_id, 50.0)
    store.set_done(job_id, filepath="/tmp/x.mp4", filename="x.mp4")

    with client.stream("GET", f"/api/progress/{job_id}") as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        body = ""
        for chunk in resp.iter_text():
            body += chunk
            if "done" in body:
                break
    assert "done" in body
    assert "x.mp4" in body


def test_progress_stream_missing_job_404(client):
    resp = client.get("/api/progress/doesnotexist")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_api.py -k progress_stream -v`
Expected: FAIL — 404 for both / route missing.

- [ ] **Step 3: Add SSE imports and route to `app/main.py`**

Add imports near the top:
```python
import asyncio
import json

from fastapi.responses import StreamingResponse
```

Add the route (after the `download` route):
```python
@app.get("/api/progress/{job_id}")
async def progress(job_id: str):
    if store.get(job_id) is None:
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_stream():
        while True:
            job = store.get(job_id)
            if job is None:
                break
            payload = {
                "status": job.status,
                "progress": job.progress,
                "filename": job.filename,
                "error": job.error,
            }
            yield f"data: {json.dumps(payload)}\n\n"
            if job.status in ("done", "error"):
                break
            await asyncio.sleep(0.5)

    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_api.py -k progress_stream -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add app/main.py tests/test_api.py
git commit -m "feat: add SSE progress stream endpoint"
```

---

## Task 10: `/api/file/{job_id}` download endpoint

**Files:**
- Modify: `app/main.py`
- Test: `tests/test_api.py` (append)

- [ ] **Step 1: Append failing tests to `tests/test_api.py`**

```python
def test_file_endpoint_serves_completed_file(client, tmp_path):
    f = tmp_path / "video.mp4"
    f.write_text("the-bytes")
    job_id = store.create()
    store.set_done(job_id, filepath=str(f), filename="video.mp4")

    resp = client.get(f"/api/file/{job_id}")
    assert resp.status_code == 200
    assert resp.content == b"the-bytes"
    assert "video.mp4" in resp.headers["content-disposition"]


def test_file_endpoint_404_when_not_done(client):
    job_id = store.create()  # still pending
    resp = client.get(f"/api/file/{job_id}")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_api.py -k file_endpoint -v`
Expected: FAIL — 404 (route missing) for the first test.

- [ ] **Step 3: Add the route to `app/main.py`**

Add import near the top:
```python
from fastapi.responses import FileResponse
```

Add the route:
```python
@app.get("/api/file/{job_id}")
def get_file(job_id: str):
    job = store.get(job_id)
    if job is None or job.status != "done" or not job.filepath:
        raise HTTPException(status_code=404, detail="File not ready")
    if not os.path.isfile(job.filepath):
        raise HTTPException(status_code=404, detail="File expired")
    return FileResponse(
        job.filepath,
        filename=job.filename,
        media_type="application/octet-stream",
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_api.py -k file_endpoint -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Run the whole test suite**

Run: `pytest -v`
Expected: PASS (all tests green)

- [ ] **Step 6: Commit**

```bash
git add app/main.py tests/test_api.py
git commit -m "feat: add file download endpoint"
```

---

## Task 11: TTL cleanup of old downloads

**Files:**
- Modify: `app/downloader.py` (add cleanup helper)
- Modify: `app/main.py` (background cleanup loop on startup)
- Test: `tests/test_downloader.py` (append)

- [ ] **Step 1: Append failing test to `tests/test_downloader.py`**

```python
import time as _time

from app.downloader import cleanup_expired


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_downloader.py -k cleanup -v`
Expected: FAIL — `ImportError: cannot import name 'cleanup_expired'`.

- [ ] **Step 3: Add `cleanup_expired` to `app/downloader.py`**

Add imports if missing:
```python
import shutil
import time
```

Add the function:
```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_downloader.py -k cleanup -v`
Expected: PASS

- [ ] **Step 5: Wire a periodic cleanup loop into `app/main.py`**

Add near the top:
```python
from app.downloader import cleanup_expired
```

Add a startup background loop (after `app = FastAPI(...)` and store/semaphore setup):
```python
@app.on_event("startup")
def start_cleanup_loop():
    def loop():
        while True:
            cleanup_expired(settings.DOWNLOAD_DIR, settings.FILE_TTL_SECONDS)
            time.sleep(600)  # every 10 minutes

    import time
    threading.Thread(target=loop, daemon=True).start()
```

- [ ] **Step 6: Run the full suite**

Run: `pytest -v`
Expected: PASS (all)

- [ ] **Step 7: Commit**

```bash
git add app/downloader.py app/main.py tests/test_downloader.py
git commit -m "feat: TTL cleanup of expired download dirs"
```

---

## Task 12: Frontend (HTML/CSS/JS) + static mount

**Files:**
- Create: `static/index.html`
- Create: `static/style.css`
- Create: `static/app.js`
- Modify: `app/main.py` (mount static + serve index at `/`)
- Test: `tests/test_api.py` (append a smoke test)

- [ ] **Step 1: Append failing smoke test to `tests/test_api.py`**

```python
def test_root_serves_html(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "YouTube Downloader" in resp.text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_api.py -k root_serves_html -v`
Expected: FAIL — 404 (no `/` route yet).

- [ ] **Step 3: Create `static/index.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>YouTube Downloader</title>
  <link rel="stylesheet" href="/static/style.css" />
</head>
<body>
  <main class="container">
    <h1>YouTube Downloader</h1>
    <form id="url-form">
      <input id="url" type="url" placeholder="Paste a YouTube URL" required />
      <button type="submit">Fetch</button>
    </form>

    <section id="info" class="hidden">
      <img id="thumb" alt="thumbnail" />
      <h2 id="title"></h2>
      <p id="meta"></p>

      <div class="options">
        <label><input type="radio" name="kind" value="video" checked /> Video (MP4)</label>
        <label><input type="radio" name="kind" value="audio" /> Audio</label>

        <div id="video-opts">
          <label>Resolution
            <select id="resolution"></select>
          </label>
        </div>

        <div id="audio-opts" class="hidden">
          <label>Format
            <select id="audio_format">
              <option value="mp3">MP3</option>
              <option value="m4a">M4A</option>
            </select>
          </label>
          <label>Bitrate
            <select id="bitrate">
              <option value="128">128 kbps</option>
              <option value="192" selected>192 kbps</option>
              <option value="256">256 kbps</option>
              <option value="320">320 kbps</option>
            </select>
          </label>
        </div>

        <label><input id="subtitles" type="checkbox" /> Include subtitles</label>
        <label id="sub-lang-wrap" class="hidden">Subtitle language
          <input id="sub_lang" type="text" value="en" size="4" />
        </label>
      </div>

      <button id="download-btn">Download</button>
    </section>

    <section id="progress-section" class="hidden">
      <div class="bar"><div id="bar-fill"></div></div>
      <p id="status-text"></p>
    </section>

    <p id="error" class="error hidden"></p>
  </main>
  <script src="/static/app.js"></script>
</body>
</html>
```

- [ ] **Step 4: Create `static/style.css`**

```css
:root { color-scheme: light dark; }
* { box-sizing: border-box; }
body {
  font-family: system-ui, sans-serif;
  margin: 0;
  padding: 2rem 1rem;
  background: #0f0f0f;
  color: #f1f1f1;
}
.container { max-width: 640px; margin: 0 auto; }
h1 { font-size: 1.6rem; }
form { display: flex; gap: .5rem; }
input[type="url"] { flex: 1; padding: .6rem; border-radius: 8px; border: 1px solid #444; background:#1c1c1c; color:#fff; }
button { padding: .6rem 1rem; border: 0; border-radius: 8px; background:#ff0033; color:#fff; cursor:pointer; }
button:disabled { opacity:.5; cursor: default; }
.hidden { display: none; }
#info { margin-top: 1.5rem; }
#thumb { max-width: 100%; border-radius: 12px; }
.options { display: flex; flex-direction: column; gap: .6rem; margin: 1rem 0; }
.bar { height: 14px; background:#333; border-radius: 999px; overflow: hidden; }
#bar-fill { height: 100%; width: 0%; background:#ff0033; transition: width .3s; }
.error { color:#ff6b6b; }
select, input[type="text"] { padding:.3rem; border-radius:6px; background:#1c1c1c; color:#fff; border:1px solid #444; }
```

- [ ] **Step 5: Create `static/app.js`**

```javascript
const $ = (id) => document.getElementById(id);

let currentInfo = null;

function show(el) { el.classList.remove("hidden"); }
function hide(el) { el.classList.add("hidden"); }

function showError(msg) {
  $("error").textContent = msg;
  show($("error"));
}

$("url-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  hide($("error"));
  hide($("info"));
  hide($("progress-section"));
  try {
    const resp = await fetch("/api/info", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: $("url").value }),
    });
    if (!resp.ok) throw new Error((await resp.json()).detail || "Failed to fetch info");
    currentInfo = await resp.json();
    renderInfo(currentInfo);
  } catch (err) {
    showError(err.message);
  }
});

function renderInfo(info) {
  $("title").textContent = info.title;
  if (info.thumbnail) { $("thumb").src = info.thumbnail; show($("thumb")); }
  $("meta").textContent = info.is_playlist
    ? `Playlist · ${info.entries_count} videos`
    : (info.duration ? `${Math.floor(info.duration / 60)}m ${info.duration % 60}s` : "");

  const res = $("resolution");
  res.innerHTML = "";
  const heights = info.available_heights.length ? info.available_heights : [1080, 720, 480];
  for (const h of heights) {
    const opt = document.createElement("option");
    opt.value = h; opt.textContent = `${h}p`;
    res.appendChild(opt);
  }
  show($("info"));
}

document.querySelectorAll('input[name="kind"]').forEach((r) =>
  r.addEventListener("change", () => {
    const isVideo = document.querySelector('input[name="kind"]:checked').value === "video";
    $("video-opts").classList.toggle("hidden", !isVideo);
    $("audio-opts").classList.toggle("hidden", isVideo);
  })
);

$("subtitles").addEventListener("change", (e) =>
  $("sub-lang-wrap").classList.toggle("hidden", !e.target.checked)
);

$("download-btn").addEventListener("click", async () => {
  hide($("error"));
  const kind = document.querySelector('input[name="kind"]:checked').value;
  const payload = {
    url: $("url").value,
    kind,
    resolution: kind === "video" ? parseInt($("resolution").value, 10) : null,
    bitrate: kind === "audio" ? parseInt($("bitrate").value, 10) : null,
    audio_format: $("audio_format").value,
    subtitles: $("subtitles").checked,
    sub_lang: $("sub_lang").value || "en",
  };
  try {
    const resp = await fetch("/api/download", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!resp.ok) throw new Error("Failed to start download");
    const { job_id } = await resp.json();
    trackProgress(job_id);
  } catch (err) {
    showError(err.message);
  }
});

function trackProgress(jobId) {
  show($("progress-section"));
  $("bar-fill").style.width = "0%";
  $("status-text").textContent = "Starting…";
  const es = new EventSource(`/api/progress/${jobId}`);
  es.onmessage = (e) => {
    const data = JSON.parse(e.data);
    if (data.status === "downloading") {
      $("bar-fill").style.width = `${data.progress}%`;
      $("status-text").textContent = `Downloading… ${data.progress}%`;
    } else if (data.status === "done") {
      $("bar-fill").style.width = "100%";
      $("status-text").textContent = "Done! Downloading file…";
      es.close();
      window.location.href = `/api/file/${jobId}`;
    } else if (data.status === "error") {
      es.close();
      showError(data.error || "Download failed");
      hide($("progress-section"));
    }
  };
  es.onerror = () => { es.close(); };
}
```

- [ ] **Step 6: Mount static files and serve index in `app/main.py`**

Add imports near the top:
```python
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
```

After the app is created, mount static and add the root route:
```python
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def index():
    return FileResponse("static/index.html")
```

- [ ] **Step 7: Run the smoke test**

Run: `pytest tests/test_api.py -k root_serves_html -v`
Expected: PASS

- [ ] **Step 8: Manual check — run the app and click through**

Run: `uvicorn app.main:app --reload`
Open `http://localhost:8000`, paste a real public YouTube URL, fetch info, pick options, download. Confirm progress bar fills and the file downloads.

- [ ] **Step 9: Commit**

```bash
git add static/ app/main.py tests/test_api.py
git commit -m "feat: add web UI and static serving"
```

---

## Task 13: Docker packaging + README

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Create: `.dockerignore`
- Create: `README.md`

- [ ] **Step 1: Create `Dockerfile`**

```dockerfile
FROM python:3.12-slim

# ffmpeg is required for muxing video+audio and extracting audio.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY static ./static

ENV DOWNLOAD_DIR=/tmp/ytdl-downloads
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Create `.dockerignore`**

```
tests/
docs/
superpowers/
__pycache__/
*.pyc
.venv/
.git/
requirements-dev.txt
```

- [ ] **Step 3: Create `docker-compose.yml`**

```yaml
services:
  youtube-downloader:
    build: .
    image: youtube-downloader
    ports:
      - "8000:8000"
    environment:
      - MAX_CONCURRENT_DOWNLOADS=3
      - FILE_TTL_SECONDS=3600
    restart: unless-stopped
```

- [ ] **Step 4: Create `README.md`**

```markdown
# YouTube Downloader

A self-hosted web app to download YouTube videos (MP4), audio (MP3/M4A),
whole playlists, and subtitles. Built with FastAPI + yt-dlp + ffmpeg.

> **Legal note:** Downloading content from YouTube may violate its Terms of
> Service. This project is intended for personal/self-hosted use with content
> you have the right to download (e.g. your own uploads or Creative Commons).
> You are responsible for how you operate your instance.

## Run with Docker

```bash
docker compose up --build
```

Then open http://localhost:8000

## Run locally (without Docker)

Requires Python 3.12 and ffmpeg installed.

```bash
pip install -r requirements.txt
uvicorn app.main:app --port 8000
```

## Configuration (env vars)

| Variable | Default | Meaning |
|---|---|---|
| `PORT` | 8000 | Port (when run via uvicorn directly) |
| `MAX_CONCURRENT_DOWNLOADS` | 3 | Simultaneous downloads |
| `FILE_TTL_SECONDS` | 3600 | How long finished files are kept |
| `DOWNLOAD_DIR` | /tmp/ytdl-downloads | Where temp files live |

## Development

```bash
pip install -r requirements-dev.txt
pytest -v
```

## Features

- Video (MP4) with selectable resolution
- Audio (MP3/M4A) with selectable bitrate (128/192/256/320 kbps)
- Whole playlists (delivered as a ZIP)
- Subtitles (.srt, delivered alongside in a ZIP)
- Real-time progress bar (SSE)

## Not in v1

- Age-restricted / login-required videos (cookies)
- User accounts, history, persistent storage
```

- [ ] **Step 5: Build and run the image to verify end-to-end**

Run: `docker compose up --build`
Open `http://localhost:8000`, download a public video, confirm it works inside the container (ffmpeg present, file delivered).

- [ ] **Step 6: Commit**

```bash
git add Dockerfile docker-compose.yml .dockerignore README.md
git commit -m "feat: Docker packaging and README"
```

---

## Self-Review (completed by plan author)

**1. Spec coverage:**
- Web app, simple UI, browser-only for visitors → Tasks 12 (UI), 1–11 (server). ✓
- Self-hosted, Docker one command → Task 13. ✓
- Stack Python + FastAPI + yt-dlp library + lightweight frontend → Tasks 1, 4–12. ✓
- Video MP4 selectable resolution → Tasks 4, 12. ✓
- Audio MP3/M4A selectable bitrate → Tasks 4, 12. ✓
- Playlists (no cap), delivered as ZIP → Task 6. ✓
- Subtitles as .srt in ZIP → Tasks 4 (opts), 6 (zip). ✓
- Real-time progress via SSE → Tasks 8 (hook), 9 (SSE), 12 (bar). ✓
- Error handling (invalid/private/login) → Tasks 7, 8 surface messages. ✓
- Concurrency semaphore → Task 8. ✓
- Temp dir + TTL cleanup → Task 11. ✓
- English UI → Task 12. ✓
- Login/cookies out of v1 → documented in README (Task 13). ✓

**2. Placeholder scan:** No TBD/TODO. Every code step includes complete code. ✓

**3. Type consistency:** `DownloadRequest` fields (`kind`, `resolution`, `bitrate`,
`audio_format`, `subtitles`, `sub_lang`) are used consistently across Tasks 2, 4, 8, 12.
`JobStore` methods (`create`, `get`, `update_progress`, `set_done`, `set_error`) match
between Tasks 3 and 8. `run_download` / `extract_info` / `build_ydl_opts` signatures
match between Tasks 4–6 and their callers in Tasks 7–8. ✓
