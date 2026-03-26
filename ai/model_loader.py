import gc
from pathlib import Path

from llama_cpp import Llama
from llama_cpp.llama_chat_format import Llava15ChatHandler

from config.user_settings import RuntimeConfig
from utils.logging_utils import get_logger


class ModelLoader:
    """Singleton loader that reuses a compatible llama.cpp model instance."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._model = None
            cls._instance._signature = None
            cls._instance._logger = get_logger(__name__)
        return cls._instance

    def load_model(self, runtime_config: RuntimeConfig):
        """Load or reuse the currently selected GGUF model."""
        if self._model is not None and self._signature == runtime_config.loader_signature:
            self._logger.debug("Reusing cached model instance for %s.", runtime_config.model.name)
            return self._model

        model_path = Path(runtime_config.model_path)
        if not model_path.exists():
            expected_names = ", ".join(runtime_config.model.candidate_files)
            raise FileNotFoundError(
                "The selected model is not installed.\n"
                f"Expected one of these files in the models folder: {expected_names}\n"
                f"Resolved path: {model_path}\n"
                f"Download source: https://huggingface.co/{runtime_config.model.repo}"
            )

        self.reset()
        chat_handler = None
        logits_all = False
        if runtime_config.model.supports("vision"):
            if not runtime_config.auxiliary_paths:
                raise FileNotFoundError("The selected vision model is missing its mmproj support file.")
            mmproj_path = runtime_config.auxiliary_paths[0]
            if not mmproj_path.exists():
                raise FileNotFoundError(f"Missing vision support file: {mmproj_path}")
            chat_handler = Llava15ChatHandler(clip_model_path=str(mmproj_path), verbose=False)
            logits_all = True

        self._logger.info(
            "Loading model %s with n_ctx=%s, n_threads=%s, n_batch=%s, gpu_layers=%s.",
            runtime_config.model.name,
            runtime_config.n_ctx,
            runtime_config.n_threads,
            runtime_config.n_batch,
            runtime_config.n_gpu_layers,
        )
        self._model = Llama(
            model_path=str(model_path),
            n_ctx=runtime_config.n_ctx,
            n_batch=runtime_config.n_batch,
            n_threads=runtime_config.n_threads,
            n_threads_batch=runtime_config.n_threads,
            n_gpu_layers=runtime_config.n_gpu_layers,
            use_mmap=runtime_config.use_mmap,
            chat_handler=chat_handler,
            logits_all=logits_all,
            verbose=False,
        )
        self._signature = runtime_config.loader_signature
        return self._model

    def reset(self):
        """Release the current model instance and reclaim memory."""
        if self._model is None:
            self._signature = None
            return

        try:
            close_method = getattr(self._model, "close", None)
            if callable(close_method):
                close_method()
        except Exception:
            self._logger.exception("Error while closing the current llama.cpp model.")

        self._model = None
        self._signature = None
        gc.collect()
        self._logger.info("Model cache cleared.")
