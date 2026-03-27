# Desktop AI Assistant

> Your local AI cockpit for chat, screenshots, files, search, and long-term knowledge.

[![Stars](https://img.shields.io/github/stars/Joyee112021/Desktop-Ai-Assistant?style=for-the-badge&color=0b1f2b)](https://github.com/Joyee112021/Desktop-Ai-Assistant)
[![License](https://img.shields.io/badge/License-MIT-0b1f2b?style=for-the-badge)](./LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12-0b1f2b?style=for-the-badge)](https://www.python.org/downloads/windows/)
[![Downloads](https://img.shields.io/github/downloads/Joyee112021/Desktop-Ai-Assistant/total?style=for-the-badge&color=0b1f2b)](https://github.com/Joyee112021/Desktop-Ai-Assistant/releases)

Desktop AI Assistant is a polished Windows desktop app for running local GGUF models with a product-style floating UI. It is designed for people who want a clean local assistant with setup automation, model downloads, screenshot analysis, file context, lightweight long-term memory, and tool-routed workflows without needing a browser tab farm.

## Why This Project

- Local-first: your prompts stay on your machine
- Beautiful floating GUI with glassmorphism, motion, and streaming responses
- Adaptive setup flow for different hardware levels
- Built-in model catalog with one-click downloads
- Tool-aware workflow: search, file context, screenshots, local memory, and explicit Python helper execution
- Ready for public GitHub distribution and Windows packaging

## Feature Map

### Core AI

- Local GGUF inference with `llama-cpp-python`
- Chat streaming with typing animation
- Vision support for screenshot and image analysis
- Separate interface language and assistant reply language
- CPU-first runtime today, with hardware modes already prepared for Intel iGPU, AMD GPU, and NVIDIA GPU

### Smart Context

- File attachment support
- Image attachment support
- Desktop screenshot capture
- Lightweight web search context
- Local long-term memory with SQLite FTS indexing for `TXT`, `MD`, `PDF`, and similar readable documents
- Automatic retrieval of relevant local knowledge snippets during chat

### Tool Workflow

- Automatic live-info detection for web search style prompts
- Explicit Python helper execution via `/python ...` or `python: ...`
- Tool-router scaffolding that prepares local memory, Python output, and search intents before inference

### UI / UX

- Glassmorphism floating assistant window
- Smooth intro and message-entry animations
- Thinking indicator and streaming typewriter output
- Rounded window mask
- Modular setup wizard with separate focused dialogs
- Resize-safe setup dialogs with scrollbars instead of collapsing controls
- Localized UI for English, Traditional Chinese, and Simplified Chinese

### Engineering

- Logging with rotating log files
- Test suite for prompt rendering, runtime config, localization helpers, inference fallback, local memory, and tool routing
- Batch launcher for beginners
- PyInstaller spec and build script for Windows packaging

## Current Model Catalog

Models are downloaded on demand. Large weights are not committed to Git.

- `tinyllama-1.1b-q4km`
- `gemma-2-2b-q4km`
- `qwen-2.5-1.5b-q4km`
- `smollm2-1.7b-q4km`
- `llama-3.2-3b-q4km`
- `phi-3.5-mini-q4km`
- `mistral-7b-q4km`
- `qwen-2.5-7b-q4km`
- `llama-3.1-8b-q4km`
- `llava-1.5-7b-q4k`
- `mistral-nemo-12b-q4km`

## Quick Start

### Easiest Launch

Run:

```bat
launch_desktop_ai_assistant.bat
```

It will:

1. Check whether Python 3.12 is installed
2. Create `venv` if needed
3. Install `requirements.txt`
4. Launch the app

### Manual Setup

```powershell
cd C:\desktop_ai_assistant
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python main.py
```

## Setup Wizard

On first launch, the adaptive setup wizard helps you choose:

- Performance preset: `Low` to `Extreme`, plus `Custom`
- Hardware mode: `CPU`, `Intel iGPU`, `AMD GPU`, `NVIDIA GPU`
- Interface language
- Assistant reply language
- Manual tuning for threads, context, batch size, token limit, history, and temperature
- Whether to use memory mapping and warmup
- Which model to install and use

The setup flow is split into focused modules:

- `General Settings`
- `Advanced Tuning`
- `Model Library`

When the dialog becomes too small, content scrolls instead of collapsing into overlapping controls.

## Long-Term Memory

This project now includes a lightweight local knowledge store backed by SQLite FTS.

What it does:

- Indexes local readable documents into chunks
- Stores them in `config/memory.sqlite3`
- Retrieves the most relevant snippets during future chats
- Automatically indexes supported files when you attach them in the UI

Supported document types:

- `TXT`
- `MD`
- `PDF`
- `LOG`
- `JSON`
- `YAML`
- `CSV`
- `PY`

## Tool-Routed Workflow

The assistant is no longer just a plain text box.

It now has a simple tool router that can:

- Trigger web-search intent for likely live-information questions
- Pull relevant snippets from the local knowledge base
- Run an explicit Python helper when the user writes `/python ...` or `python: ...`

Examples:

```text
latest llama.cpp release notes
```

```text
/python print(sum(i * i for i in range(10)))
```

```text
Use my local notes to summarize the project roadmap
```

## Performance Notes

For CPU-heavy systems like an Intel Core i7-14700:

- Start with `Normal` or `High`
- `Llama 3.1 8B Instruct` is the recommended all-round default
- The runtime now uses hybrid-core-aware thread caps to avoid overcommitting efficiency cores on heavier CPU workloads

Memory guidance:

- 8 GB RAM: tiny and small models
- 8 to 12 GB RAM: 3B to 4B class models
- 16 GB RAM: 7B to 8B class models and LLaVA 7B
- 24 GB RAM or more: larger 12B-class models

## Packaging for Release

This repository includes a Windows build pipeline:

- [build_release.bat](./build_release.bat)
- [desktop_ai_assistant.spec](./desktop_ai_assistant.spec)

Build command:

```bat
build_release.bat
```

This installs dependencies and builds a PyInstaller release using the included spec file.

## Project Structure

```text
desktop_ai_assistant/
|-- ai/
|-- config/
|-- gui/
|-- models/
|-- tests/
|-- utils/
|-- build_release.bat
|-- desktop_ai_assistant.spec
|-- download_model.py
|-- launch_desktop_ai_assistant.bat
|-- main.py
`-- README.md
```

## Troubleshooting

### The app says GPU mode is unavailable

Your current `llama-cpp-python` build does not support GPU offload yet, so the app will fall back to CPU mode.

### A model is too large for my RAM

Pick a smaller model or switch to a GPU-enabled backend later.

### Image analysis is unavailable

Use the `LLaVA 1.5 7B Vision` model and make sure both the main model and `mmproj` file are downloaded.

### First response is slow

That is normal for local inference. Use warmup, choose a smaller model, or lower the preset.

## Roadmap

- CUDA/NVIDIA backend edition
- Better semantic retrieval and embeddings
- Multi-step agent actions
- Session sidebar and conversation naming
- Richer model benchmarks inside the setup wizard
- Release-grade installer and signed Windows builds

## License

Application code is released under the MIT License. Third-party models have their own licenses and usage terms. Always review the original model card before redistributing or packaging a model with your release.

## THIS README.MD IS MADE BY CHATGPT 5.4
