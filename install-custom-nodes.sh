#!/usr/bin/env bash
set -euo pipefail

while read -r name url revision; do
    [[ -z "$name" || "$name" == \#* ]] && continue
    directory="/comfyui/custom_nodes/$name"
    git init "$directory"
    git -C "$directory" fetch --depth=1 "$url" "$revision"
    git -C "$directory" checkout --detach FETCH_HEAD
    if [[ -f "$directory/requirements.txt" ]]; then
        pip install --no-cache-dir -r "$directory/requirements.txt"
    fi
    rm -rf "$directory/.git"
done < /opt/runner/custom-nodes.lock
