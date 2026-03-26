import ssl
import time
from pathlib import Path
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    import certifi
except ImportError:  # pragma: no cover - optional fallback for source-only environments
    certifi = None


def format_size_gb(size_gb: float) -> str:
    return f"{size_gb:.1f} GB"


def _download_context() -> ssl.SSLContext:
    if certifi is not None:
        return ssl.create_default_context(cafile=certifi.where())
    return ssl.create_default_context()


def _friendly_error_message(url: str, exc: Exception) -> str:
    if isinstance(exc, HTTPError):
        return f"HTTP {exc.code} while downloading from Hugging Face."
    if isinstance(exc, ssl.SSLError):
        return "SSL verification failed while connecting to Hugging Face."
    if isinstance(exc, TimeoutError):
        return "The download timed out while waiting for Hugging Face."
    if isinstance(exc, URLError):
        reason = exc.reason
        if isinstance(reason, ssl.SSLError):
            return "SSL verification failed while connecting to Hugging Face."
        if isinstance(reason, TimeoutError):
            return "The download timed out while waiting for Hugging Face."
        return f"Could not reach Hugging Face: {reason}"
    if isinstance(exc, OSError):
        return f"Could not save the model file: {exc.strerror or exc}"
    return f"Unexpected download error for {url}: {exc}"


def download_to_path(
    url: str,
    target_path: Path,
    progress_callback: Callable[[int, int], None] | None = None,
    chunk_size: int = 1024 * 1024,
    max_retries: int = 3,
) -> Path:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = target_path.with_suffix(target_path.suffix + ".part")
    ssl_context = _download_context()

    headers = {
        "User-Agent": "Desktop-AI-Assistant-CPU/1.1",
        "Accept": "application/octet-stream",
    }

    last_error: Exception | None = None

    for attempt in range(1, max_retries + 1):
        if temp_path.exists():
            temp_path.unlink()

        request = Request(url, headers=headers)

        try:
            with urlopen(request, timeout=60, context=ssl_context) as response, temp_path.open("wb") as handle:
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
        except (HTTPError, URLError, TimeoutError, ssl.SSLError, OSError) as exc:
            last_error = exc
            if temp_path.exists():
                temp_path.unlink()
            if attempt < max_retries:
                time.sleep(min(3.0, 0.8 * attempt))
                continue
            raise RuntimeError(_friendly_error_message(url, exc)) from exc

    if last_error is not None:  # pragma: no cover - defensive fallback
        raise RuntimeError(_friendly_error_message(url, last_error)) from last_error
    raise RuntimeError(f"Unexpected download failure for {target_path.name}.")
