#!/usr/bin/env bash
# The one home of the llama.cpp pin: which build, which asset, and the digest of
# the archive that asset is.
#
# It used to be written in six places that had to change together - five
# workflow `env:` blocks and nothing that read them against each other - and
# eight fetch steps spelled the download. Miss one on an upgrade and a case runs
# on a build production does not run, which is a measurement about a binary
# nobody ships (Guardrail #10).
#
# Two ways to read it, and neither takes an argument.
#   source it   assigns all three. `fetch-model-runtime.sh` does this.
#   run it      prints the build as `key=value`, for a step to publish. A
#               weights cache key names the build and the cache step runs
#               before the fetch, so the pin has to be readable without
#               downloading anything.
#
# The SHA-256 is the release API's own `digest` for that asset. It was confirmed
# on 2026-08-25 by downloading the 16,377,727-byte archive and hashing it.
#
# SC2034 is off for the whole file: assigning for somebody else is what a
# sourced file is, so "appears unused" is true here and means nothing.
# shellcheck disable=SC2034
set -euo pipefail

LLAMA_CPP_BUILD=b10598
LLAMA_CPP_ASSET="llama-${LLAMA_CPP_BUILD}-bin-ubuntu-x64.tar.gz"
LLAMA_CPP_SHA256=d77a09db4165f8850b513629ed0ffeaab7851bb03e7cc3870b74e721f894694c

# Only when run, never when sourced. A sourced copy that printed would append a
# stray line to whatever its caller was writing.
if [ "${BASH_SOURCE[0]}" = "$0" ]; then
	echo "llama_cpp_build=${LLAMA_CPP_BUILD}"
fi
