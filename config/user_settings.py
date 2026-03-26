import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import llama_cpp

from config.localization import build_system_prompt, hardware_label, language_label, tr
from config.settings import (
    DEFAULT_GPU_LAYERS,
    DEFAULT_HARDWARE_MODE,
    DEFAULT_HISTORY_MESSAGES,
    DEFAULT_HOTKEY,
    DEFAULT_INTERFACE_LANGUAGE,
    DEFAULT_REPEAT_PENALTY,
    DEFAULT_RESPONSE_LANGUAGE,
    DEFAULT_TEMPERATURE,
    DEFAULT_TOP_P,
    DEFAULT_USE_MMAP,
    HARDWARE_MODES,
    INTERFACE_LANGUAGES,
    MODEL_CATALOG_PATH,
    MODEL_DIR,
    PERFORMANCE_PROFILES,
    RESPONSE_LANGUAGES,
    SETTINGS_SCHEMA_VERSION,
    USER_SETTINGS_PATH,
    recommended_default_profile,
)
from utils.system_info import SystemInfo, collect_system_info


LEGACY_PROFILE_MAP = {
    "efficiency": "low",
    "balanced": "normal",
    "power": "high",
}

KNOWN_BACKEND_INCOMPATIBLE_MODELS = {
    "mistral-nemo-12b-q4km": "The installed llama-cpp-python build in this project cannot load Mistral Nemo 12B yet.",
}


@dataclass(frozen=True)
class ModelOption:
    id: str
    name: str
    family: str
    parameter_size: str
    quantization: str
    summary: str
    recommended_for: str
    badge: str
    repo: str
    primary_file: str
    candidate_files: tuple[str, ...]
    auxiliary_files: tuple[str, ...]
    capabilities: tuple[str, ...]
    approx_size_gb: float
    minimum_ram_gb: int
    default_profile_id: str = "normal"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ModelOption":
        primary_file = data.get("primary_file") or data.get("filename")
        candidate_files = data.get("candidate_files") or [primary_file]
        auxiliary_files = data.get("auxiliary_files") or []
        capabilities = data.get("capabilities") or ["chat"]
        return cls(
            id=data["id"],
            name=data["name"],
            family=data["family"],
            parameter_size=data["parameter_size"],
            quantization=data["quantization"],
            summary=data["summary"],
            recommended_for=data["recommended_for"],
            badge=data["badge"],
            repo=data["repo"],
            primary_file=primary_file,
            candidate_files=tuple(candidate_files),
            auxiliary_files=tuple(auxiliary_files),
            capabilities=tuple(capabilities),
            approx_size_gb=float(data["approx_size_gb"]),
            minimum_ram_gb=int(data["minimum_ram_gb"]),
            default_profile_id=data.get("default_profile_id", "normal"),
        )

    def install_path(self) -> Path:
        return MODEL_DIR / self.primary_file

    def existing_primary_path(self) -> Path | None:
        for candidate in self.candidate_files:
            path = MODEL_DIR / candidate
            if path.exists():
                return path
        return None

    def required_files(self) -> tuple[Path, ...]:
        return tuple(MODEL_DIR / filename for filename in self.auxiliary_files)

    def missing_files(self) -> list[str]:
        missing = []
        if self.existing_primary_path() is None:
            missing.append(self.primary_file)
        for path in self.required_files():
            if not path.exists():
                missing.append(path.name)
        return missing

    def is_ready(self) -> bool:
        return self.existing_primary_path() is not None and not self.missing_files()

    def supports(self, capability: str) -> bool:
        return capability in self.capabilities

    def download_targets(self) -> tuple[str, ...]:
        return (self.primary_file, *self.auxiliary_files)

    def auxiliary_paths(self) -> tuple[Path, ...]:
        return tuple(MODEL_DIR / filename for filename in self.auxiliary_files)

    def download_url(self, filename: str) -> str:
        return f"https://huggingface.co/{self.repo}/resolve/main/{filename}?download=true"


@dataclass
class UserSettings:
    schema_version: int = SETTINGS_SCHEMA_VERSION
    first_run_complete: bool = False
    profile_id: str = field(default_factory=recommended_default_profile)
    selected_model_id: str = ""
    hardware_mode: str = DEFAULT_HARDWARE_MODE
    interface_language: str = DEFAULT_INTERFACE_LANGUAGE
    response_language: str = DEFAULT_RESPONSE_LANGUAGE
    hotkey: str = DEFAULT_HOTKEY
    warmup_on_launch: bool = True
    history_messages: int = DEFAULT_HISTORY_MESSAGES
    n_threads: int | None = None
    n_ctx: int | None = None
    n_batch: int | None = None
    max_tokens: int | None = None
    temperature: float = DEFAULT_TEMPERATURE
    top_p: float = DEFAULT_TOP_P
    repeat_penalty: float = DEFAULT_REPEAT_PENALTY
    use_mmap: bool = DEFAULT_USE_MMAP

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UserSettings":
        profile_id = str(data.get("profile_id", recommended_default_profile()))
        profile_id = LEGACY_PROFILE_MAP.get(profile_id, profile_id)

        return cls(
            schema_version=int(data.get("schema_version", SETTINGS_SCHEMA_VERSION)),
            first_run_complete=bool(data.get("first_run_complete", False)),
            profile_id=profile_id,
            selected_model_id=str(data.get("selected_model_id", "")),
            hardware_mode=str(data.get("hardware_mode", DEFAULT_HARDWARE_MODE)),
            interface_language=str(data.get("interface_language", DEFAULT_INTERFACE_LANGUAGE)),
            response_language=str(data.get("response_language", DEFAULT_RESPONSE_LANGUAGE)),
            hotkey=str(data.get("hotkey", DEFAULT_HOTKEY)),
            warmup_on_launch=bool(data.get("warmup_on_launch", True)),
            history_messages=int(data.get("history_messages", DEFAULT_HISTORY_MESSAGES)),
            n_threads=_optional_int(data.get("n_threads")),
            n_ctx=_optional_int(data.get("n_ctx")),
            n_batch=_optional_int(data.get("n_batch")),
            max_tokens=_optional_int(data.get("max_tokens")),
            temperature=float(data.get("temperature", DEFAULT_TEMPERATURE)),
            top_p=float(data.get("top_p", DEFAULT_TOP_P)),
            repeat_penalty=float(data.get("repeat_penalty", DEFAULT_REPEAT_PENALTY)),
            use_mmap=bool(data.get("use_mmap", DEFAULT_USE_MMAP)),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RuntimeConfig:
    model: ModelOption
    model_path: Path
    auxiliary_paths: tuple[Path, ...]
    profile_id: str
    profile_label: str
    hardware_mode: str
    hardware_label: str
    response_language: str
    n_ctx: int
    n_threads: int
    n_batch: int
    n_gpu_layers: int
    use_mmap: bool
    max_tokens: int
    temperature: float
    top_p: float
    repeat_penalty: float
    hotkey: str
    history_messages: int
    warmup_on_launch: bool
    system_prompt: str
    total_memory_gb: int
    gpu_offload_supported: bool
    backend_warning: str | None = None

    @property
    def loader_signature(self) -> tuple[Any, ...]:
        return (
            str(self.model_path),
            tuple(str(path) for path in self.auxiliary_paths),
            self.n_ctx,
            self.n_threads,
            self.n_batch,
            self.n_gpu_layers,
            self.use_mmap,
            self.hardware_mode,
        )


def _optional_int(value: Any) -> int | None:
    if value in (None, "", "null"):
        return None
    return int(value)


def llama_cpp_version() -> str:
    return str(getattr(llama_cpp, "__version__", "unknown"))


def backend_model_issue(model: ModelOption) -> str | None:
    return KNOWN_BACKEND_INCOMPATIBLE_MODELS.get(model.id)


def load_model_catalog() -> list[ModelOption]:
    with MODEL_CATALOG_PATH.open("r", encoding="utf-8") as handle:
        raw_data = json.load(handle)

    items = raw_data.get("models", raw_data)
    return [ModelOption.from_dict(item) for item in items]


def find_model_option(model_id: str, catalog: list[ModelOption] | None = None) -> ModelOption | None:
    catalog = catalog or load_model_catalog()
    for option in catalog:
        if option.id == model_id:
            return option
    return None


def default_model_id(catalog: list[ModelOption] | None = None) -> str:
    catalog = catalog or load_model_catalog()
    system_info = collect_system_info()

    preferred = find_model_option("llama-3.1-8b-q4km", catalog)
    if preferred is not None and preferred.is_ready() and backend_model_issue(preferred) is None:
        return preferred.id

    for option in catalog:
        if option.is_ready() and backend_model_issue(option) is None:
            return option.id

    if preferred is not None:
        if system_info.total_memory_gb >= preferred.minimum_ram_gb and backend_model_issue(preferred) is None:
            return preferred.id

    candidates = [
        "mistral-nemo-12b-q4km",
        "llama-3.1-8b-q4km",
        "qwen-2.5-7b-q4km",
        "phi-3.5-mini-q4km",
        "llama-3.2-3b-q4km",
        "qwen-2.5-1.5b-q4km",
        "smollm2-1.7b-q4km",
        "tinyllama-1.1b-q4km",
    ]
    for model_id in candidates:
        option = find_model_option(model_id, catalog)
        if (
            option is not None
            and system_info.total_memory_gb >= option.minimum_ram_gb
            and backend_model_issue(option) is None
        ):
            return option.id

    for option in catalog:
        if backend_model_issue(option) is None:
            return option.id

    return catalog[0].id


def normalize_settings(settings: UserSettings, catalog: list[ModelOption] | None = None) -> UserSettings:
    catalog = catalog or load_model_catalog()

    if settings.schema_version != SETTINGS_SCHEMA_VERSION:
        settings = UserSettings()

    settings.profile_id = LEGACY_PROFILE_MAP.get(settings.profile_id, settings.profile_id)

    if settings.profile_id not in PERFORMANCE_PROFILES:
        settings.profile_id = recommended_default_profile()

    if settings.hardware_mode not in HARDWARE_MODES:
        settings.hardware_mode = DEFAULT_HARDWARE_MODE

    if settings.interface_language not in INTERFACE_LANGUAGES:
        settings.interface_language = DEFAULT_INTERFACE_LANGUAGE

    if settings.response_language not in RESPONSE_LANGUAGES:
        settings.response_language = DEFAULT_RESPONSE_LANGUAGE

    selected_model = find_model_option(settings.selected_model_id, catalog)
    if not settings.selected_model_id or selected_model is None or backend_model_issue(selected_model) is not None:
        settings.selected_model_id = default_model_id(catalog)

    settings.history_messages = max(4, min(24, settings.history_messages))
    settings.temperature = max(0.1, min(1.5, settings.temperature))
    settings.top_p = max(0.1, min(1.0, settings.top_p))
    settings.repeat_penalty = max(1.0, min(1.4, settings.repeat_penalty))
    return settings


def user_settings_exist() -> bool:
    return USER_SETTINGS_PATH.exists()


def load_user_settings(catalog: list[ModelOption] | None = None) -> UserSettings:
    catalog = catalog or load_model_catalog()

    if not USER_SETTINGS_PATH.exists():
        return normalize_settings(UserSettings(), catalog)

    with USER_SETTINGS_PATH.open("r", encoding="utf-8") as handle:
        raw_data = json.load(handle)

    return normalize_settings(UserSettings.from_dict(raw_data), catalog)


def save_user_settings(settings: UserSettings) -> None:
    USER_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with USER_SETTINGS_PATH.open("w", encoding="utf-8") as handle:
        json.dump(settings.to_dict(), handle, indent=2, ensure_ascii=True)


def _resolve_gpu_layers(settings: UserSettings, model: ModelOption, system_info: SystemInfo) -> tuple[int, str | None]:
    if settings.hardware_mode == "cpu":
        return DEFAULT_GPU_LAYERS, None

    if not system_info.gpu_offload_supported:
        return 0, tr(
            "backend_gpu_fallback",
            settings.interface_language,
            hardware=hardware_label(settings.hardware_mode, settings.interface_language),
        )

    if settings.hardware_mode == "intel":
        return 24, None
    if model.approx_size_gb >= 7.0:
        return 50, None
    return -1, None


def _optimize_for_large_models(
    n_threads: int,
    n_ctx: int,
    n_batch: int,
    max_tokens: int,
    model: ModelOption,
    settings: UserSettings,
    system_info: SystemInfo,
) -> tuple[int, int, int, int]:
    if system_info.efficiency_core_hint > 0:
        hybrid_cap = max(
            system_info.performance_core_hint,
            system_info.performance_core_hint + max(2, system_info.efficiency_core_hint // 2),
        )
        n_threads = min(n_threads, hybrid_cap)

    if settings.hardware_mode in {"cpu", "intel"} and model.approx_size_gb >= 7.0:
        cpu_thread_cap = max(8, system_info.logical_cpu_count - 4)
        if system_info.efficiency_core_hint > 0:
            cpu_thread_cap = min(
                cpu_thread_cap,
                system_info.performance_core_hint + max(2, system_info.efficiency_core_hint // 2),
            )
        n_threads = min(n_threads, cpu_thread_cap)
        n_ctx = min(n_ctx, 5120)
        n_batch = min(n_batch, 640)
        max_tokens = min(max_tokens, 448)

    if settings.hardware_mode in {"cpu", "intel"} and system_info.total_memory_gb < model.minimum_ram_gb:
        n_ctx = min(n_ctx, 2048)
        n_batch = min(n_batch, 256)
        max_tokens = min(max_tokens, 256)

    return n_threads, n_ctx, n_batch, max_tokens


def build_runtime_config(
    settings: UserSettings,
    catalog: list[ModelOption] | None = None,
    system_info: SystemInfo | None = None,
) -> RuntimeConfig:
    catalog = catalog or load_model_catalog()
    system_info = system_info or collect_system_info()
    settings = normalize_settings(settings, catalog)
    model = find_model_option(settings.selected_model_id, catalog)
    if model is None:
        raise ValueError(f"Unknown model id: {settings.selected_model_id}")

    if settings.profile_id == "custom":
        fallback = PERFORMANCE_PROFILES["normal"]
        n_threads = settings.n_threads or int(fallback["n_threads"])
        n_ctx = settings.n_ctx or int(fallback["n_ctx"])
        n_batch = settings.n_batch or int(fallback["n_batch"])
        max_tokens = settings.max_tokens or int(fallback["max_tokens"])
        profile_label = str(PERFORMANCE_PROFILES["custom"]["label"])
    else:
        profile = PERFORMANCE_PROFILES[settings.profile_id]
        n_threads = int(profile["n_threads"])
        n_ctx = int(profile["n_ctx"])
        n_batch = int(profile["n_batch"])
        max_tokens = int(profile["max_tokens"])
        profile_label = str(profile["label"])

    n_threads, n_ctx, n_batch, max_tokens = _optimize_for_large_models(
        n_threads,
        n_ctx,
        n_batch,
        max_tokens,
        model,
        settings,
        system_info,
    )
    n_gpu_layers, backend_warning = _resolve_gpu_layers(settings, model, system_info)
    model_path = model.existing_primary_path() or model.install_path()

    return RuntimeConfig(
        model=model,
        model_path=model_path,
        auxiliary_paths=model.auxiliary_paths(),
        profile_id=settings.profile_id,
        profile_label=profile_label,
        hardware_mode=settings.hardware_mode,
        hardware_label=str(HARDWARE_MODES[settings.hardware_mode]["label"]),
        response_language=settings.response_language,
        n_ctx=n_ctx,
        n_threads=n_threads,
        n_batch=n_batch,
        n_gpu_layers=n_gpu_layers,
        use_mmap=settings.use_mmap,
        max_tokens=max_tokens,
        temperature=settings.temperature,
        top_p=settings.top_p,
        repeat_penalty=settings.repeat_penalty,
        hotkey=settings.hotkey,
        history_messages=settings.history_messages,
        warmup_on_launch=settings.warmup_on_launch,
        system_prompt=build_system_prompt(settings.response_language),
        total_memory_gb=system_info.total_memory_gb,
        gpu_offload_supported=system_info.gpu_offload_supported,
        backend_warning=backend_warning,
    )
