#!/usr/bin/env bash
# Start llama-server for one role and prove the process survived the start.
#
# Two jobs do this: `work` serves the summarizer, `route` serves the router.
# The bodies were 80.6 percent identical inline shell, differing only in which
# `models.<role>` config block to read and what to call the log and the pid
# file. Two copies of a start sequence drift, and the copy that drifts is
# whichever one nobody looked at this week - so there is one, and a test runs
# it rather than reading it.
#
# The argv itself is still built by `idhazh.llm.server.server_argv`, which is
# the single place a llama-server flag may be spelled (Rule #6). This script
# never names one.
#
# Usage: start-llama-server.sh <role> <name>
#   role  the attribute on settings.app.models - `summarize` or `visual_planner`
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
	summarize | visual_planner) ;;
	*)
		echo "unknown role ${ROLE} - expected summarize or visual_planner" >&2
		exit 2
		;;
esac

: "${LLAMA_WEIGHTS:?LLAMA_WEIGHTS must name the weights file}"
: "${LLAMA_PORT:?LLAMA_PORT must name the loopback port}"

chmod +x backend/bin/llama-server
mkdir -p backend/var

LLAMA_ROLE="$ROLE" python - <<'PY' > backend/var/llama-argv
import os
import sys
from pathlib import Path

from idhazh import config
from idhazh.llm.server import server_argv

settings = config.load(Path("config"))
argv = server_argv(
    binary=Path("backend/bin/llama-server"),
    weights=Path(os.environ["LLAMA_WEIGHTS"]),
    model=getattr(settings.app.models, os.environ["LLAMA_ROLE"]),
    inference=settings.app.models.inference,
    port=int(os.environ["LLAMA_PORT"]),
)
sys.stdout.write("\0".join(argv) + "\0")
PY

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
