import os
import sys
from pathlib import Path


APP_NAME = "Desktop AI Assistant"
APP_VERSION = "1.2.0"
APP_EDITION = "Adaptive Local Edition"

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
    RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", BASE_DIR))
else:
    BASE_DIR = Path(__file__).resolve().parent.parent
    RESOURCE_DIR = BASE_DIR
CONFIG_DIR = BASE_DIR / "config"
MODEL_DIR = BASE_DIR / "models"
README_PATH = RESOURCE_DIR / "README.md"
LOG_DIR = BASE_DIR / "logs"
BUILD_DIR = BASE_DIR / "build"
DIST_DIR = BASE_DIR / "dist"

USER_SETTINGS_PATH = CONFIG_DIR / "user_settings.json"
MODEL_CATALOG_PATH = RESOURCE_DIR / "models" / "catalog.json"
MEMORY_DB_PATH = CONFIG_DIR / "memory.sqlite3"

CPU_COUNT = os.cpu_count() or 8

APP_WIDTH = 580
APP_HEIGHT = 900
APP_WINDOW_RADIUS = 24
SETUP_DIALOG_WIDTH = 980
SETUP_DIALOG_HEIGHT = 1040

SETTINGS_SCHEMA_VERSION = 2

DEFAULT_HOTKEY = os.getenv("DESKTOP_AI_HOTKEY", "ctrl+space")
DEFAULT_HISTORY_MESSAGES = 12
DEFAULT_TEMPERATURE = 0.55
DEFAULT_TOP_P = 0.90
DEFAULT_REPEAT_PENALTY = 1.08
DEFAULT_USE_MMAP = True
DEFAULT_GPU_LAYERS = 0
DEFAULT_RESPONSE_LANGUAGE = "en"
DEFAULT_INTERFACE_LANGUAGE = "en"
DEFAULT_HARDWARE_MODE = "cpu"
DEFAULT_RAG_RESULTS = 3
DEFAULT_RAG_CHUNK_SIZE = 1200
DEFAULT_RAG_CHUNK_OVERLAP = 180

PYTHON_WINDOWS_DOWNLOAD_URL = "https://www.python.org/downloads/windows/"


def clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, value))


def build_performance_profiles(cpu_count: int = CPU_COUNT) -> dict[str, dict[str, int | str]]:
    return {
        "low": {
            "label": "Low",
            "description": "Smallest load on the system. Best for weak CPUs or quiet background use.",
            "n_threads": clamp(max(2, cpu_count // 5), 2, 6),
            "n_ctx": 2048,
            "n_batch": 256,
            "max_tokens": 192,
        },
        "medium": {
            "label": "Medium",
            "description": "Lightweight and stable. Good for laptops and entry-level desktops.",
            "n_threads": clamp(max(4, cpu_count // 4), 4, 8),
            "n_ctx": 3072,
            "n_batch": 384,
            "max_tokens": 256,
        },
        "normal": {
            "label": "Normal",
            "description": "Recommended starting point for most users.",
            "n_threads": clamp(max(6, cpu_count // 3), 6, 12),
            "n_ctx": 4096,
            "n_batch": 512,
            "max_tokens": 384,
        },
        "high": {
            "label": "High",
            "description": "Higher throughput with more CPU pressure and memory use.",
            "n_threads": clamp(max(8, cpu_count // 2), 8, 16),
            "n_ctx": 5120,
            "n_batch": 768,
            "max_tokens": 448,
        },
        "ultra": {
            "label": "Ultra",
            "description": "Aggressive local tuning for strong desktop CPUs and more RAM.",
            "n_threads": clamp(max(10, int(cpu_count * 0.7)), 10, 22),
            "n_ctx": 6144,
            "n_batch": 1024,
            "max_tokens": 512,
        },
        "extreme": {
            "label": "Extreme",
            "description": "Maximum preset for users who want the app to push harder.",
            "n_threads": clamp(max(12, cpu_count - 2), 12, 26),
            "n_ctx": 8192,
            "n_batch": 1280,
            "max_tokens": 640,
        },
        "custom": {
            "label": "Custom",
            "description": "Manual tuning for advanced users.",
            "n_threads": clamp(max(6, cpu_count // 3), 6, 12),
            "n_ctx": 4096,
            "n_batch": 512,
            "max_tokens": 384,
        },
    }


PERFORMANCE_PROFILES = build_performance_profiles()

HARDWARE_MODES = {
    "cpu": {
        "label": "CPU",
        "description": "Most compatible mode. Best when your llama.cpp build does not support GPU offload.",
    },
    "nvidia": {
        "label": "NVIDIA GPU",
        "description": "Uses NVIDIA offload when a GPU-enabled llama.cpp build is installed.",
    },
    "amd": {
        "label": "AMD GPU",
        "description": "Uses AMD-capable offload when supported by the installed backend.",
    },
    "intel": {
        "label": "Intel iGPU",
        "description": "Uses Intel integrated graphics when a compatible backend is available.",
    },
}

RESPONSE_LANGUAGES = {
    "en": "English",
    "zh-TW": "Traditional Chinese",
    "zh-CN": "Simplified Chinese",
    "ja": "Japanese",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "ko": "Korean",
}

INTERFACE_LANGUAGES = {
    "en": "English",
    "zh-TW": "Traditional Chinese",
    "zh-CN": "Simplified Chinese",
}


def recommended_default_profile(cpu_count: int = CPU_COUNT) -> str:
    if cpu_count >= 24:
        return "high"
    if cpu_count >= 12:
        return "normal"
    return "medium"
