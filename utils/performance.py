import time

from PySide6.QtCore import QThread, Signal

from ai.inference import InferenceEngine
from ai.model_loader import ModelLoader
from config.user_settings import RuntimeConfig
from utils.logging_utils import get_logger


class ModelWarmupWorker(QThread):
    """Warm up the selected model without blocking the GUI thread."""

    signal_ready = Signal(float)
    signal_error = Signal(str)

    def __init__(self, runtime_config: RuntimeConfig):
        super().__init__()
        self.runtime_config = runtime_config
        self._logger = get_logger(__name__)

    def set_runtime_config(self, runtime_config: RuntimeConfig):
        self.runtime_config = runtime_config

    def run(self):
        started = time.perf_counter()
        try:
            self._logger.info("Starting model warmup for %s.", self.runtime_config.model.name)
            ModelLoader().load_model(self.runtime_config)
            self.signal_ready.emit(time.perf_counter() - started)
        except Exception as exc:
            self._logger.exception("Model warmup failed.")
            self.signal_error.emit(str(exc))


class AIWorker(QThread):
    """Run inference in a dedicated thread and stream partial output to the UI."""

    signal_start = Signal()
    signal_token = Signal(str)
    signal_done = Signal()
    signal_error = Signal(str)
    signal_stopped = Signal()

    def __init__(self, memory, runtime_config: RuntimeConfig):
        super().__init__()
        self.memory = memory
        self.engine = InferenceEngine(runtime_config)
        self.model_ready = False
        self._stop_requested = False
        self._logger = get_logger(__name__)

    def set_runtime_config(self, runtime_config: RuntimeConfig):
        self.engine.set_runtime_config(runtime_config)
        self.model_ready = False

    def init_model(self):
        if self.model_ready:
            return True, ""

        try:
            self.engine.initialize()
            self.model_ready = True
            self._logger.info("Inference model initialized successfully.")
            return True, ""
        except Exception as exc:
            self.model_ready = False
            self._logger.exception("Inference model initialization failed.")
            return False, str(exc)

    def request_stop(self):
        self._stop_requested = True
        self.engine.request_stop()
        self._logger.info("Stop requested for active inference.")

    def run(self):
        self._stop_requested = False
        self.engine.reset_stop()

        try:
            success, error = self.init_model()
            if not success:
                self.signal_error.emit(error)
                return

            self.signal_start.emit()
            self._logger.debug("AIWorker started token streaming.")

            produced_output = False
            chunk_buffer = []
            chunk_length = 0
            last_flush = time.perf_counter()

            for token in self.engine.generate_stream(self.memory.get_context()):
                produced_output = True
                chunk_buffer.append(token)
                chunk_length += len(token)
                now = time.perf_counter()

                if chunk_length >= 28 or (now - last_flush) >= 0.024:
                    self.signal_token.emit("".join(chunk_buffer))
                    chunk_buffer.clear()
                    chunk_length = 0
                    last_flush = now

            if chunk_buffer:
                self.signal_token.emit("".join(chunk_buffer))

            if self.engine.was_stopped or self._stop_requested:
                self.signal_stopped.emit()
            elif not produced_output:
                self.signal_error.emit(
                    "The model finished without returning any text. "
                    "Try a different model or reduce the context size."
                )
        except Exception as exc:
            self._logger.exception("Unexpected AI worker failure.")
            self.signal_error.emit(f"Unexpected worker error: {exc}")
        finally:
            self.signal_done.emit()
