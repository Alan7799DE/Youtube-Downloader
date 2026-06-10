# YouTube Downloader

[![Tests](https://github.com/Alan7799DE/youtube-downloader/actions/workflows/tests.yml/badge.svg)](https://github.com/Alan7799DE/youtube-downloader/actions/workflows/tests.yml)

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
