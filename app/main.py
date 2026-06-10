from fastapi import FastAPI

app = FastAPI(title="YouTube Downloader")


@app.get("/api/health")
def health():
    return {"status": "ok"}
