#!/usr/bin/env bash
# Install the declared optional Linux instruments without changing PMU permissions.
set -euo pipefail

: "${RUNNER_TEMP:?Cache tool installation requires a private runner directory}"
: "${GITHUB_PATH:?Cache tool installation requires the existing CI path file}"
config=config/host-cache-tools.json
jq -e '.packages | type == "array" and length > 0 and all(.[]; type == "string" and length > 0)' "$config" >/dev/null
jq -e '.perf_packages | type == "array" and length > 0 and all(.[]; type == "string" and length > 0)' "$config" >/dev/null
mapfile -t packages < <(jq -er '.packages[]' "$config")
mapfile -t perf_packages < <(jq -er '.perf_packages[]' "$config")
repository=$(jq -er '.multichase.repository' "$config")
revision=$(jq -er '.multichase.revision' "$config")
if ! [[ "$revision" =~ ^[a-f0-9]{40}$ ]]; then
  echo "host-cache-tools.multichase.revision must pin one commit" >&2
  exit 1
fi
tools="$RUNNER_TEMP/host-cache-tools"
source="$RUNNER_TEMP/host-cache-source"
log="$RUNNER_TEMP/host-cache-tools-install.log"
started=$SECONDS
stage=packages
trap 'printf "Declared optional cache tool installation failed at %s\n" "$stage" >&2; if test -f "$log"; then tail -n 20 "$log" >&2; fi' ERR
sudo apt-get update --quiet >"$log" 2>&1
perf_package=
for candidate in "${perf_packages[@]}"; do
  if apt-cache show "$candidate" >/dev/null 2>&1; then
    perf_package=$candidate
    break
  fi
done
if test -z "$perf_package"; then
  echo "No declared perf package is available from the configured Ubuntu repositories" >&2
  exit 1
fi
sudo apt-get install --yes --no-install-recommends -- "$perf_package" "${packages[@]}" >>"$log" 2>&1

# New images package perf separately. Older generic packages name an ABI link
# and an executable dependency; inspect those exact packages, never a tools-tree glob.
stage=perf_executable
perf_executable_package=$perf_package
if test "$perf_package" = linux-tools-generic; then
  perf_abi_package=$(dpkg-query -W -f='${Depends}' "$perf_package" | awk '{print $1}')
  perf_executable_package=$(dpkg-query -W -f='${Depends}' "$perf_abi_package" | tr ',' '\n' |
    awk '$1 ~ /^linux-tools-[0-9]/ && $1 !~ /-generic$/ {print $1; exit}')
  if ! [[ "$perf_executable_package" =~ ^linux-tools-[0-9][0-9a-z.-]*$ ]]; then
    echo "The declared generic Linux tools package has no named executable dependency" >&2
    exit 1
  fi
fi
perf_binary=$(dpkg-query -L "$perf_executable_package" | awk '/\/perf$/ {print; exit}')
if test -z "$perf_binary" || ! test -f "$perf_binary" || ! test -x "$perf_binary"; then
  echo "The declared Linux tools executable package contains no usable perf binary" >&2
  exit 1
fi
mkdir -p "$tools"
ln -s "$perf_binary" "$tools/perf"
perf_version=$("$tools/perf" --version)
if ! [[ "$perf_version" =~ ^perf\ version\ [0-9a-zA-Z.+_-]+$ ]]; then
  echo "The installed perf executable did not report a supported version format" >&2
  exit 1
fi
stage=multichase_source
git init --quiet "$source"
git -C "$source" fetch --quiet --depth 1 -- "$repository" "$revision"
git -C "$source" checkout --quiet --detach FETCH_HEAD
test "$(git -C "$source" rev-parse HEAD)" = "$revision"
stage=multichase_build
make --quiet -C "$source" multichase >>"$log" 2>&1
install "$source/multichase" "$tools/multichase"
printf '%s\n' "$tools" >>"$GITHUB_PATH"
printf '{"source_revision":"%s","perf_package":"%s","perf_version":"%s","install_seconds":%d,"multichase_binary_bytes":%d,"perf_binary_bytes":%d}\n' \
  "$revision" "$perf_package" "$perf_version" "$((SECONDS - started))" "$(wc -c <"$tools/multichase")" "$(wc -c <"$perf_binary")" \
  >"$RUNNER_TEMP/host-cache-tool-install.json"
