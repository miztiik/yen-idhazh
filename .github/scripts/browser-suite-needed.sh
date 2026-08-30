#!/usr/bin/env bash
# Decide whether a change can move the published surface, and so whether the
# canary build and the browser suite have to run for it.
#
# The expensive half of the site gate is two extra builds, a Chromium install
# and ~340 browser tests. It answers one question - is what a reader sees still
# correct - and a change that cannot reach a published page cannot change that
# answer. The cheap half (`npm run check`, one build, the bundle gate, the site
# weight) still runs on everything, because `pip install -e .` puts every
# backend module on the import path and almost any of them can break it.
#
# The list is an allow-list rather than a skip-list on purpose: a path nobody
# thought about lands in "run it", which is the safe direction. It is only
# consulted for a pull request. A push to `main` and a manual dispatch always
# run, so a pull request the list was wrong about is caught on the merge commit
# rather than in a deploy.
#
# Writes one `browser=true|false` line, for $GITHUB_OUTPUT.
set -euo pipefail

: "${EVENT:=}"
: "${BASE:=}"
: "${HEAD:=}"

if [ "$EVENT" != "pull_request" ] || [ -z "$BASE" ] || [ -z "$HEAD" ]; then
	echo "browser=true"
	echo "console=true"
	exit 0
fi

# Anything a published page reads, plus the backend the canary day is built
# with: the builder itself, the contracts whose column lists the projection
# subtracts, the projection, and the extraction and sanitisation the raw attack
# text passes through on its way to a canary page.
PATTERN='^('
PATTERN+='frontend/'
PATTERN+='|config/'
PATTERN+='|schemas/'
PATTERN+='|tests/fixtures/'
PATTERN+='|state/'
PATTERN+='|backend/idhazh/contracts/'
PATTERN+='|backend/idhazh/(publish_telemetry|telemetry|sanitize|extract|taxonomy|retention|ledger|assemble|render)\.py'
PATTERN+='|backend/utilities/build_canary_day\.py'
PATTERN+='|[.]github/(workflows/ci\.yml|scripts/browser-suite-needed\.sh)'
PATTERN+=')'

# The console's own half. 233 of the 411 browser tests are its specs, and a
# reader never opens that page - so a change to a reading route, to the search
# index or to the on-device encoder buys the other 178 and stops. Everything a
# console panel draws from is here: its route, the chart engine, the shared
# components and server loaders it renders through, the ledgers and projections
# it reads at build time, the canary that stands in for them, and the config it
# takes its window and its bands from.
CONSOLE='^('
CONSOLE+='frontend/src/routes/console/'
CONSOLE+='|frontend/src/lib/(charts|components|server)/'
CONSOLE+='|frontend/tests/console'
CONSOLE+='|frontend/scripts/build-canary\.mjs'
CONSOLE+='|frontend/playwright\.config\.ts'
CONSOLE+='|config/'
CONSOLE+='|state/'
CONSOLE+='|frontend/public/telemetry/'
CONSOLE+='|backend/idhazh/contracts/'
CONSOLE+='|backend/idhazh/(publish_telemetry|telemetry|retention|ledger)\.py'
CONSOLE+='|backend/utilities/build_canary_day\.py'
CONSOLE+='|[.]github/(workflows/ci\.yml|scripts/browser-suite-needed\.sh)'
CONSOLE+=')'

changed=$(git diff --name-only "$BASE...$HEAD")

if printf '%s\n' "$changed" | grep -Eq "$PATTERN"; then
	echo "browser=true"
else
	echo "browser=false"
fi

if printf '%s\n' "$changed" | grep -Eq "$CONSOLE"; then
	echo "console=true"
else
	echo "console=false"
fi
