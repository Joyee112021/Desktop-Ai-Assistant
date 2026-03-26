from pathlib import Path
from typing import Callable
from urllib.request import Request, urlopen


def format_size_gb(size_gb: float) -> str:
    return f"{size_gb:.1f} GB"


def download_to_path(
    url: str,
    target_path: Path,
    progress_callback: Callable[[int, int], None] | None = None,
    chunk_size: int = 1024 * 1024,
) -> Path:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = target_path.with_suffix(target_path.suffix + ".part")

    request = Request(url, headers={"User-Agent": "Desktop-AI-Assistant-CPU/1.0"})

    with urlopen(request, timeout=60) as response, temp_path.open("wb") as handle:
        total_bytes = int(response.headers.get("Content-Length", "0") or 0)
        downloaded_bytes = 0

        while True:
            chunk = response.read(chunk_size)
            if not chunk:
                break

            handle.write(chunk)
            downloaded_bytes += len(chunk)

            if progress_callback is not None:
                progress_callback(downloaded_bytes, total_bytes)

    temp_path.replace(target_path)
    return target_path
