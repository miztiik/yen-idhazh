"""What does this job hold in memory while the server it was given is alive?

Three verbs, one program. `start-sampler` launches the loop and returns,
`sample` is the loop, and `summarize` reads back what the loop wrote.

It was 108 lines of shell writing two tab-separated files, and an `awk` program
inside a workflow step read one of them back. A tab-separated row is a format
this repository invented so that shell could hold a structure; JSON Lines is one
the standard library already reads, and it carries `null` - which a cell cannot,
because an empty cell reads as zero and zero available memory is a very
different claim from no reading. It also ends the whole class of defect the old
reader was written against: a key is a key wherever it sits on the line, so no
column can move.

The `/proc` read is shared with `runtime_sweep.py`, which has sampled a server
the same way since before this was a script. `read_status` is that one read, and
the dict it hands back is a bench payload's shape rather than this module's.

**Both marks, for python as well as for llama-server.** llama-server is not the
whole job: the stage that reads the feeds, extracts the text and scores the
summaries runs beside it on the same 16 GB. `VmHWM` is the high-water mark a
process reached and `VmRSS` is what it holds right now, and reading only `VmRSS`
made the recorded python figure a LOWER bound - a lower bound is the unsafe
direction for a headroom decision.

**The roll-call beside the count.** A count and a sum cannot say what was
counted, and that is not a small gap here: the four captures under
`tests/fixtures/runtime/` record three python processes at every peak, and two
of the three are already running before the job's own python starts. Those two
hold 63,432 to 69,780 kB across 1,261 samples, so about 4 percent of the
recorded python figure belongs to something the job did not start.

**The executable and three argv fields, never the whole command line.** `comm`
is `python3` for every one of them, which names nothing; the executable path
plus argv 1 to 3 separates a hosted-tool-cache `python -m idhazh` from a
distribution `/usr/bin/python3 -u /usr/sbin/...` and stops there, so a secret
further along a command line is never copied into an artifact (CLAUDE.md
section 1b).

**The machine's own account of itself** is taken beside the two process marks,
because adding two process marks together does not give the memory the machine
committed: no `-lm` flag is passed, so llama.cpp maps the weights and their
resident pages count in every resident-set figure as file-backed and evictable,
and pages two processes share are counted twice. `MemAvailable` is the kernel's
estimate of what a new allocation could get, which is the question a headroom
decision actually asks; `Committed_AS` is what has been promised; `MemTotal` is
what the machine has.

Nothing here raises on a `/proc` entry that vanished between the walk and the
read. That is the normal case on a busy host, and a sampler has to outlive it.
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
import time
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import IO, Any, Final

LOG: Final = logging.getLogger("memory_sampler")

#: Where the kernel publishes what every process holds.
PROC: Final = Path("/proc")

#: Where the cgroup's current charge is read from, first one that is there. The
#: first path is cgroup v2 and the second v1; a runner has one of the two.
CGROUP_CURRENT_PATHS: Final = (
    Path("/sys/fs/cgroup/memory.current"),
    Path("/sys/fs/cgroup/memory/memory.usage_in_bytes"),
)

#: The three rows of `/proc/meminfo` a headroom decision reads, and what each
#: one is called on a sample record.
MEMINFO_KEYS: Final = {
    "MemTotal": "mem_total_kb",
    "MemAvailable": "mem_available_kb",
    "Committed_AS": "committed_as_kb",
}

#: Where the loop writes. One JSON object a line, so a file still being written
#: parses up to its last whole line.
RSS_SAMPLE_FILE: Final = Path("rss-samples.jsonl")

PYTHON_PROCS_FILE: Final = Path("python-procs.jsonl")

#: The stem for `<name>.log` and `<name>.pid`.
DEFAULT_NAME: Final = "memory-sampler"

#: How often the loop wakes. Fifteen seconds is what the shell slept, and it is
#: a floor on what a reading can see rather than a preference: a spike shorter
#: than one interval is invisible to `VmRSS`, which is why `VmHWM` is recorded
#: beside it - the kernel holds the peak the sampler slept through.
SAMPLE_EVERY_SECONDS: Final = 15.0

#: How long the launched child gets to die before the parent calls the launch
#: good. A loop handed a pid nothing owns is gone in well under a second, and
#: the point of this shape is that such a launch is loud rather than a green
#: step with a pid file naming a process that never sampled anything.
START_GRACE_SECONDS: Final = 2.0

#: How much of the child's log a refused launch carries out with it.
LOG_TAIL_LINES: Final = 20

#: Which argv fields past the program name reach the roll-call.
ARGV_FIELDS: Final = slice(1, 4)


def read_status(pid: int, *, proc_root: Path = PROC) -> dict[str, str]:
    """The process's resident set, as the kernel reports it this second.

    `runtime_sweep.py` calls this too and keeps what it returns, so the values
    carry the kernel's own `kB` suffix: `measure_llm.py` parses them back out of
    a committed bench summary, which makes this dict a payload shape rather than
    a convenience.
    """
    status = proc_root / str(pid) / "status"
    values: dict[str, str] = {}
    if not status.exists():
        return values
    for line in status.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith(("VmRSS:", "VmHWM:")):
            key, value = line.split(":", 1)
            values[key] = value.strip()
    return values


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _text(path: Path) -> str | None:
    """One small file, or nothing at all when it went away mid-walk."""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _kilobytes(values: Mapping[str, str], key: str) -> int | None:
    """`1234 kB` as a number, or nothing at all when that row was not there."""
    fields = (values.get(key) or "").split()
    return int(fields[0]) if fields and fields[0].isdigit() else None


def _meminfo(proc_root: Path) -> dict[str, int | None]:
    """The machine's three figures, keyed as a sample record spells them."""
    found: dict[str, int | None] = dict.fromkeys(MEMINFO_KEYS.values())
    text = _text(proc_root / "meminfo")
    if text is None:
        return found
    for line in text.splitlines():
        key, _, rest = line.partition(":")
        if key in MEMINFO_KEYS:
            fields = rest.split()
            found[MEMINFO_KEYS[key]] = int(fields[0]) if fields and fields[0].isdigit() else None
    return found


def _cgroup_current(paths: Sequence[Path]) -> int | None:
    for path in paths:
        text = _text(path)
        if text is not None:
            stripped = text.strip()
            return int(stripped) if stripped.isdigit() else None
    return None


def _argv_fields(entry: Path) -> str | None:
    """The three argv fields after the program name, as one line.

    `/proc/<pid>/cmdline` is NUL-separated, and everything past the fourth field
    is dropped rather than written into an artifact.
    """
    try:
        raw = (entry / "cmdline").read_bytes()
    except OSError:
        return None
    argv = [part for part in raw.decode("utf-8", "replace").split("\0") if part]
    return " ".join(" ".join(argv[ARGV_FIELDS]).split())


def _python_processes(proc_root: Path, now: str) -> list[dict[str, Any]]:
    """One row per python process, off the single walk the count is taken on."""
    rows: list[dict[str, Any]] = []
    if not proc_root.is_dir():
        return rows
    for entry in sorted(proc_root.iterdir(), key=lambda path: path.name):
        if not entry.name.isdigit():
            continue
        comm = (_text(entry / "comm") or "").strip()
        if not comm.startswith("python"):
            continue
        status = read_status(int(entry.name), proc_root=proc_root)
        resident = _kilobytes(status, "VmRSS")
        if resident is None:
            continue
        try:
            # POSIX separators, because this string is written into an artifact
            # (CLAUDE.md section 2).
            executable: str | None = (entry / "exe").readlink().as_posix()
        except OSError:
            executable = None
        rows.append(
            {
                "ts": now,
                "pid": int(entry.name),
                "comm": comm,
                "vmrss_kb": resident,
                "vmhwm_kb": _kilobytes(status, "VmHWM"),
                "exe": executable,
                "args": _argv_fields(entry),
            }
        )
    return rows


def sample_once(
    pid: int,
    *,
    proc_root: Path = PROC,
    cgroup_paths: Sequence[Path] = CGROUP_CURRENT_PATHS,
    now: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """One reading of the server, of every python process, and of the machine.

    The count and the roll-call come off one walk, or the sum would be taken
    over a set the roll-call never named.
    """
    moment = now or _now()
    server = read_status(pid, proc_root=proc_root)
    rows = _python_processes(proc_root, moment)
    record: dict[str, Any] = {
        "ts": moment,
        "llama_vmrss_kb": _kilobytes(server, "VmRSS"),
        "llama_vmhwm_kb": _kilobytes(server, "VmHWM"),
        "python_vmrss_kb": sum(row["vmrss_kb"] for row in rows),
        "python_procs": len(rows),
        # The kernel keeps no high-water mark for a process it has forgotten, so
        # a row missing one contributes what it holds now - which is the same
        # lower bound the shell summed, named here rather than implied.
        "python_vmhwm_kb": sum(row["vmhwm_kb"] or row["vmrss_kb"] for row in rows),
        **_meminfo(proc_root),
        "cgroup_current_bytes": _cgroup_current(cgroup_paths),
    }
    return record, rows


def _write(stream: IO[str], record: Mapping[str, Any]) -> None:
    stream.write(json.dumps(record, separators=(",", ":")) + "\n")
    stream.flush()


def sample(pid: int, *, every: float = SAMPLE_EVERY_SECONDS) -> int:
    """Write one record a wake until the process this was given goes away.

    Both files are flushed a record at a time, because the step that reads them
    runs in the same job while this is still running.
    """
    taken = 0
    with (
        RSS_SAMPLE_FILE.open("w", encoding="utf-8") as samples,
        PYTHON_PROCS_FILE.open("w", encoding="utf-8") as roll_call,
    ):
        while (PROC / str(pid)).is_dir():
            record, rows = sample_once(pid)
            _write(samples, record)
            for row in rows:
                _write(roll_call, row)
            taken += 1
            time.sleep(every)
    LOG.info("pid %d is gone, after %d samples", pid, taken)
    return taken


def _refuse_a_sampler_that_died_at_startup(
    child: subprocess.Popen[bytes], log_path: Path
) -> None:
    """Say the loop is already gone, rather than leaving a pid file that lies."""
    try:
        child.wait(timeout=START_GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        return
    tail = ""
    text = _text(log_path)
    if text is not None:
        tail = "\n".join(text.splitlines()[-LOG_TAIL_LINES:])
    raise SystemExit(f"the sampler exited {child.returncode} before it took a sample\n{tail}")


def start_sampler(pid: int, name: str, every: float) -> None:
    """Launch the loop in its own session, prove it is running, and return.

    The parent is a foreground step that exits 0. `start_new_session` calls
    `setsid`, which is strictly more detached than `nohup`: with no controlling
    terminal, SIGHUP is never delivered at all. All three of the child's streams
    are set, because a detached child holding the step's stdio pipe is the
    classic way an Actions step hangs at completion.

    The pid written is the CHILD's. The shell wrote `$!`, which was the pid of
    the backgrounded *shell* - so a loop that died at once left a pid file
    naming a process that had never sampled anything, and a green step.
    """
    log_path = Path(f"{name}.log")
    with log_path.open("wb") as log:
        child = subprocess.Popen(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                "sample",
                "--pid",
                str(pid),
                "--every",
                str(every),
            ],
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            close_fds=True,
        )
    Path(f"{name}.pid").write_text(str(child.pid), encoding="utf-8")
    _refuse_a_sampler_that_died_at_startup(child, log_path)
    LOG.info("sampling pid %d every %.1fs, as pid %d", pid, every, child.pid)


def _records(path: Path) -> list[dict[str, Any]] | None:
    """Every whole line of one file, or nothing at all when it is not there.

    A run killed mid-write leaves a partial last line. It is dropped rather than
    raised on: the summary is what an operator reads off a failed shard.
    """
    text = _text(path)
    if text is None:
        return None
    records: list[dict[str, Any]] = []
    for line in text.splitlines():
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def summarize() -> None:
    """The five figures, and who the python kilobytes belonged to.

    It reads and never writes, and it fails on nothing: an absent file says so.
    """
    samples = _records(RSS_SAMPLE_FILE)
    if samples is None:
        LOG.info("%s not found", RSS_SAMPLE_FILE.name)
    else:
        llama = max((row.get("llama_vmhwm_kb") or 0 for row in samples), default=0)
        python_peak = max((row.get("python_vmhwm_kb") or 0 for row in samples), default=0)
        together = max(
            (
                (row.get("llama_vmrss_kb") or 0) + (row.get("python_vmrss_kb") or 0)
                for row in samples
            ),
            default=0,
        )
        LOG.info(
            "peak llama VmHWM %d kB, peak python VmHWM %d kB, "
            "most the two held at once %d kB, n=%d samples",
            llama,
            python_peak,
            together,
            len(samples),
        )

    # A sum over three processes says nothing about which one to look at.
    roll_call = _records(PYTHON_PROCS_FILE)
    if roll_call is None:
        LOG.info("%s not found", PYTHON_PROCS_FILE.name)
        return
    peak: dict[str, int] = {}
    seen: Counter[str] = Counter()
    for row in roll_call:
        who = f"{row.get('pid')}  {row.get('comm')}  {row.get('exe')}  {row.get('args')}"
        peak[who] = max(peak.get(who, 0), row.get("vmrss_kb") or 0)
        seen[who] += 1
    for who in sorted(peak):
        LOG.info("python %s peak VmRSS %d kB in %d samples", who, peak[who], seen[who])


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    verbs = parser.add_subparsers(dest="verb", required=True)

    def watching(name: str, help_text: str) -> argparse.ArgumentParser:
        verb = verbs.add_parser(name, help=help_text)
        verb.add_argument(
            "--pid", type=int, required=True, help="The process to sample until it goes away."
        )
        verb.add_argument(
            "--every",
            type=float,
            default=SAMPLE_EVERY_SECONDS,
            help="Seconds between one sample and the next.",
        )
        return verb

    start = watching("start-sampler", "Launch the loop in its own session and return.")
    start.add_argument(
        "--name", default=DEFAULT_NAME, help="The stem for <name>.log and <name>.pid."
    )
    watching("sample", "The loop itself, which start-sampler launches.")
    verbs.add_parser("summarize", help="Print what the two files the loop wrote hold.")
    args = parser.parse_args(argv)

    # CLAUDE.md section 1b takes the level from `config/`. This program reads no
    # config on purpose - it runs beside a job rather than inside one, and it
    # imports nothing from `idhazh` - so the level is fixed at INFO, which is
    # what every line it writes needs.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stderr,
    )

    ran: dict[str, Callable[[], object]] = {
        "start-sampler": lambda: start_sampler(args.pid, args.name, args.every),
        "sample": lambda: sample(args.pid, every=args.every),
        "summarize": summarize,
    }
    ran[args.verb]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
