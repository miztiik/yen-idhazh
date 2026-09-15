#!/usr/bin/env bash
# Which pages a change touched, for `doc_load.py --changed`.
#
# Prints the two `$GITHUB_OUTPUT` lines the docs job reads. It never fails a
# run: this measures and gates nothing, so a range it cannot resolve answers
# "no pages" rather than reddening a check.
set -euo pipefail

empty=0000000000000000000000000000000000000000

if [ -z "${BASE:-}" ] || [ "${BASE}" = "${empty}" ] || [ -z "${HEAD:-}" ]; then
  echo "any=false"
  exit 0
fi

# A force-push or a first push on a branch leaves a base this clone cannot
# resolve. Asking git for a range it does not hold is a failure, not an answer.
if ! git cat-file -e "${BASE}^{commit}" 2>/dev/null; then
  echo "any=false"
  exit 0
fi

paths=$(git diff --name-only --diff-filter=d "${BASE}" "${HEAD}" -- '*.md' | tr '\n' ' ')
paths=${paths% }

if [ -z "${paths}" ]; then
  echo "any=false"
  exit 0
fi

echo "any=true"
echo "paths=${paths}"
