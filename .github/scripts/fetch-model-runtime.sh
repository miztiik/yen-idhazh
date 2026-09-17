#!/usr/bin/env bash
# Install the pinned llama.cpp build, then download the weights a job is about
# to open.
#
# The pin is `llama-cpp-pin.sh`, sourced below, and a workflow that calls this
# carries no copy of it. Four workflows each spell that pin out and fetch the
# build themselves; this is the step they collapse into, one caller at a time.
#
# It takes no arguments. Everything it needs arrives through the environment,
# so no value is pasted into this program before it is a value (Guardrail #11):
#   GITHUB_TOKEN      looks the pinned release up
#   WEIGHTS_REPO      the hub repository holding the weights
#   WEIGHTS_REVISION  the commit, never a branch name
#   WEIGHTS_FILE      the .gguf filename
#   DRAFT_REPO, DRAFT_REVISION, DRAFT_FILE  the draft head, or empty
#
# It checks the ARCHIVE against the pinned digest. The weights digest is a
# config fact rather than a pin, and the caller checks it in a step carrying no
# `if:` - a restored cache entry is the one case where nobody watched the bytes
# arrive.
set -euo pipefail

if [ "$#" -ne 0 ]; then
	echo "usage: $0   (every input arrives through the environment)" >&2
	exit 2
fi

# shellcheck source=.github/scripts/llama-cpp-pin.sh
. .github/scripts/llama-cpp-pin.sh

: "${GITHUB_TOKEN:?GITHUB_TOKEN must be set to look the pinned release up}"
: "${WEIGHTS_REPO:?WEIGHTS_REPO must name the hub repository}"
: "${WEIGHTS_REVISION:?WEIGHTS_REVISION must name the commit}"
: "${WEIGHTS_FILE:?WEIGHTS_FILE must name the weights file}"

mkdir -p backend/bin backend/models

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

# The pinned commit, never a branch, and `-f` so an HTTP error body cannot be
# written into the weights file and then saved under the cache key.
curl -fsSL --retry 3 --retry-all-errors \
	-o "backend/models/${WEIGHTS_FILE}" \
	"https://huggingface.co/${WEIGHTS_REPO}/resolve/${WEIGHTS_REVISION}/${WEIGHTS_FILE}?download=true"

# The draft head, where the entry declares one. The server loads it at start-up,
# so a model that declares one and cannot find it does not serve at all.
if [ -n "${DRAFT_FILE:-}" ]; then
	: "${DRAFT_REPO:?DRAFT_REPO must name the hub repository holding the head}"
	: "${DRAFT_REVISION:?DRAFT_REVISION must name the commit holding the head}"
	curl -fsSL --retry 3 --retry-all-errors \
		-o "backend/models/${DRAFT_FILE}" \
		"https://huggingface.co/${DRAFT_REPO}/resolve/${DRAFT_REVISION}/${DRAFT_FILE}?download=true"
fi
