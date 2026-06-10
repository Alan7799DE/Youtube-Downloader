import asyncio
import json
import os
import threading
import time

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.downloader import cleanup_expired, extract_info, run_download
from app.jobs import JobStore
from app.models import DownloadRequest, InfoRequest, JobCreated, VideoInfo

app = FastAPI(title="YouTube Downloader")
app.mount("/static", StaticFiles(directory="static"), name="static")
store = JobStore()
_semaphore = threading.Semaphore(settings.MAX_CONCURRENT_DOWNLOADS)


@app.get("/")
def index():
    return FileResponse("static/index.html")


@app.on_event("startup")
def start_cleanup_loop():
    def loop():
        while True:
            cleanup_expired(settings.DOWNLOAD_DIR, settings.FILE_TTL_SECONDS)
            time.sleep(600)  # every 10 minutes

    threading.Thread(target=loop, daemon=True).start()


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/info", response_model=VideoInfo)
def info(req: InfoRequest):
    try:
        return extract_info(req.url)
    except Exception as exc:  # surface a clean message to the UI
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
