#!/usr/bin/env bash
# Install the pinned llama.cpp build onto this runner, and nothing else.
#
# Held apart from `fetch-model-runtime.sh` because `probe.yml` asks the binary
# what it accepts and opens no weights at all. One script that always downloaded
# a multi-gigabyte GGUF would turn a one-minute probe into the slowest question
# in the repository, and a `WEIGHTS_FILE` allowed to be empty would make the
# refusals every other caller depends on optional.
#
# It takes no arguments and reads one thing from the environment, so no value is
# pasted into this program before it is a value (Guardrail #11):
#   GITHUB_TOKEN  looks the pinned release up
#
# Source it or run it. `fetch-model-runtime.sh` sources it, so the pin it reads
# lands in the same shell the weights half runs in.
set -euo pipefail

: "${GITHUB_TOKEN:?GITHUB_TOKEN must be set to look the pinned release up}"

# shellcheck source=.github/scripts/llama-cpp-pin.sh
. .github/scripts/llama-cpp-pin.sh

mkdir -p backend/bin

# Authenticated, because every shard asks at once and anonymous api.github.com
# allows 60 requests an hour - a ceiling of eight shards makes that eight askers
# on a cold cache, not four.
URL=$(curl -fsS -H "Authorization: Bearer ${GITHUB_TOKEN}" \
	"https://api.github.com/repos/ggml-org/llama.cpp/releases/tags/${LLAMA_CPP_BUILD}" \
	| jq -r --arg asset "$LLAMA_CPP_ASSET" \
		'if type=="object" then ([.assets[] | select(.name == $asset)][0].browser_download_url // "") else "" end')
if [ -z "$URL" ] || [ "$URL" = "null" ]; then
	echo "pinned llama.cpp asset not found: ${LLAMA_CPP_BUILD}/${LLAMA_CPP_ASSET}" >&2
	exit 1
fi
curl -fsSL --retry 3 --retry-all-errors -o llama.tar.gz "$URL"
echo "${LLAMA_CPP_SHA256}  llama.tar.gz" | sha256sum --check
mkdir -p llama && tar -xzf llama.tar.gz -C llama
# `cp -a`, never `find -type f`: these builds ship versioned shared objects as
# symlinks, and a symlink is not a file to `find`. The whole directory, because
# a binary copied without its shared objects dies at exec with a 127 that names
# a library rather than the mistake.
SRC=$(dirname "$(find llama -type f -name 'llama-server' | head -1)")
cp -a "$SRC"/. backend/bin/
chmod +x backend/bin/llama-server
