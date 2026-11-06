#!/usr/bin/env bash
# Download the pinned Qwen3-4B-Instruct-2507 Q4_K_M weights into ./models and verify the SHA-256.
# Pins come from ADR 0010. A mismatch deletes the file and exits non-zero.
set -euo pipefail

REPO="unsloth/Qwen3-4B-Instruct-2507-GGUF"
REVISION="a06e946bb6b655725eafa393f4a9745d460374c9"
FILE="Qwen3-4B-Instruct-2507-Q4_K_M.gguf"
SHA256="3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597"

dest_dir="${1:-$(dirname "$0")/../models}"
mkdir -p "$dest_dir"
dest="$dest_dir/$FILE"

check() { echo "$SHA256  $1" | sha256sum -c --status -; }

if [[ -f "$dest" ]] && check "$dest"; then
  echo "ok: $dest already matches $SHA256"
  exit 0
fi

url="https://huggingface.co/$REPO/resolve/$REVISION/$FILE"
tmp="$dest.part"
curl -fL --retry 3 -C - -o "$tmp" "$url"

if ! check "$tmp"; then
  rm -f "$tmp"
  echo "error: SHA-256 mismatch for $FILE at revision $REVISION. File removed." >&2
  exit 1
fi
mv "$tmp" "$dest"
echo "ok: $dest verified"
