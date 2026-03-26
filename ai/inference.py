from typing import Any, Iterable, Mapping

from ai.model_loader import ModelLoader
from ai.prompt_template import render_prompt_from_messages
from config.user_settings import RuntimeConfig
from utils.logging_utils import get_logger


class InferenceEngine:
    """Thin wrapper around llama.cpp chat and completion streaming APIs."""

    def __init__(self, runtime_config: RuntimeConfig):
        self.loader = ModelLoader()
        self.runtime_config = runtime_config
        self.llm = None
        self._stop_requested = False
        self._was_stopped = False
        self._logger = get_logger(__name__)

    @property
    def was_stopped(self) -> bool:
        return self._was_stopped

    def set_runtime_config(self, runtime_config: RuntimeConfig):
        self.runtime_config = runtime_config
        self.llm = None

    def initialize(self):
        """Initialize the active llama.cpp model if needed."""
        if self.llm is None:
            self._logger.debug("Initializing inference model for %s.", self.runtime_config.model.name)
            self.llm = self.loader.load_model(self.runtime_config)
        return self.llm

    def request_stop(self):
        self._stop_requested = True

    def reset_stop(self):
        self._stop_requested = False
        self._was_stopped = False

    def generate_stream(self, messages: Iterable[Mapping[str, Any]]):
        """Yield model tokens using chat completion with prompt fallback."""
        llm = self.initialize()
        self.reset_stop()
        message_list = list(messages)
        chat_error = None

        try:
            self._logger.debug("Starting chat completion stream with %s messages.", len(message_list))
            stream = llm.create_chat_completion(
                messages=message_list,
                max_tokens=self.runtime_config.max_tokens,
                temperature=self.runtime_config.temperature,
                top_p=self.runtime_config.top_p,
                repeat_penalty=self.runtime_config.repeat_penalty,
                stream=True,
            )
            yield from self._yield_tokens(stream)
            return
        except Exception as exc:
            chat_error = exc
            self._logger.warning("Chat completion failed; falling back to prompt completion: %s", exc)

        try:
            prompt = render_prompt_from_messages(message_list)
            self._logger.debug("Starting prompt completion fallback.")
            stream = llm.create_completion(
                prompt=prompt,
                max_tokens=self.runtime_config.max_tokens,
                temperature=self.runtime_config.temperature,
                top_p=self.runtime_config.top_p,
                repeat_penalty=self.runtime_config.repeat_penalty,
                stream=True,
            )
            yield from self._yield_tokens(stream)
        except Exception as exc:
            if chat_error is not None:
                raise RuntimeError(
                    "Model inference failed. "
                    f"Chat completion error: {chat_error}. "
                    f"Prompt fallback error: {exc}"
                ) from exc
            raise RuntimeError(f"Model inference failed: {exc}") from exc

    def _yield_tokens(self, stream):
        for chunk in stream:
            if self._stop_requested:
                self._was_stopped = True
                self._logger.info("Inference stream stopped by user request.")
                break

            token = self._extract_token(chunk)
            if token:
                yield token

    @staticmethod
    def _extract_token(chunk) -> str:
        choices = chunk.get("choices") or []
        if not choices:
            return ""

        choice = choices[0]
        delta = choice.get("delta") or {}
        token = delta.get("content")

        if isinstance(token, str) and token:
            return token

        text = choice.get("text")
        if isinstance(text, str) and text:
            return text

        message = choice.get("message") or {}
        content = message.get("content")
        if isinstance(content, str) and content:
            return content

        return ""
