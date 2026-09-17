#!/usr/bin/env bash
# Install the pinned llama.cpp build, then download the weights a job is about
# to open.
#
# The build half is `install-llama-runtime.sh`, sourced below, and the pin that
# script reads is `llama-cpp-pin.sh`. A workflow that calls this carries neither.
#
# It takes no arguments. Everything it needs arrives through the environment,
# so no value is pasted into this program before it is a value (Guardrail #11):
#   GITHUB_TOKEN      looks the pinned release up
#   WEIGHTS_REPO      the hub repository holding the weights
#   WEIGHTS_REVISION  the commit, never a branch name
#   WEIGHTS_FILE      the .gguf filename
#   DRAFT_REPO, DRAFT_REVISION, DRAFT_FILE  the draft head, or empty
#
# The weights refusals come before the install, so a caller that forgot a ref
# fails in a second rather than after unpacking a runtime it will not use.
#
# The ARCHIVE is checked against the pinned digest by the script this sources.
# The weights digest is a config fact rather than a pin, and the caller checks
# it in a step carrying no `if:` - a restored cache entry is the one case where
# nobody watched the bytes arrive.
set -euo pipefail

if [ "$#" -ne 0 ]; then
	echo "usage: $0   (every input arrives through the environment)" >&2
	exit 2
fi

: "${WEIGHTS_REPO:?WEIGHTS_REPO must name the hub repository}"
: "${WEIGHTS_REVISION:?WEIGHTS_REVISION must name the commit}"
: "${WEIGHTS_FILE:?WEIGHTS_FILE must name the weights file}"

# shellcheck source=.github/scripts/install-llama-runtime.sh
. .github/scripts/install-llama-runtime.sh

mkdir -p backend/models

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
