from __future__ import annotations

import re
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from pypdf import PdfReader

from config.settings import DEFAULT_RAG_CHUNK_OVERLAP, DEFAULT_RAG_CHUNK_SIZE, DEFAULT_RAG_RESULTS, MEMORY_DB_PATH
from utils.logging_utils import get_logger


LOGGER = get_logger(__name__)
SUPPORTED_DOCUMENT_SUFFIXES = {".txt", ".md", ".log", ".json", ".yaml", ".yml", ".toml", ".csv", ".py", ".pdf"}


@dataclass(frozen=True)
class MemoryHit:
    """A retrieved knowledge chunk from the local long-term memory store."""

    source_name: str
    source_path: str
    snippet: str
    score: float


class DocumentMemoryStore:
    """A lightweight local knowledge store backed by SQLite FTS for document RAG."""

    def __init__(self, db_path: Path = MEMORY_DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _ensure_schema(self) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    source_path TEXT PRIMARY KEY,
                    source_name TEXT NOT NULL,
                    mtime REAL NOT NULL,
                    file_size INTEGER NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS memory_chunks USING fts5(
                    source_path UNINDEXED,
                    source_name UNINDEXED,
                    chunk_index UNINDEXED,
                    content
                )
                """
            )
            connection.commit()

    def supports(self, path: Path) -> bool:
        """Return whether the provided file can be indexed into the memory store."""
        return path.suffix.lower() in SUPPORTED_DOCUMENT_SUFFIXES

    def index_path(self, path: Path) -> int:
        """Index a supported local document and return the number of stored chunks."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(path)
        if not self.supports(path):
            raise ValueError(f"Unsupported document type: {path.suffix}")

        text = self._read_document(path)
        chunks = list(_chunk_text(text, DEFAULT_RAG_CHUNK_SIZE, DEFAULT_RAG_CHUNK_OVERLAP))
        stat = path.stat()

        with closing(self._connect()) as connection:
            connection.execute("DELETE FROM memory_chunks WHERE source_path = ?", (str(path),))
            connection.execute(
                """
                INSERT INTO documents (source_path, source_name, mtime, file_size)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(source_path) DO UPDATE SET
                    source_name = excluded.source_name,
                    mtime = excluded.mtime,
                    file_size = excluded.file_size
                """,
                (str(path), path.name, stat.st_mtime, stat.st_size),
            )
            connection.executemany(
                """
                INSERT INTO memory_chunks (source_path, source_name, chunk_index, content)
                VALUES (?, ?, ?, ?)
                """,
                [(str(path), path.name, index, chunk) for index, chunk in enumerate(chunks)],
            )
            connection.commit()

        LOGGER.info("Indexed %s chunk(s) from %s into local memory.", len(chunks), path)
        return len(chunks)

    def search(self, query: str, limit: int = DEFAULT_RAG_RESULTS) -> list[MemoryHit]:
        """Retrieve the most relevant local memory chunks for the current query."""
        cleaned_query = _normalize_query(query)
        if not cleaned_query:
            return []

        with closing(self._connect()) as connection:
            try:
                rows = connection.execute(
                    """
                    SELECT
                        source_name,
                        source_path,
                        content,
                        bm25(memory_chunks) AS score
                    FROM memory_chunks
                    WHERE memory_chunks MATCH ?
                    ORDER BY score
                    LIMIT ?
                    """,
                    (cleaned_query, limit),
                ).fetchall()
            except sqlite3.OperationalError:
                rows = []

            if not rows:
                rows = connection.execute(
                    """
                    SELECT source_name, source_path, content
                    FROM memory_chunks
                    LIMIT 300
                    """
                ).fetchall()
                return _fallback_rank(query, rows, limit)

        hits = [
            MemoryHit(
                source_name=row["source_name"],
                source_path=row["source_path"],
                snippet=_trim_snippet(row["content"]),
                score=float(-row["score"]),
            )
            for row in rows
        ]
        LOGGER.debug("Local memory search for '%s' returned %s hit(s).", query, len(hits))
        return hits

    def format_hits(self, hits: Iterable[MemoryHit]) -> str:
        """Render retrieved memory snippets into prompt-friendly context text."""
        hits = list(hits)
        if not hits:
            return ""

        lines = ["Local knowledge base context:"]
        for index, hit in enumerate(hits, start=1):
            lines.append(f"{index}. {hit.source_name}")
            lines.append(f"   Path: {hit.source_path}")
            lines.append(f"   Snippet: {hit.snippet}")
        return "\n".join(lines)

    def _read_document(self, path: Path) -> str:
        if path.suffix.lower() == ".pdf":
            reader = PdfReader(str(path))
            text = "\n".join((page.extract_text() or "").strip() for page in reader.pages)
        else:
            text = path.read_text(encoding="utf-8", errors="ignore")

        normalized = re.sub(r"\s+\n", "\n", text).strip()
        if not normalized:
            raise ValueError(f"No readable text was found in {path.name}")
        return normalized


def _chunk_text(text: str, chunk_size: int, overlap: int) -> Iterable[str]:
    cleaned = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not cleaned:
        return []

    chunks: list[str] = []
    cursor = 0
    text_length = len(cleaned)
    while cursor < text_length:
        end = min(text_length, cursor + chunk_size)
        chunk = cleaned[cursor:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= text_length:
            break
        cursor = max(end - overlap, cursor + 1)
    return chunks


def _normalize_query(query: str) -> str:
    tokens = re.findall(r"[A-Za-z0-9_\-\u4e00-\u9fff]{2,}", query.lower())
    return " OR ".join(tokens[:10])


def _trim_snippet(content: str, max_chars: int = 280) -> str:
    content = re.sub(r"\s+", " ", content).strip()
    if len(content) <= max_chars:
        return content
    return content[: max_chars - 3].rstrip() + "..."


def _fallback_rank(query: str, rows: Iterable[sqlite3.Row], limit: int) -> list[MemoryHit]:
    tokens = set(re.findall(r"[A-Za-z0-9_\-\u4e00-\u9fff]{2,}", query.lower()))
    scored: list[MemoryHit] = []
    for row in rows:
        content = str(row["content"])
        lowered = content.lower()
        overlap = sum(1 for token in tokens if token in lowered)
        if overlap <= 0:
            continue
        scored.append(
            MemoryHit(
                source_name=row["source_name"],
                source_path=row["source_path"],
                snippet=_trim_snippet(content),
                score=float(overlap),
            )
        )

    scored.sort(key=lambda item: item.score, reverse=True)
    return scored[:limit]
