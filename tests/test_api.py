def test_health_returns_ok(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


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


from app.main import store


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
