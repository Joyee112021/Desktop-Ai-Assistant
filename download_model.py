import argparse
import sys

from config.user_settings import find_model_option, load_model_catalog
from utils.model_download import download_to_path


def print_model_list():
    catalog = load_model_catalog()
    print("Available Desktop AI Assistant models:\n")
    for option in catalog:
        print(f"- {option.id}")
        print(f"  Name: {option.name}")
        print(f"  Size: {option.parameter_size} | Quant: {option.quantization} | Approx: {option.approx_size_gb:.1f} GB")
        print(f"  Capabilities: {', '.join(option.capabilities)}")
        print(f"  Best for: {option.recommended_for}")
        print(f"  Installed: {'yes' if option.is_ready() else 'no'}")
        print("")


def download_model(model_id: str):
    catalog = load_model_catalog()
    model = find_model_option(model_id, catalog)
    if model is None:
        print(f"Unknown model id: {model_id}", file=sys.stderr)
        return 1

    if model.is_ready():
        print(f"{model.name} is already installed at {model.existing_primary_path()}")
        return 0

    print(f"Downloading {model.name}")
    for filename in model.download_targets():
        target_path = model.install_path().parent / filename
        if target_path.exists():
            print(f"Skipping existing file: {filename}")
            continue

        print(f"Source: {model.download_url(filename)}")
        print(f"Target: {target_path}")

        def on_progress(done: int, total: int):
            if total > 0:
                percent = int((done / total) * 100)
                print(f"\rProgress: {percent:3d}% ({filename})", end="", flush=True)
            else:
                print(f"\rDownloaded: {done / (1024 * 1024):.1f} MB ({filename})", end="", flush=True)

        download_to_path(model.download_url(filename), target_path, progress_callback=on_progress)
        print("")

    print("Download finished.")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Download a GGUF model for Desktop AI Assistant.")
    parser.add_argument("--list", action="store_true", help="List the built-in model catalog.")
    parser.add_argument("--model", help="Model id to download.")
    args = parser.parse_args()

    if args.list or not args.model:
        print_model_list()
        if not args.model:
            return 0

    return download_model(args.model)


if __name__ == "__main__":
    raise SystemExit(main())
