from __future__ import annotations

import base64
import tempfile
import time
from pathlib import Path

from PySide6.QtWidgets import QApplication
from pypdf import PdfReader


TEXT_FILE_SUFFIXES = {
    ".txt",
    ".md",
    ".py",
    ".json",
    ".yaml",
    ".yml",
    ".csv",
    ".log",
    ".ini",
    ".toml",
    ".html",
    ".css",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".xml",
}
DOCUMENT_FILE_SUFFIXES = TEXT_FILE_SUFFIXES | {".pdf"}


def is_text_file(path: Path) -> bool:
    return path.suffix.lower() in TEXT_FILE_SUFFIXES


def is_document_file(path: Path) -> bool:
    return path.suffix.lower() in DOCUMENT_FILE_SUFFIXES


def read_text_file_context(path: Path, max_chars: int = 12000) -> str:
    content = read_document_text(path)
    content = content[:max_chars]
    return f"Attached file: {path.name}\n\n{content}"


def read_document_text(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        reader = PdfReader(str(path))
        return "\n".join((page.extract_text() or "").strip() for page in reader.pages).strip()
    return path.read_text(encoding="utf-8", errors="ignore")


def image_file_to_data_url(path: Path) -> str:
    mime = "image/png"
    if path.suffix.lower() in {".jpg", ".jpeg"}:
        mime = "image/jpeg"
    elif path.suffix.lower() == ".webp":
        mime = "image/webp"

    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def capture_desktop_screenshot() -> Path:
    app = QApplication.instance()
    if app is None:
        raise RuntimeError("Desktop capture requires a running QApplication instance.")

    screen = app.primaryScreen()
    if screen is None:
        raise RuntimeError("No screen is available for desktop capture.")

    screenshot_dir = Path(tempfile.gettempdir()) / "desktop_ai_assistant"
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    screenshot_path = screenshot_dir / f"desktop_capture_{time.strftime('%Y%m%d_%H%M%S')}.png"

    pixmap = screen.grabWindow(0)
    if pixmap.isNull() or not pixmap.save(str(screenshot_path), "PNG"):
        raise RuntimeError("Could not capture the desktop screenshot.")

    return screenshot_path
