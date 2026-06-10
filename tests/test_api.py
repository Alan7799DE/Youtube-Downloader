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
