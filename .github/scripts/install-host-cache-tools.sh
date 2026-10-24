#!/usr/bin/env bash
# Install the declared optional Linux instruments without changing PMU permissions.
set -euo pipefail

: "${RUNNER_TEMP:?Cache tool installation requires a private runner directory}"
: "${GITHUB_PATH:?Cache tool installation requires the existing CI path file}"
config=config/host-cache-tools.json
mapfile -t packages < <(jq -er '.packages[]' "$config")
repository=$(jq -er '.multichase.repository' "$config")
revision=$(jq -er '.multichase.revision' "$config")
tools="$RUNNER_TEMP/host-cache-tools"
source="$RUNNER_TEMP/host-cache-source"
log="$RUNNER_TEMP/host-cache-tools-install.log"
started=$SECONDS
stage=packages
trap 'printf "Declared optional cache tool installation failed at %s\n" "$stage" >&2; if test -f "$log"; then tail -n 20 "$log" >&2; fi' ERR
sudo apt-get update --quiet >"$log" 2>&1
sudo apt-get install --yes --no-install-recommends "${packages[@]}" >>"$log" 2>&1

# The distribution's /usr/bin/perf wrapper requires an exact kernel package.
# Use the installed generic package's real executable, not that wrapper.
stage=perf_executable
perf_package=$(dpkg-query -W -f='${Depends}' linux-tools-generic | awk '{print $1}')
perf_binary=$(dpkg-query -L "$perf_package" | awk '/\/perf$/ {print; exit}')
test -n "$perf_binary" && test -x "$perf_binary"
mkdir -p "$tools"
ln -s "$perf_binary" "$tools/perf"
stage=multichase_source
git init --quiet "$source"
git -C "$source" fetch --quiet --depth 1 "$repository" "$revision"
git -C "$source" checkout --quiet --detach FETCH_HEAD
test "$(git -C "$source" rev-parse HEAD)" = "$revision"
stage=multichase_build
make --quiet -C "$source" multichase >>"$log" 2>&1
install "$source/multichase" "$tools/multichase"
printf '%s\n' "$tools" >>"$GITHUB_PATH"
printf '{"source_revision":"%s","install_seconds":%d,"multichase_binary_bytes":%d,"perf_binary_bytes":%d}\n' \
  "$revision" "$((SECONDS - started))" "$(wc -c <"$tools/multichase")" "$(wc -c <"$perf_binary")" \
  >"$RUNNER_TEMP/host-cache-tool-install.json"
