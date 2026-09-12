#!/usr/bin/env bash
# Sample what this job holds in memory, once every 15 seconds, until the server
# it was given goes away.
#
# Two jobs of the daily run stand a llama-server up - `work` serves the
# summarizer and `visuals` serves the visual planner - and both need the same
# reading, so it is written once here rather than pasted into two `run:` bodies
# (`CLAUDE.md` section 3). Everything it writes is read back by
# `RuntimeCountersRow.from_metrics_text`, which finds each column by name off
# this file's own header.
#
# `set -u` and not `set -e`: a /proc entry that vanishes between the glob and
# the read is the normal case on a busy host, and the sampler has to outlive it.
#
# VmHWM is the high-water mark a process reached and VmRSS is what it holds
# right now. Both marks are taken for python as well as for llama-server,
# because llama-server is not the whole job: the stage that reads the feeds,
# extracts the text and scores the summaries runs beside it on the same 16 GB.
# Reading only VmRSS there made the recorded python figure a LOWER bound - a
# 15-second sampler misses a spike between two samples - and a lower bound is
# the unsafe direction for a headroom decision.
#
# `python_vmhwm_kb` is appended at the END of the row rather than beside its
# VmRSS sibling. A file written before it existed then still parses, and nothing
# that reads `python_procs` by position moves.
#
# `python-procs.tsv` names them, one row per process per sample. A count and a
# sum cannot say what was counted, and that is not a small gap: the four
# captures under `tests/fixtures/runtime/` record three python processes at
# every peak, and two of the three are already running before the job's own
# python starts. Those two hold 63,432 to 69,780 kB across 1,261 samples, so
# about 4 percent of the recorded python figure belongs to something the job did
# not start - and nothing on the row says what.
#
# The executable and three argv fields, not the whole command line. `comm` is
# `python3` for every one of them, which names nothing; the executable path plus
# argv 1 to 3 separates a hosted-tool-cache `python -m idhazh` from a
# distribution `/usr/bin/python3 -u /usr/sbin/...` and stops there, so a secret
# further along a command line is never copied into an artifact (`CLAUDE.md`
# section 1b).
#
# `mem_total_kb`, `mem_available_kb`, `committed_as_kb` and
# `cgroup_current_bytes` are the machine's own account of itself, taken beside
# the two process marks from 2026-09-09. Everything above measures processes,
# and adding two process marks together does not give the memory the machine
# committed: no `-lm` flag is passed, so llama.cpp maps the weights and their
# resident pages count in every RSS figure as file-backed and evictable, and
# pages two processes share are counted twice. `MemAvailable` is the kernel's
# own estimate of what a new allocation could get, which is the question a
# headroom decision actually asks; `Committed_AS` is what has been promised;
# `MemTotal` is what the machine has.
#
# `absent` is written in full wherever a file does not exist. An empty cell
# reads as zero, and zero available memory is a very different claim from no
# reading.
set -u

pid="$1"

meminfo_kb() {
  [ -r /proc/meminfo ] || { printf 'absent\n'; return; }
  awk -v key="$1:" \
    '$1 == key { print $2; seen = 1; exit } END { if (!seen) print "absent" }' \
    /proc/meminfo
}

cgroup_current() {
  for file in /sys/fs/cgroup/memory.current \
              /sys/fs/cgroup/memory/memory.usage_in_bytes; do
    if [ -r "$file" ]; then cat "$file"; return; fi
  done
  printf 'absent\n'
}

printf 'ts\tllama_vmrss_kb\tllama_vmhwm_kb\tpython_vmrss_kb\tpython_procs\tpython_vmhwm_kb' > rss-samples.tsv
printf '\tmem_total_kb\tmem_available_kb\tcommitted_as_kb\tcgroup_current_bytes\n' >> rss-samples.tsv
printf 'ts\tpid\tcomm\tvmrss_kb\tvmhwm_kb\texe\targs\n' > python-procs.tsv

while kill -0 "$pid" 2>/dev/null; do
  now=$(date -u +%FT%TZ)
  rss=$(awk '/^VmRSS:/ {print $2}' "/proc/$pid/status" 2>/dev/null || true)
  hwm=$(awk '/^VmHWM:/ {print $2}' "/proc/$pid/status" 2>/dev/null || true)
  python_kb=0
  python_hwm_kb=0
  python_n=0
  for proc in /proc/[0-9]*; do
    comm=$(cat "$proc/comm" 2>/dev/null || true)
    case "$comm" in
      python*) ;;
      *) continue ;;
    esac
    kb=$(awk '/^VmRSS:/ {print $2}' "$proc/status" 2>/dev/null || true)
    [ -n "$kb" ] || continue
    proc_hwm=$(awk '/^VmHWM:/ {print $2}' "$proc/status" 2>/dev/null || true)
    python_kb=$((python_kb + kb))
    python_hwm_kb=$((python_hwm_kb + ${proc_hwm:-$kb}))
    python_n=$((python_n + 1))
    exe=$(readlink "$proc/exe" 2>/dev/null || true)
    args=$(tr '\0\t\n' '   ' < "$proc/cmdline" 2>/dev/null | cut -d' ' -f2-4 || true)
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
      "$now" "${proc##*/}" "$comm" "$kb" "${proc_hwm:-}" "${exe:-}" "${args:-}" \
      >> python-procs.tsv
  done
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$now" "${rss:-}" "${hwm:-}" "$python_kb" "$python_n" "$python_hwm_kb" \
    "$(meminfo_kb MemTotal)" "$(meminfo_kb MemAvailable)" \
    "$(meminfo_kb Committed_AS)" "$(cgroup_current)" >> rss-samples.tsv
  sleep 15
done
