from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

from config.localization import build_system_prompt
from config.settings import DEFAULT_RESPONSE_LANGUAGE


Message = Dict[str, Any]


def _flatten_content(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        segments: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "text":
                segments.append(str(item.get("text", "")).strip())
            elif item.get("type") == "image_url":
                segments.append("[Image attached]")
        return "\n".join(segment for segment in segments if segment)

    return str(content).strip()


def render_prompt_from_messages(messages: Iterable[Message]) -> str:
    lines: list[str] = []

    for message in messages:
        role = message.get("role", "user").strip().lower()
        content = _flatten_content(message.get("content", ""))
        if not content:
            continue

        if role == "system":
            lines.append(f"System:\n{content}")
        elif role == "assistant":
            lines.append(f"Assistant:\n{content}")
        else:
            lines.append(f"User:\n{content}")

    lines.append("Assistant:\n")
    return "\n\n".join(lines)


@dataclass
class ChatMemory:
    system_prompt: str = build_system_prompt(DEFAULT_RESPONSE_LANGUAGE)
    max_history_messages: int = 12
    messages: List[Message] = field(default_factory=list)

    def __post_init__(self):
        if not self.messages:
            self.clear()

    def add_user_message(self, content: Any):
        normalized = _normalize_content(content)
        if normalized:
            self.messages.append({"role": "user", "content": normalized})
            self._trim_history()

    def add_assistant_message(self, text: str):
        text = text.strip()
        if text:
            self.messages.append({"role": "assistant", "content": text})
            self._trim_history()

    def clear(self):
        self.messages = [{"role": "system", "content": self.system_prompt}]

    def get_context(self) -> List[Message]:
        return list(self.messages)

    def last_assistant_message(self) -> Optional[str]:
        for message in reversed(self.messages):
            if message.get("role") == "assistant":
                return message.get("content", "")
        return None

    def _trim_history(self):
        if self.max_history_messages <= 0:
            return

        system_message = self.messages[:1]
        history = self.messages[1:]

        if len(history) > self.max_history_messages:
            history = history[-self.max_history_messages :]

        self.messages = system_message + history


def _normalize_content(content: Any) -> Any:
    if isinstance(content, str):
        content = content.strip()
        return content if content else None

    if isinstance(content, list):
        return content if content else None

    return content
