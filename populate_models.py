"""Provision an explicitly selected model profile from a temporary Runpod Pod."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from urllib.parse import quote


def matches(path, model):
    if not path.is_file() or path.stat().st_size != model["bytes"]:
        return False
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest() == model["sha256"]


def install(root, model, staging_dir):
    destination = root / model["target"]
    if not destination.resolve().is_relative_to(root):
        raise ValueError(f"Target must stay in the models directory: {model['target']}")
    if matches(destination, model):
        print(f"Verified {destination}", flush=True)
        return
    if destination.exists() or destination.is_symlink():
        raise ValueError(f"Checksum mismatch at {destination}; move it aside before retrying")

    url_path = quote(f"{model['repo']}/resolve/{model['revision']}/{model['source']}")
    with tempfile.NamedTemporaryFile(dir=staging_dir, suffix=".safetensors") as temporary:
        print(f"Downloading {model['target']} ({model['bytes']} bytes)", flush=True)
        subprocess.run(
            ["curl", "--fail", "--location", "--silent", "--show-error", "--retry", "3",
             "--connect-timeout", "30", "--max-filesize", str(model["bytes"]),
             "--output", temporary.name, f"https://huggingface.co/{url_path}"],
            check=True,
        )
        if not matches(Path(temporary.name), model):
            raise ValueError(f"Downloaded file does not match SHA-256 for {model['target']}")

        destination.parent.mkdir(parents=True, exist_ok=True)
        created = False
        try:
            with destination.open("xb") as output:
                created = True
                with Path(temporary.name).open("rb") as source:
                    shutil.copyfileobj(source, output, length=8 * 1024 * 1024)
        except BaseException:
            if created:
                destination.unlink(missing_ok=True)
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--models-dir", type=Path, required=True)
    parser.add_argument("--staging-dir", type=Path, default=Path("/tmp"))
    parser.add_argument("--only", action="append", metavar="TARGET",
                        help="Select a target from the profile. Repeat for multiple files.")
    parser.add_argument("--check", action="store_true", help="Verify existing files without downloading")
    args = parser.parse_args()

    try:
        models = json.loads(args.profile.read_text())
        models_by_target = {model["target"]: model for model in models}
        if len(models_by_target) != len(models):
            parser.error("Profile contains duplicate targets")
        if args.only:
            models = [models_by_target[target] for target in dict.fromkeys(args.only)]

        root = args.models_dir.resolve()
        staging_dir = args.staging_dir.resolve()
        if args.check:
            for model in models:
                path = (root / model["target"]).resolve()
                if not path.is_relative_to(root) or not matches(path, model):
                    parser.exit(1, f"Missing or invalid model: {model['target']}\n")
            print(f"Verified {len(models)} model file(s)")
            return

        if not os.environ.get("RUNPOD_POD_ID"):
            parser.error("Model downloads must run inside the Runpod provisioning Pod")
        if staging_dir.is_relative_to(root) or staging_dir == root.parent:
            parser.error("--staging-dir must be on the Pod's local disk")
        for model in models:
            install(root, model, staging_dir)
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Model provisioning failed: {error}\n")


if __name__ == "__main__":
    main()
