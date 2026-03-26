from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from utils.logging_utils import get_logger


LOGGER = get_logger(__name__)


@dataclass(frozen=True)
class ScriptExecutionResult:
    """Structured result for an explicit Python tool execution request."""

    command_label: str
    output: str
    success: bool


def extract_python_request(text: str) -> str | None:
    """Extract an explicit Python snippet request from the user message."""
    stripped = text.strip()
    if stripped.lower().startswith("/python "):
        return stripped[8:].strip()
    if stripped.lower().startswith("python:"):
        return stripped[7:].strip()

    fence = re.search(r"```python\s+(.*?)```", stripped, re.DOTALL | re.IGNORECASE)
    if fence:
        return fence.group(1).strip()
    return None


def run_python_snippet(code: str, timeout_seconds: int = 8) -> ScriptExecutionResult:
    """Run an explicit Python snippet in a subprocess and capture its output."""
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as handle:
        script_path = Path(handle.name)
        handle.write(code)

    try:
        LOGGER.info("Running explicit Python tool request: %s", script_path)
        completed = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        output = (completed.stdout or "").strip()
        if completed.stderr:
            output = (output + "\n" + completed.stderr.strip()).strip()
        if not output:
            output = "(The Python script finished without output.)"
        return ScriptExecutionResult(
            command_label="Python helper",
            output=output,
            success=completed.returncode == 0,
        )
    finally:
        try:
            script_path.unlink(missing_ok=True)
        except Exception:
            LOGGER.exception("Failed to delete temporary Python script: %s", script_path)
