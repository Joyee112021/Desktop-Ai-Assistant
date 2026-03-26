from __future__ import annotations

import ctypes
import os
import platform
import subprocess
from dataclasses import dataclass
from functools import lru_cache

import psutil
from llama_cpp import llama_supports_gpu_offload


class MemoryStatusEx(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


@dataclass(frozen=True)
class GPUInfo:
    name: str
    vendor: str


@dataclass(frozen=True)
class SystemInfo:
    cpu_name: str
    logical_cpu_count: int
    physical_cpu_count: int
    performance_core_hint: int
    efficiency_core_hint: int
    total_memory_gb: int
    available_memory_gb: int
    gpus: tuple[GPUInfo, ...]
    gpu_offload_supported: bool


def _vendor_from_name(name: str) -> str:
    lowered = name.lower()
    if "nvidia" in lowered:
        return "nvidia"
    if "amd" in lowered or "radeon" in lowered:
        return "amd"
    if "intel" in lowered:
        return "intel"
    return "unknown"


def _run_powershell(command: str) -> list[str]:
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
        return [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    except Exception:
        return []


def _get_cpu_name() -> str:
    lines = _run_powershell("Get-CimInstance Win32_Processor | Select-Object -First 1 -ExpandProperty Name")
    if lines:
        return lines[0]
    return platform.processor() or "Unknown CPU"


def _get_gpu_list() -> tuple[GPUInfo, ...]:
    lines = _run_powershell("Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name")
    gpus = [GPUInfo(name=line, vendor=_vendor_from_name(line)) for line in lines]
    return tuple(gpus)


def _get_memory_info() -> tuple[int, int]:
    try:
        memory = psutil.virtual_memory()
        return int(memory.total / (1024**3)), int(memory.available / (1024**3))
    except Exception:
        memory_status = MemoryStatusEx()
        memory_status.dwLength = ctypes.sizeof(MemoryStatusEx)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory_status))
        total_gb = int(memory_status.ullTotalPhys / (1024**3))
        available_gb = int(memory_status.ullAvailPhys / (1024**3))
        return total_gb, available_gb


def _estimate_hybrid_core_layout(cpu_name: str, logical_cpu_count: int, physical_cpu_count: int) -> tuple[int, int]:
    normalized = cpu_name.lower().replace(" ", "").replace("-", "")
    explicit_map = {
        "i714700": (8, 12),
        "i714700k": (8, 12),
        "i714700f": (8, 12),
        "i914900": (8, 16),
        "i914900k": (8, 16),
        "i513600": (6, 8),
        "i713700": (8, 8),
        "i713700k": (8, 8),
        "i714700hx": (8, 12),
    }
    for token, layout in explicit_map.items():
        if token in normalized:
            return layout

    if "intel" in normalized and physical_cpu_count >= 12 and logical_cpu_count > physical_cpu_count:
        performance_guess = min(8, max(4, physical_cpu_count // 2))
        efficiency_guess = max(0, physical_cpu_count - performance_guess)
        return performance_guess, efficiency_guess

    return physical_cpu_count, 0


@lru_cache(maxsize=1)
def collect_system_info() -> SystemInfo:
    total_memory_gb, available_memory_gb = _get_memory_info()
    cpu_name = _get_cpu_name()
    logical_cpu_count = psutil.cpu_count(logical=True) or os.cpu_count() or 8
    physical_cpu_count = psutil.cpu_count(logical=False) or max(1, logical_cpu_count // 2)
    performance_core_hint, efficiency_core_hint = _estimate_hybrid_core_layout(
        cpu_name,
        logical_cpu_count,
        physical_cpu_count,
    )
    return SystemInfo(
        cpu_name=cpu_name,
        logical_cpu_count=logical_cpu_count,
        physical_cpu_count=physical_cpu_count,
        performance_core_hint=performance_core_hint,
        efficiency_core_hint=efficiency_core_hint,
        total_memory_gb=total_memory_gb,
        available_memory_gb=available_memory_gb,
        gpus=_get_gpu_list(),
        gpu_offload_supported=bool(llama_supports_gpu_offload()),
    )
