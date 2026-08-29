from pathlib import Path


def cache_dir() -> Path:
    path = Path.home() / ".cache" / "labelprint"
    path.mkdir(parents=True, exist_ok=True)
    return path


def default_preview_path() -> Path:
    return cache_dir() / "preview.png"


def default_job_path() -> Path:
    return cache_dir() / "job.png"
