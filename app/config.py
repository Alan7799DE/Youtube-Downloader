import os


class Settings:
    MAX_CONCURRENT_DOWNLOADS: int = int(os.getenv("MAX_CONCURRENT_DOWNLOADS", "3"))
    FILE_TTL_SECONDS: int = int(os.getenv("FILE_TTL_SECONDS", "3600"))
    DOWNLOAD_DIR: str = os.getenv("DOWNLOAD_DIR", "/tmp/ytdl-downloads")


settings = Settings()
