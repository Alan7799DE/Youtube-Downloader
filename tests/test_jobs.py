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
