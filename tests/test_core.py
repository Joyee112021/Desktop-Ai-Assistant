import tempfile
import unittest
from pathlib import Path

from ai.inference import InferenceEngine
from ai.prompt_template import ChatMemory, render_prompt_from_messages
from ai.tool_router import ToolRouter
from config.localization import hardware_label, model_copy, profile_label, tr
from config.user_settings import (
    UserSettings,
    backend_model_issue,
    build_runtime_config,
    find_model_option,
    load_model_catalog,
    normalize_settings,
)
from utils.document_memory import DocumentMemoryStore


class FakeLLM:
    def __init__(self, chat_chunks=None, completion_chunks=None, raise_on_chat=False):
        self.chat_chunks = chat_chunks or []
        self.completion_chunks = completion_chunks or []
        self.raise_on_chat = raise_on_chat
        self.calls = []

    def create_chat_completion(self, **kwargs):
        self.calls.append(("chat", kwargs))
        if self.raise_on_chat:
            raise RuntimeError("missing chat template")
        return iter(self.chat_chunks)

    def create_completion(self, **kwargs):
        self.calls.append(("completion", kwargs))
        return iter(self.completion_chunks)


class ChatMemoryTests(unittest.TestCase):
    def test_memory_keeps_system_prompt_and_trims_history(self):
        memory = ChatMemory(system_prompt="system", max_history_messages=4)
        memory.add_user_message("u1")
        memory.add_assistant_message("a1")
        memory.add_user_message("u2")
        memory.add_assistant_message("a2")
        memory.add_user_message("u3")

        context = memory.get_context()

        self.assertEqual(context[0], {"role": "system", "content": "system"})
        self.assertEqual(
            context[1:],
            [
                {"role": "assistant", "content": "a1"},
                {"role": "user", "content": "u2"},
                {"role": "assistant", "content": "a2"},
                {"role": "user", "content": "u3"},
            ],
        )

    def test_last_assistant_message_returns_latest(self):
        memory = ChatMemory(system_prompt="system")
        memory.add_user_message("hello")
        memory.add_assistant_message("latest")

        self.assertEqual(memory.last_assistant_message(), "latest")

    def test_prompt_renderer_creates_simple_fallback_prompt(self):
        prompt = render_prompt_from_messages(
            [
                {"role": "system", "content": "system"},
                {"role": "user", "content": "hello"},
            ]
        )
        self.assertIn("System:\nsystem", prompt)
        self.assertIn("User:\nhello", prompt)
        self.assertTrue(prompt.endswith("Assistant:\n"))

    def test_prompt_renderer_flattens_image_messages(self):
        prompt = render_prompt_from_messages(
            [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Describe this"},
                        {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}},
                    ],
                }
            ]
        )

        self.assertIn("Describe this", prompt)
        self.assertIn("[Image attached]", prompt)


class SettingsTests(unittest.TestCase):
    def test_normalize_settings_picks_a_valid_model(self):
        catalog = load_model_catalog()
        settings = normalize_settings(UserSettings(selected_model_id=""), catalog)
        model_ids = [option.id for option in catalog]

        self.assertIn(settings.selected_model_id, model_ids)

    def test_build_runtime_config_uses_profile_defaults(self):
        catalog = load_model_catalog()
        settings = normalize_settings(UserSettings(profile_id="normal"), catalog)
        runtime = build_runtime_config(settings, catalog)

        self.assertEqual(runtime.profile_label, "Normal")
        self.assertGreaterEqual(runtime.n_threads, 1)
        self.assertGreaterEqual(runtime.n_ctx, 2048)
        self.assertTrue(str(runtime.model_path).endswith(".gguf"))

    def test_build_runtime_config_uses_custom_values(self):
        catalog = load_model_catalog()
        settings = normalize_settings(
            UserSettings(
                profile_id="custom",
                n_threads=7,
                n_ctx=3584,
                n_batch=640,
                max_tokens=320,
            ),
            catalog,
        )
        runtime = build_runtime_config(settings, catalog)

        self.assertEqual(runtime.profile_label, "Custom")
        self.assertEqual(runtime.n_threads, 7)
        self.assertEqual(runtime.n_ctx, 3584)
        self.assertEqual(runtime.n_batch, 640)
        self.assertEqual(runtime.max_tokens, 320)

    def test_normalize_settings_keeps_interface_language(self):
        catalog = load_model_catalog()
        settings = normalize_settings(UserSettings(interface_language="zh-TW"), catalog)
        self.assertEqual(settings.interface_language, "zh-TW")

    def test_localization_helpers_return_natural_chinese_labels(self):
        self.assertEqual(profile_label("normal", "zh-TW"), "標準")
        self.assertEqual(profile_label("custom", "zh-CN"), "自定义")
        self.assertEqual(hardware_label("intel", "zh-TW"), "Intel 內顯")
        self.assertEqual(tr("app_settings", "zh-CN"), "设置")
        self.assertIn("最推薦", model_copy("llama-3.1-8b-q4km", "summary", "", "zh-TW"))

    def test_normalize_settings_skips_backend_incompatible_model(self):
        catalog = load_model_catalog()
        incompatible = find_model_option("mistral-nemo-12b-q4km", catalog)
        self.assertIsNotNone(incompatible)
        self.assertIsNotNone(backend_model_issue(incompatible))

        settings = normalize_settings(UserSettings(selected_model_id="mistral-nemo-12b-q4km"), catalog)

        self.assertNotEqual(settings.selected_model_id, "mistral-nemo-12b-q4km")

    def test_document_memory_store_indexes_and_retrieves_text(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            db_path = temp_path / "memory.sqlite3"
            doc_path = temp_path / "notes.md"
            doc_path.write_text("The RTX 5090 is a future GPU reference used in roadmap planning.", encoding="utf-8")

            store = DocumentMemoryStore(db_path)
            chunks = store.index_path(doc_path)
            hits = store.search("What does the roadmap mention about RTX 5090?", limit=2)

            self.assertGreaterEqual(chunks, 1)
            self.assertTrue(hits)
            self.assertIn("RTX 5090", hits[0].snippet)

    def test_tool_router_runs_explicit_python_requests(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = DocumentMemoryStore(Path(temp_dir) / "memory.sqlite3")
            router = ToolRouter(store)

            result = router.prepare("/python print(6 * 7)", allow_search=False)

            self.assertIn("Python helper output", result.prompt_context)
            self.assertIn("42", result.prompt_context)
            self.assertIn("python", result.labels)


class InferenceEngineTests(unittest.TestCase):
    def _runtime_config(self):
        catalog = load_model_catalog()
        settings = normalize_settings(UserSettings(), catalog)
        return build_runtime_config(settings, catalog)

    def test_generate_stream_extracts_delta_tokens(self):
        engine = InferenceEngine(self._runtime_config())
        engine.llm = FakeLLM(
            chat_chunks=[
                {"choices": [{"delta": {"content": "hello"}}]},
                {"choices": [{"delta": {"content": " world"}}]},
            ]
        )

        tokens = list(engine.generate_stream([{"role": "user", "content": "hi"}]))

        self.assertEqual(tokens, ["hello", " world"])

    def test_generate_stream_falls_back_to_prompt_completion(self):
        engine = InferenceEngine(self._runtime_config())
        engine.llm = FakeLLM(
            completion_chunks=[{"choices": [{"text": "plain text"}]}],
            raise_on_chat=True,
        )

        tokens = list(engine.generate_stream([{"role": "user", "content": "test"}]))

        self.assertEqual(tokens, ["plain text"])
        self.assertEqual(engine.llm.calls[0][0], "chat")
        self.assertEqual(engine.llm.calls[1][0], "completion")

    def test_request_stop_sets_stopped_flag(self):
        engine = InferenceEngine(self._runtime_config())
        engine.llm = FakeLLM(
            chat_chunks=[
                {"choices": [{"delta": {"content": "a"}}]},
                {"choices": [{"delta": {"content": "b"}}]},
            ]
        )

        iterator = engine.generate_stream([{"role": "user", "content": "stop"}])
        first = next(iterator)
        engine.request_stop()
        remaining = list(iterator)

        self.assertEqual(first, "a")
        self.assertEqual(remaining, [])
        self.assertTrue(engine.was_stopped)


if __name__ == "__main__":
    unittest.main()
