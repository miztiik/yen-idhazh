#!/usr/bin/env bash
set -euo pipefail

exec node "$(dirname "$0")/../../frontend/scripts/test-scope.ts" --ci
