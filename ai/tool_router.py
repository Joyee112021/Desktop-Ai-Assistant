from __future__ import annotations

from dataclasses import dataclass, field

from utils.document_memory import DocumentMemoryStore
from utils.logging_utils import get_logger
from utils.script_runner import extract_python_request, run_python_snippet


LOGGER = get_logger(__name__)

LIVE_INFO_HINTS = (
    "today",
    "latest",
    "current",
    "recent",
    "news",
    "price",
    "weather",
    "score",
    "release",
    "version",
    "download",
    "documentation",
    "update",
    "github",
    "2025",
    "2026",
    "今天",
    "最新",
    "現在",
    "目前",
    "近期",
    "新闻",
    "新聞",
    "价格",
    "價格",
    "版本",
    "更新",
    "下载",
    "下載",
)


@dataclass(frozen=True)
class ToolPreparation:
    """Tool-routing result to merge into the next user prompt."""

    prompt_context: str = ""
    labels: tuple[str, ...] = field(default_factory=tuple)
    search_query: str | None = None


class ToolRouter:
    """Decide when to use long-term memory, Python tools, or live web search."""

    def __init__(self, memory_store: DocumentMemoryStore):
        self.memory_store = memory_store

    def prepare(self, query: str, allow_search: bool = True) -> ToolPreparation:
        """Analyze the query and return extra prompt context plus tool intents."""
        context_blocks: list[str] = []
        labels: list[str] = []
        search_query: str | None = None

        memory_hits = self.memory_store.search(query)
        if memory_hits:
            context_blocks.append(self.memory_store.format_hits(memory_hits))
            labels.append("memory")

        python_code = extract_python_request(query)
        if python_code:
            result = run_python_snippet(python_code)
            context_blocks.append(
                "Python helper output:\n"
                f"Command: {result.command_label}\n"
                f"Success: {'yes' if result.success else 'no'}\n"
                f"{result.output}"
            )
            labels.append("python")

        if allow_search and self.should_search(query):
            search_query = query
            labels.append("search")

        LOGGER.debug(
            "Tool routing prepared labels=%s search=%s for query=%s",
            labels,
            bool(search_query),
            query,
        )
        return ToolPreparation(
            prompt_context="\n\n".join(block for block in context_blocks if block).strip(),
            labels=tuple(labels),
            search_query=search_query,
        )

    @staticmethod
    def should_search(query: str) -> bool:
        """Return whether the question likely needs fresh web data."""
        lowered = query.strip().lower()
        if len(lowered) < 8:
            return False
        return any(hint in lowered for hint in LIVE_INFO_HINTS)
