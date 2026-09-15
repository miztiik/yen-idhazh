#!/usr/bin/env bash
# Run one case of the pipeline test over the two articles the draw chose.
#
# Usage: run-pipeline-test-case.sh <case> <date>
#   case   an id declared in `config/pipeline-tests.json`
#   date  the day the plan was written for
#
# Every case runs the same plan, so the cases record the same two item ids and the
# numbers between them can be subtracted. The plan is copied in rather than
# written here: one case minting its own would be one case reading different
# articles, which is the whole failure this workflow exists to avoid.
#
# A script rather than three near-identical `run:` bodies. `CLAUDE.md` section 3
# asks for it, `shellcheck` reads this directory, and a test can execute this
# rather than grep a workflow.
#
# The faithfulness scorer is skipped. It is a second model download, it is the
# same in every case so it cancels from every comparison here, and it is not what
# the two-call path is being measured for.
set -euo pipefail

if [ "$#" -ne 2 ]; then
	echo "usage: $0 <case> <date>" >&2
	exit 2
fi

CASE="$1"
RUN_DATE="$2"
CASE_ROOT="backend/var/cases/${CASE}"

# The case has to be one config declares. A typo would otherwise run the
# committed config under another case's name and report it as that case's number.
if [ ! -d "${CASE_ROOT}/config" ]; then
	echo "unknown case ${CASE} - config/pipeline-tests.json declares no such id" >&2
	exit 2
fi

if [ ! -f backend/var/pipeline-tests/plan.json ]; then
	echo "no plan to run - the draw and the plan step come before every case" >&2
	exit 2
fi

rm -rf "backend/var/run/${RUN_DATE}" "${CASE_ROOT}/run"
mkdir -p "backend/var/run/${RUN_DATE}"
cp backend/var/pipeline-tests/plan.json "backend/var/run/${RUN_DATE}/plan.json"

STARTED=$(date +%s)
python -m idhazh work \
	--date "${RUN_DATE}" \
	--config "${CASE_ROOT}/config" \
	--no-faithfulness
echo "case ${CASE} took $(($(date +%s) - STARTED)) seconds"

mv "backend/var/run/${RUN_DATE}" "${CASE_ROOT}/run"
