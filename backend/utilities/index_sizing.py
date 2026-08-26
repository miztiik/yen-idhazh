"""Size the archive index before anything signs a shape for it.

The archive page inlines every committed day so the on-device search can see the
whole corpus, and that page is now 1.68 MB gzipped
(`docs/reference/measurements.md`). Splitting it into month shards needs four
numbers that were estimates: how well the committed int8 vectors compress, how
many items a month actually carries, what a browse entry costs, and what the
ranking loop costs at a scope a reader would wait for. This tool measures all
four over the committed archive, so the shape decision is made on Rule #10
numbers rather than on arithmetic somebody did in their head.

Three traps, all found by running it:

1. **The day payload is `digest.json`, not `day.json`.** A glob on the wrong
   name finds nothing and reports a plausible zero for every ratio. Every count
   below is printed with its denominator, and a corpus of zero days is an error.
2. **gzip is what a reader actually receives, and the edge compresses at level
   5.** Measured against the live Pages origin on 2026-08-26:
   `Accept-Encoding: gzip, br, zstd` gets `gzip` back for HTML, JSON, WASM and
   `application/octet-stream` alike, and `Accept-Encoding: br` alone gets no
   compression at all. The edge's own gzip of the committed 22,972,370-byte
   encoder landed on 16,222,259 bytes, which is `gzip -5` to the byte. So this
   tool sizes a transfer at level 5 and reports level 9 beside it, because level
   9 is the unit every page-weight number in `docs/reference/measurements.md`
   already uses. Brotli is reported for the record and is not what transfers.
3. **The ranking cost has to run on V8 or it means nothing.** A Python loop over
   the same arithmetic is a different machine. The harness below is a deliberate
   copy of `decodeVector` and `cosine` from
   `frontend/src/lib/assist/search.ts`, run through `node`, because `backend/`
   may not import frontend code (`CLAUDE.md` section 4). If those two functions
   change, this copy has to follow.

Read-only. It touches no network, writes no payload, and reports counts only.
"""

from __future__ import annotations

import argparse
import base64
import gzip
import json
import platform
import re
import shutil
import statistics
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

from idhazh.config import REPO_ROOT, load
from idhazh.contracts.digest_day import DigestDay

# Where the pipeline commits a published day, and the workflow that says how
# often it runs. Relative and POSIX, per CLAUDE.md section 2.
DIGEST_RELDIR: Final = "frontend/public/digest"
WORKFLOW_RELPATH: Final = ".github/workflows/digest.yml"

# The gzip level the GitHub Pages edge uses, pinned by measurement rather than
# assumed: it served the committed 22,972,370-byte encoder as 16,222,259 bytes,
# which local `gzip -5` reproduces exactly (-1 gives 16,638,186, -6 gives
# 16,217,077, -9 gives 16,212,805). A month file is sized at this level because
# this is what a reader downloads.
GZIP_EDGE_LEVEL: Final = 5

# The level every page-weight number in docs/reference/measurements.md uses.
# Reported beside the edge level so the two pages can be read against each other.
GZIP_GATE_LEVEL: Final = 9

# A month, for sizing. Thirty days is a convention rather than a measurement,
# and it is named once so every table divides by the same number.
DAYS_PER_MONTH: Final = 30

# The scopes a search-scope default has to be chosen from.
REPORTED_SCOPES_MONTHS: Final = (1, 3, 12)

# The two sizes a month shard is judged against. Both were estimates when this
# tool was written - 300 KB and 4 MB - and both were already busted by the
# numbers below. They now carry the budget derived from those numbers in
# `docs/architecture/publishing/layout.md`: 1.5 MB is 30 percent above what the
# structural ceiling projects for the browse index, and 8 MB is half of the
# encoder download a searcher has already accepted.
BROWSE_TRIGGER_BYTES: Final = 1_500_000
VECTOR_TRIGGER_BYTES: Final = 8 * 1024 * 1024

# A reference line, so a transfer figure has a unit a reader feels. This is a
# parameter, not a measurement of anybody's connection; `--line-mbit` moves it.
DEFAULT_LINE_MBIT: Final = 10.0

# How many times the ranking loop is timed at each scope. Odd, so the median is
# a sample rather than an average of two.
DEFAULT_REPEATS: Final = 7

# A deliberate copy of the two functions in `frontend/src/lib/assist/search.ts`.
# See trap 3 in the module docstring for why it is a copy.
_NODE_HARNESS: Final = """\
import { readFileSync, writeFileSync } from 'node:fs';
import { brotliCompressSync, constants } from 'node:zlib';
import { performance } from 'node:perf_hooks';

const [, , jobPath, outPath] = process.argv;
const job = JSON.parse(readFileSync(jobPath, 'utf8'));
const result = { node: process.version, brotli: {}, rank: [] };

for (const [label, encoded] of Object.entries(job.brotli ?? {})) {
  const raw = Buffer.from(encoded, 'base64');
  result.brotli[label] = brotliCompressSync(raw, {
    params: {
      [constants.BROTLI_PARAM_QUALITY]: constants.BROTLI_MAX_QUALITY,
      [constants.BROTLI_PARAM_SIZE_HINT]: raw.length
    }
  }).length;
}

function decodeVector(encoded) {
  const binary = atob(encoded);
  const values = new Array(binary.length);
  let sum = 0;
  for (let index = 0; index < binary.length; index += 1) {
    const byte = binary.charCodeAt(index);
    const signed = (byte > 127 ? byte - 256 : byte) / 127;
    values[index] = signed;
    sum += signed * signed;
  }
  const length = Math.sqrt(sum) || 1;
  for (let index = 0; index < values.length; index += 1) values[index] /= length;
  return values;
}

function cosine(left, right) {
  let total = 0;
  for (let index = 0; index < left.length; index += 1) total += left[index] * right[index];
  return total;
}

// The loop `rank` runs: decode one vector, score it, drop it. Indexed modulo the
// committed corpus so a scope larger than the archive costs the same per item.
function score(vectors, query, count) {
  let best = -2;
  for (let index = 0; index < count; index += 1) {
    const value = cosine(query, decodeVector(vectors[index % vectors.length]));
    if (value > best) best = value;
  }
  return best;
}

const plan = job.rank;
if (plan) {
  const vectors = plan.vectors;
  const query = decodeVector(vectors[0]);
  for (let warm = 0; warm < 3; warm += 1) score(vectors, query, vectors.length);
  for (const scope of plan.scopes) {
    const samples = [];
    for (let repeat = 0; repeat < plan.repeats; repeat += 1) {
      const started = performance.now();
      score(vectors, query, scope.n);
      samples.push(performance.now() - started);
    }
    samples.sort((left, right) => left - right);
    result.rank.push({
      label: scope.label,
      n: scope.n,
      median_ms: samples[(samples.length - 1) >> 1],
      min_ms: samples[0],
      max_ms: samples[samples.length - 1],
      samples_ms: samples
    });
  }
}

writeFileSync(outPath, JSON.stringify(result));
"""


def digest_paths(root: Path) -> list[Path]:
    return sorted((root / DIGEST_RELDIR).glob("*/*/*/digest.json"))


def scheduled_runs_per_day(root: Path) -> tuple[int, list[str]]:
    """How many times a day the pipeline runs, read off the workflow's own cron.

    Not a constant here. The number multiplies the per-run safety ceiling into
    the structural item ceiling, and a copy of it in this file would go stale
    the first time a slot is added.
    """
    text = (root / WORKFLOW_RELPATH).read_text(encoding="utf-8")
    slots = 0
    expressions: list[str] = []
    for match in re.finditer(r"^\s*-\s*cron:\s*['\"]([^'\"]+)['\"]", text, re.MULTILINE):
        expression = match.group(1)
        fields = expression.split()
        if len(fields) != 5:
            raise ValueError(f"cron {expression!r} in {WORKFLOW_RELPATH} is not five fields")
        hours = fields[1]
        if "/" in hours or "-" in hours:
            raise ValueError(f"cron {expression!r} uses a step or range this tool cannot count")
        slots += 24 if hours == "*" else len(hours.split(","))
        expressions.append(expression)
    if not slots:
        raise ValueError(f"no cron schedule found in {WORKFLOW_RELPATH}")
    return slots, expressions


def gzipped(data: bytes, level: int = GZIP_EDGE_LEVEL) -> int:
    """gzip with the timestamp zeroed, so the same bytes always give the same size."""
    return len(gzip.compress(data, compresslevel=level, mtime=0))


def census(days: list[DigestDay]) -> dict[str, Any]:
    """Items and vectors per published day, which is the only rate on record."""
    rows: list[dict[str, Any]] = []
    for day in days:
        vectors = len(day.embeddings.vectors) if day.embeddings else 0
        rows.append({"date": str(day.date), "items": len(day.items), "vectors": vectors})
    items = [int(row["items"]) for row in rows]
    embedded = sum(int(row["vectors"]) for row in rows)
    total = sum(items)
    return {
        "days": rows,
        "n_days": len(rows),
        "n_items": total,
        "n_vectors": embedded,
        "vector_coverage": round(embedded / total, 4) if total else 0.0,
        "items_per_day_mean": round(statistics.fmean(items), 1) if items else 0.0,
        "items_per_day_stddev": round(statistics.stdev(items), 1) if len(items) > 1 else 0.0,
        "items_per_day_median": round(statistics.median(items), 1) if items else 0.0,
        "items_per_day_max": max(items) if items else 0,
    }


def vector_shapes(days: list[DigestDay]) -> dict[str, bytes]:
    """The two shapes a month's vectors could ship in, built from the real bytes.

    `bin` is the sibling file: raw int8, one vector after another, ordered by
    the browse index that already names them. `json` is the same vectors kept
    where they are today, base64 inside a JSON object keyed by item id.
    """
    raw = bytearray()
    keyed: dict[str, str] = {}
    for day in days:
        if not day.embeddings:
            continue
        for item_id, encoded in day.embeddings.vectors.items():
            raw += base64.b64decode(encoded)
            keyed[f"{day.date}/{item_id}"] = encoded
    return {
        "bin": bytes(raw),
        "json": json.dumps(keyed, separators=(",", ":")).encode("utf-8"),
    }


def browse_shapes(days: list[DigestDay]) -> dict[str, bytes]:
    """A real browse entry per real item - no estimated field widths.

    `flat` carries what a search result renders plus the vertical the plan asked
    to see priced: the item id, the date, the vertical and the title. `grouped`
    is the same information with the date lifted to a key and the vertical left
    where it already is, inside the item id, so the floor is visible next to it.
    """
    flat: list[dict[str, str]] = []
    grouped: dict[str, list[list[str]]] = {}
    for day in days:
        date = str(day.date)
        for item in day.items:
            flat.append({"i": item.item_id, "d": date, "v": item.vertical, "t": item.title})
            grouped.setdefault(date, []).append([item.item_id, item.title])
    dumped = json.dumps
    return {
        "flat": dumped(flat, separators=(",", ":"), ensure_ascii=False).encode("utf-8"),
        "grouped": dumped(grouped, separators=(",", ":"), ensure_ascii=False).encode("utf-8"),
    }


def linearity(data: bytes, count: int) -> list[dict[str, Any]]:
    """Whether per-item gzipped bytes hold at a quarter, a half and the whole.

    A month at the structural ceiling is ten times the committed archive, so the
    per-item rate is applied to a blob larger than anything measured here. This
    is the check that the rate does not move with the blob.
    """
    rows: list[dict[str, Any]] = []
    for share in (0.25, 0.5, 1.0):
        part = data[: round(len(data) * share)]
        items = max(1, round(count * share))
        rows.append(
            {
                "share": share,
                "n_items": items,
                "raw_bytes": len(part),
                "gzip_bytes": gzipped(part),
                "gzip_bytes_per_item": round(gzipped(part) / items, 2),
            }
        )
    return rows


def run_node(node: str, job: dict[str, Any]) -> dict[str, Any]:
    """Brotli sizes and ranking milliseconds, from the engine a browser runs."""
    with tempfile.TemporaryDirectory(prefix="idhazh-index-sizing-") as directory:
        workspace = Path(directory)
        harness = workspace / "harness.mjs"
        job_path = workspace / "job.json"
        out_path = workspace / "out.json"
        harness.write_text(_NODE_HARNESS, encoding="utf-8", newline="\n")
        job_path.write_text(json.dumps(job), encoding="utf-8", newline="\n")
        # A fixed script and three paths this process made. No untrusted argv.
        completed = subprocess.run(
            [node, str(harness), str(job_path), str(out_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(f"node exited {completed.returncode}: {completed.stderr.strip()}")
        parsed: dict[str, Any] = json.loads(out_path.read_text(encoding="utf-8"))
        return parsed


def hardware() -> dict[str, Any]:
    """Rule #10: a number without its hardware and date is not a measurement."""
    return {
        "measured_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "platform": platform.platform(),
        "processor": platform.processor() or "unknown",
        "python": platform.python_version(),
    }


def transfer_seconds(byte_count: int, line_mbit: float) -> float:
    return round(byte_count / (line_mbit * 1_000_000 / 8), 2)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help="Repository root to read.")
    parser.add_argument(
        "--node",
        default=shutil.which("node"),
        help="Node executable. Brotli and the ranking clock are skipped without it.",
    )
    parser.add_argument("--repeats", type=int, default=DEFAULT_REPEATS)
    parser.add_argument(
        "--line-mbit",
        type=float,
        default=DEFAULT_LINE_MBIT,
        help="Reference connection for the transfer seconds. A parameter, not a measurement.",
    )
    parser.add_argument("--json", action="store_true", help="Print the whole report as JSON.")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    paths = digest_paths(root)
    if not paths:
        parser.error(f"no committed days under {DIGEST_RELDIR}")
    days = [DigestDay.from_json(path.read_text(encoding="utf-8")) for path in paths]

    counts = census(days)
    if not counts["n_vectors"]:
        parser.error(f"{counts['n_days']} committed days carry no vectors at all")

    slots, crons = scheduled_runs_per_day(root)
    ceiling_per_run = load(root / "config").app.run.safety_ceiling_per_run
    observed_rate = float(counts["items_per_day_mean"])
    ceiling_rate = float(slots * ceiling_per_run)
    rates = {"observed": observed_rate, "ceiling": ceiling_rate}

    vectors = vector_shapes(days)
    browse = browse_shapes(days)
    n_vectors = int(counts["n_vectors"])
    n_items = int(counts["n_items"])

    sizes: dict[str, dict[str, Any]] = {}
    for label, blob, count in (
        ("vectors.bin", vectors["bin"], n_vectors),
        ("vectors.json", vectors["json"], n_vectors),
        ("browse.flat", browse["flat"], n_items),
        ("browse.grouped", browse["grouped"], n_items),
    ):
        sizes[label] = {
            "n": count,
            "raw_bytes": len(blob),
            "raw_bytes_per_item": round(len(blob) / count, 2),
            "gzip_bytes": gzipped(blob),
            "gzip_bytes_per_item": round(gzipped(blob) / count, 2),
            "gzip9_bytes": gzipped(blob, GZIP_GATE_LEVEL),
            "gzip9_bytes_per_item": round(gzipped(blob, GZIP_GATE_LEVEL) / count, 2),
        }

    node_result: dict[str, Any] = {}
    node_reason = ""
    if args.node:
        scopes = [
            {"label": f"{rate}-{months}mo", "n": round(rate_value * DAYS_PER_MONTH * months)}
            for rate, rate_value in rates.items()
            for months in REPORTED_SCOPES_MONTHS
        ]
        encoded = [
            value
            for day in days
            if day.embeddings
            for value in day.embeddings.vectors.values()
        ]
        node_result = run_node(
            args.node,
            {
                "brotli": {
                    label: base64.b64encode(blob).decode("ascii")
                    for label, blob in (
                        ("vectors.bin", vectors["bin"]),
                        ("vectors.json", vectors["json"]),
                        ("browse.flat", browse["flat"]),
                        ("browse.grouped", browse["grouped"]),
                    )
                },
                "rank": {"vectors": encoded, "scopes": scopes, "repeats": args.repeats},
            },
        )
        for label, brotli_bytes in node_result.get("brotli", {}).items():
            sizes[label]["brotli_bytes"] = brotli_bytes
            sizes[label]["brotli_bytes_per_item"] = round(brotli_bytes / sizes[label]["n"], 2)
    else:
        node_reason = "node was not found, so brotli and the ranking clock were not measured"

    per_vector = float(sizes["vectors.bin"]["gzip_bytes_per_item"])
    per_browse = float(sizes["browse.flat"]["gzip_bytes_per_item"])
    months: list[dict[str, Any]] = []
    for rate_label, rate in rates.items():
        month_items = round(rate * DAYS_PER_MONTH)
        vector_bytes = round(month_items * per_vector)
        browse_bytes = round(month_items * per_browse)
        months.append(
            {
                "rate": rate_label,
                "items_per_day": rate,
                "items_per_month": month_items,
                "vector_gzip_bytes": vector_bytes,
                "vector_over_trigger": vector_bytes > VECTOR_TRIGGER_BYTES,
                "browse_gzip_bytes": browse_bytes,
                "browse_over_trigger": browse_bytes > BROWSE_TRIGGER_BYTES,
                "vector_seconds": transfer_seconds(vector_bytes, args.line_mbit),
                "browse_seconds": transfer_seconds(browse_bytes, args.line_mbit),
            }
        )

    report: dict[str, Any] = {
        "hardware": hardware(),
        "root": root.as_posix(),
        "days_read": [path.relative_to(root).as_posix() for path in paths],
        "census": counts,
        "schedule": {
            "cron": crons,
            "runs_per_day": slots,
            "safety_ceiling_per_run": ceiling_per_run,
            "structural_items_per_day": ceiling_rate,
        },
        "sizes": sizes,
        "gzip_linearity": {
            "vectors.bin": linearity(vectors["bin"], n_vectors),
            "browse.flat": linearity(browse["flat"], n_items),
        },
        "months": months,
        "triggers": {
            "browse_index_gzip_bytes": BROWSE_TRIGGER_BYTES,
            "vector_file_transferred_bytes": VECTOR_TRIGGER_BYTES,
        },
        "gzip_level_sized_on": GZIP_EDGE_LEVEL,
        "gzip_level_reported_beside": GZIP_GATE_LEVEL,
        "line_mbit": args.line_mbit,
        "rank": node_result.get("rank", []),
        "node": node_result.get("node", node_reason),
    }

    if args.json:
        print(json.dumps(report, indent=2))
        return 0

    print(f"{counts['n_days']} committed days, {n_items} items, {n_vectors} carry a vector "
          f"({counts['vector_coverage'] * 100:.1f}%)")
    print(f"items a day: mean {counts['items_per_day_mean']} +/- {counts['items_per_day_stddev']}, "
          f"median {counts['items_per_day_median']}, max {counts['items_per_day_max']}")
    print(f"schedule: {slots} runs a day x safety ceiling {ceiling_per_run} = "
          f"{ceiling_rate:.0f} items a day at the structural ceiling")

    header = (
        "shape                  n      raw B  raw/item    gzip5 B  gz5/item  gz9/item   brotli B"
    )
    print(f"\n{header}")
    for label, row in sizes.items():
        brotli = row.get("brotli_bytes")
        print(f"  {label:<18} {row['n']:>6} {row['raw_bytes']:>10} {row['raw_bytes_per_item']:>9} "
              f"{row['gzip_bytes']:>10} {row['gzip_bytes_per_item']:>9} "
              f"{row['gzip9_bytes_per_item']:>9} "
              f"{(brotli if brotli is not None else '-'):>10}")

    print("\na 30-day month, sized on the level-5 gzipped per-item rates above")
    for row in months:
        print(f"  {row['rate']:<9} {row['items_per_month']:>7} items  "
              f"browse {row['browse_gzip_bytes']:>9} B "
              f"({'OVER' if row['browse_over_trigger'] else 'under'} 1.5 MB, "
              f"{row['browse_seconds']}s)  "
              f"vectors {row['vector_gzip_bytes']:>9} B "
              f"({'OVER' if row['vector_over_trigger'] else 'under'} 8 MB, "
              f"{row['vector_seconds']}s)")

    if report["rank"]:
        print(f"\nranking clock on {report['node']}, {args.repeats} repeats, median of samples")
        for row in report["rank"]:
            print(f"  {row['label']:<16} {row['n']:>7} vectors  "
                  f"{row['median_ms']:.1f} ms  (min {row['min_ms']:.1f}, max {row['max_ms']:.1f})")
    elif node_reason:
        print(f"\n{node_reason}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
