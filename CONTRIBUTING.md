# Contributing

Thanks for your interest in improving Desktop AI Assistant.

## Local setup

1. Install Python 3.12.
2. Create a virtual environment.
3. Install dependencies with `pip install -r requirements.txt`.
4. Run the app with `python main.py`.

## Before opening a pull request

1. Run `python -m compileall main.py download_model.py ai config gui utils tests`
2. Run `python -m unittest discover -s tests -v`
3. Verify the setup wizard still opens and the main window can launch.

## Project rules

- Do not commit downloaded GGUF model files.
- Keep the public UI in English unless a specific localization feature is being added.
- Prefer small, reviewable pull requests.
- Document user-facing changes in `README.md` and `CHANGELOG.md`.

## Bug reports

Please include:

- Windows version
- Python version
- `llama-cpp-python` version
- Selected model id
- Selected hardware mode
- Error message or screenshot
