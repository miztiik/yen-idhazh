#!/usr/bin/env bash
# Run one arm of the pipeline test over the two articles the draw chose.
#
# Usage: run-pipeline-test-arm.sh <arm> <date>
#   arm   an id declared in `config/pipeline-tests.json`
#   date  the day the plan was written for
#
# Every arm runs the same plan, so the arms record the same two item ids and the
# numbers between them can be subtracted. The plan is copied in rather than
# written here: one arm minting its own would be one arm reading different
# articles, which is the whole failure this workflow exists to avoid.
#
# A script rather than three near-identical `run:` bodies. `CLAUDE.md` section 3
# asks for it, `shellcheck` reads this directory, and a test can execute this
# rather than grep a workflow.
#
# The faithfulness scorer is skipped. It is a second model download, it is the
# same in every arm so it cancels from every comparison here, and it is not what
# the two-call path is being measured for.
set -euo pipefail

if [ "$#" -ne 2 ]; then
	echo "usage: $0 <arm> <date>" >&2
	exit 2
fi

ARM="$1"
RUN_DATE="$2"
ARM_ROOT="backend/var/arms/${ARM}"

# The arm has to be one config declares. A typo would otherwise run the
# committed config under another arm's name and report it as that arm's number.
if [ ! -d "${ARM_ROOT}/config" ]; then
	echo "unknown arm ${ARM} - config/pipeline-tests.json declares no such id" >&2
	exit 2
fi

if [ ! -f backend/var/pipeline-tests/plan.json ]; then
	echo "no plan to run - the draw and the plan step come before every arm" >&2
	exit 2
fi

rm -rf "backend/var/run/${RUN_DATE}" "${ARM_ROOT}/run"
mkdir -p "backend/var/run/${RUN_DATE}"
cp backend/var/pipeline-tests/plan.json "backend/var/run/${RUN_DATE}/plan.json"

STARTED=$(date +%s)
python -m idhazh work \
	--date "${RUN_DATE}" \
	--config "${ARM_ROOT}/config" \
	--no-faithfulness
echo "arm ${ARM} took $(($(date +%s) - STARTED)) seconds"

mv "backend/var/run/${RUN_DATE}" "${ARM_ROOT}/run"
