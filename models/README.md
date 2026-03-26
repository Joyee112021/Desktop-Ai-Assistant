# Models Folder

Place your `.gguf` model files in this folder.

This project ships with a model catalog in [`catalog.json`](./catalog.json), but the large model weights are not committed to GitHub. You can install them in two ways:

1. Start the app and use the first-run setup window to download a model.
2. Run `python download_model.py --list` and `python download_model.py --model <model-id>`.

You can also copy any compatible GGUF file into this folder manually and select it from the setup window if it matches one of the catalog entries.
