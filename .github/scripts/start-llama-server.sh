#!/usr/bin/env bash
# Start llama-server for one role and prove the process survived the start.
#
# One job does this today: `work` serves the summarizer. It was two until plan
# 11 row #6 retired the visual planner, and the bodies were 80.6 percent
# identical inline shell, differing only in which `models.<role>` config block
# to read and what to call the log and the pid file. The script stays a script
# rather than folding back inline: a test runs it rather than reading it, and
# `shellcheck` covers it.
#
# The argv itself is still built by `idhazh.llm.server.server_argv`, which is
# the single place a llama-server flag may be spelled (Guardrail #6). This script
# never names one.
#
# Usage: start-llama-server.sh <role> <name>
#   role  the attribute on settings.models - `summarize`
#   name  the stem for <name>.log and <name>.pid
#
# Reads LLAMA_WEIGHTS and LLAMA_PORT from the environment.
set -euo pipefail

if [ "$#" -ne 2 ]; then
	echo "usage: $0 <role> <name>" >&2
	exit 2
fi

ROLE="$1"
NAME="$2"

case "$ROLE" in
	summarize) ;;
	*)
		echo "unknown role ${ROLE} - expected summarize" >&2
		exit 2
		;;
esac

: "${LLAMA_WEIGHTS:?LLAMA_WEIGHTS must name the weights file}"
: "${LLAMA_PORT:?LLAMA_PORT must name the loopback port}"

echo "::group::Locked-memory limit before model startup"
printf 'ulimit -l before (KiB, or unlimited): '
ulimit -l 2>&1 || echo "::warning::Could not read the current locked-memory limit."
printf 'ulimit -Hl (KiB, or unlimited): '
ulimit -Hl 2>&1 || echo "::warning::Could not read the hard locked-memory limit."
echo "Running: sudo prlimit --memlock=unlimited --pid $$"
if sudo prlimit --memlock=unlimited --pid "$$"; then
	echo "Locked-memory limit raised."
else
	echo "::warning::Could not raise the locked-memory limit; model memory may remain unlocked."
fi
printf 'ulimit -l after (KiB, or unlimited): '
ulimit -l 2>&1 || echo "::warning::Could not read the effective locked-memory limit."
echo "::endgroup::"

chmod +x backend/bin/llama-server
mkdir -p backend/var

LLAMA_ROLE="$ROLE" python3 backend/utilities/llama_argv.py \
	--config-root config \
	--role "$ROLE" > backend/var/llama-argv

mapfile -d '' LLAMA_ARGV < backend/var/llama-argv
echo "starting: ${LLAMA_ARGV[*]}"
LD_LIBRARY_PATH=backend/bin nohup "${LLAMA_ARGV[@]}" > "${NAME}.log" 2>&1 &
echo "$!" > "${NAME}.pid"
sleep 2
kill -0 "$(cat "${NAME}.pid")" || {
	echo "${NAME} exited before it could answer" >&2
	tail -50 "${NAME}.log" >&2
	exit 1
}
