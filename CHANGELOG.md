# Changelog

## 1.2.1

- Split interface language from assistant reply language.
- Rebuilt the setup wizard into a modular button-driven flow with separate dialogs.
- Fixed setup wizard state sync so model and language changes apply correctly.
- Reworked runtime controls layout to reduce overlap on scaled displays.
- Added backend compatibility guard for Mistral Nemo 12B on the current llama-cpp-python build.
- Added automatic web-search trigger heuristics for likely live-information questions.
- Improved uploaded file and image messaging so the next user bubble shows the attached item names.
- Expanded GitHub project metadata with license, changelog, contributing guide, and stronger `.gitignore`.

## 1.2.0

- Added adaptive setup wizard with hardware modes and response language selection.
- Added expanded GGUF model catalog with tiny, standard, vision, and larger models.
- Added desktop screenshot capture, image upload, file attachment, and manual web search.
- Added automatic Windows launcher batch script.
