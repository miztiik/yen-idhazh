#!/usr/bin/env bash
# Build the declared native instruments without Python execution, modules or kernel changes.
set -euo pipefail
export LC_ALL=C

: "${RUNNER_TEMP:?Cache tool installation requires a private runner directory}"
: "${GITHUB_PATH:?Cache tool installation requires the existing CI path file}"
config=config/host-cache-tools.json
jq -e '.packages | type == "array" and length > 0 and all(.[]; type == "string" and length > 0)' "$config" >/dev/null
jq -e '.build_jobs | type == "number" and . > 0 and floor == .' "$config" >/dev/null
jq -e '.perf.make_options | index("NO_LIBPYTHON=1") != null and index("NO_JEVENTS=1") != null
  and index("PYTHON=/usr/bin/false") != null and index("PYTHON_CONFIG=/usr/bin/false") != null' "$config" >/dev/null
mapfile -t packages < <(jq -er '.packages[]' "$config")
mapfile -t perf_paths < <(jq -er '.perf.checkout_paths[]' "$config")
mapfile -t perf_options < <(jq -er '.perf.make_options[]' "$config")
jobs=$(jq -er '.build_jobs' "$config")
perf_repository=$(jq -er '.perf.repository' "$config")
perf_revision=$(jq -er '.perf.revision' "$config")
repository=$(jq -er '.multichase.repository' "$config")
revision=$(jq -er '.multichase.revision' "$config")
if ! [[ "$revision" =~ ^[a-f0-9]{40}$ && "$perf_revision" =~ ^[a-f0-9]{40}$ ]]; then
  echo "host-cache-tools native revisions must pin one official commit each" >&2
  exit 1
fi
tools="$RUNNER_TEMP/host-cache-tools"
source="$RUNNER_TEMP/host-cache-source"
perf_source="$RUNNER_TEMP/host-cache-perf-source"
log="$RUNNER_TEMP/host-cache-tools-install.log"
apt_log="$RUNNER_TEMP/host-cache-packages.log"
trace="$RUNNER_TEMP/host-cache-perf-build-executions"
started=$SECONDS
stage=packages
trap 'printf "Declared native cache tool build failed at %s\n" "$stage" >&2; if test -f "$log"; then tail -n 25 "$log" >&2; fi' ERR
sudo apt-get update --quiet >"$log" 2>&1
apt-get --simulate install --no-install-recommends -- "${packages[@]}" >"$apt_log" 2>&1
if awk '$1 == "Inst" && $2 ~ /^(python[0-9]|libpython)/ { found=1 } END { exit !found }' "$apt_log"; then
  echo "Declared native build dependencies would install or update Python packages" >&2
  exit 1
fi
sudo apt-get install --yes --no-install-recommends -- "${packages[@]}" >"$apt_log" 2>&1
mapfile -t added_packages < <(awk '/^Selecting previously unselected package / { sub(/[.]$/, "", $5); print $5 }' "$apt_log")
if ((${#added_packages[@]})); then
  added_json=$(dpkg-query -W -f='${binary:Package}\t${Version}\t${Installed-Size}\n' "${added_packages[@]}" |
    jq -Rn '[inputs | split("\t") | {name: .[0], version: .[1], installed_kib: (.[2] | tonumber)}]')
else
  added_json='[]'
fi
mkdir -p "$tools"
stage=perf_source
perf_fetch_started=$SECONDS
git init --quiet "$perf_source"
git -C "$perf_source" remote add origin "$perf_repository"
git -C "$perf_source" -c remote.origin.promisor=true -c remote.origin.partialclonefilter=blob:none \
  fetch --quiet --depth 1 --filter=blob:none origin "$perf_revision"
git -C "$perf_source" config remote.origin.promisor true
git -C "$perf_source" config remote.origin.partialclonefilter blob:none
git -C "$perf_source" sparse-checkout set --no-cone -- "${perf_paths[@]}"
git -C "$perf_source" checkout --quiet --detach FETCH_HEAD
test "$(git -C "$perf_source" rev-parse HEAD)" = "$perf_revision"
perf_fetch_seconds=$((SECONDS - perf_fetch_started))
stage=perf_build
perf_build_started=$SECONDS
mkdir -p "$trace"
# One trace per owned build process prevents interleaved exec lines hiding an interpreter.
if strace -ff -e trace=execve -s 512 -o "$trace/exec" \
  make --quiet -C "$perf_source/tools/perf" -j "$jobs" "${perf_options[@]}" perf >>"$log" 2>&1; then
  perf_build_status=0
else
  perf_build_status=$?
fi
perf_build_seconds=$((SECONDS - perf_build_started))
trace_files=("$trace"/exec.*)
test -s "${trace_files[0]}"
python_exec_count=$(awk '/execve\("[^"]*(\/python[0-9.]*(-config)?|[.]py)"/ && /[=] 0$/ { count++ } END { print count+0 }' "${trace_files[@]}")
if test "$python_exec_count" -ne 0; then
  printf 'Official perf build executed Python %s times; this is not a compliant instrument\n' "$python_exec_count" >&2
  exit 1
fi
if test "$perf_build_status" -ne 0; then
  printf 'Official no-Python perf build failed with exit status %s\n' "$perf_build_status" >&2
  tail -n 25 "$log" >&2
  exit "$perf_build_status"
fi
install "$perf_source/tools/perf/perf" "$tools/perf"
readelf -d "$tools/perf" >"$RUNNER_TEMP/host-cache-perf-elf.txt"
mapfile -t perf_libraries < <(sed -nE 's/.*Shared library: \[([^]]+)\].*/\1/p' "$RUNNER_TEMP/host-cache-perf-elf.txt")
if printf '%s\n' "${perf_libraries[@]}" | grep -qi python; then
  echo "Built perf still links Python; no replacement binary is accepted" >&2
  exit 1
fi
perf_libraries_json=$(printf '%s\n' "${perf_libraries[@]}" | jq -Rn '[inputs | select(length > 0)]')
runtime_libraries_json='[]'
if ((${#perf_libraries[@]})); then
  runtime_links=$(ldd "$tools/perf")
  if printf '%s\n' "$runtime_links" | grep -qiE 'python|not found'; then
    echo "Built perf has a Python or missing runtime dependency" >&2
    exit 1
  fi
  runtime_libraries_json=$(printf '%s\n' "$runtime_links" | awk '{name=$1; sub(/^.*\//, "", name); print name}' |
    jq -Rn '[inputs | select(length > 0)]')
fi
perf_version=$("$tools/perf" --version)
if ! [[ "$perf_version" =~ ^perf\ version\ [0-9a-zA-Z.+_-]+$ ]]; then
  echo "The built perf executable did not report a supported version format" >&2
  exit 1
fi
stage=multichase_source
git init --quiet "$source"
git -C "$source" fetch --quiet --depth 1 -- "$repository" "$revision"
git -C "$source" checkout --quiet --detach FETCH_HEAD
test "$(git -C "$source" rev-parse HEAD)" = "$revision"
stage=multichase_build
multichase_build_started=$SECONDS
make --quiet -C "$source" multichase >>"$log" 2>&1
multichase_build_seconds=$((SECONDS - multichase_build_started))
install "$source/multichase" "$tools/multichase"
printf '%s\n' "$tools" >>"$GITHUB_PATH"
jq -n --arg source_revision "$revision" --arg perf_source_revision "$perf_revision" --arg perf_version "$perf_version" \
  --argjson install_seconds "$((SECONDS - started))" --argjson perf_fetch_seconds "$perf_fetch_seconds" \
  --argjson perf_build_seconds "$perf_build_seconds" --argjson multichase_build_seconds "$multichase_build_seconds" \
  --argjson multichase_binary_bytes "$(wc -c <"$tools/multichase")" --argjson perf_binary_bytes "$(wc -c <"$tools/perf")" \
  --argjson python_execution_count "$python_exec_count" --argjson perf_elf_libraries "$perf_libraries_json" \
  --argjson perf_runtime_libraries "$runtime_libraries_json" \
  --argjson added_os_packages "$added_json" \
  '{source_revision: $source_revision, perf_source_revision: $perf_source_revision, perf_version: $perf_version,
    install_seconds: $install_seconds, perf_fetch_seconds: $perf_fetch_seconds, perf_build_seconds: $perf_build_seconds,
    multichase_build_seconds: $multichase_build_seconds, multichase_binary_bytes: $multichase_binary_bytes,
    perf_binary_bytes: $perf_binary_bytes, python_execution_count: $python_execution_count,
    perf_elf_libraries: $perf_elf_libraries, perf_runtime_libraries: $perf_runtime_libraries,
    added_os_packages: $added_os_packages}' \
  >"$RUNNER_TEMP/host-cache-tool-install.json"
