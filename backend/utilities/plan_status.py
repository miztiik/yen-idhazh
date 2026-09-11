"""Say what the plan queue is doing: what landed, what can start, what disagrees.

The symptom this exists for. Five plan-docs were open on 2026-09-11 with 58 live
rows between them, and the only way to ask "what can start now" was to open five
files and diff them by eye against `gh pr list`. The answer that reading gave
was also wrong. Pull request 608 merged row `#P1` of the classification plan and
that plan's own Status Reckoner still read `PENDING` with no pull request beside
it, because the rule that a row's pull request updates its own Reckoner line was
written down and nothing ever checked it. A queue nobody can read drifts, and a
queue that drifts sends the next worker at a row that is already done.

What it does. It finds every Status Reckoner under `TODO/`, reads the rows, and
answers three questions on one screen: what has landed, what can start now
because every row it depends on has landed, and where the table disagrees with
the repository. Drift exits non-zero, so this can gate.

    python backend/utilities/plan_status.py              # the queue, and its drift
    python backend/utilities/plan_status.py --in-flight  # ... plus what is half-done
    python backend/utilities/plan_status.py --ready      # just the dispatch list
    python backend/utilities/plan_status.py --plan 23    # one plan
    python backend/utilities/plan_status.py --no-gh      # git only, no pull requests

Discovery is structural, never a list. A plan-doc is any file under `TODO/`
carrying a markdown table with a `#` column and a `Status` column, and the
column NAMES are read from the header rather than counted - so a plan spelling
its group column `Group` and a plan spelling it `Parallel-group` both parse, a
plan with no `Worktree` column parses, and a sixth plan needs no edit here
(Rule #6).

What it reads, and why that is bounded. The plan-docs, and nothing else. Those
are source a person writes, so they grow at review speed rather than once a run,
and reading all of them is a bounded read under Rule #12. It never opens
`state/`, the published archive, or any collection a run appends to. The `git`
and `gh` questions are bounded the same way: one per live worktree, and one per
pull request a live row names.

What it deliberately does not do. It does not edit a plan-doc. Correcting a
drifted row is a judgement - a pull request can be merged and the row still be
right to leave alone, and only a person who read that pull request can say - so
this names the row, the file and the line, and stops.

It imports nothing from `idhazh` and reads no configuration, so it runs from a
fresh clone with any supported Python and no install.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Final

#: Where the plan-docs live, relative to the repository root.
PLANS: Final = "TODO"

#: What a finished branch is measured against, and the remote that carries it.
TRUNK: Final = "origin/main"
REMOTE: Final = "origin"

#: The pull request state that means the row landed. `gh` spells it upper case.
MERGED: Final = "MERGED"

#: Header spellings, by what the column means. The first hit in the header wins,
#: so a plan may use any one of them and none of them is required.
COLUMNS: Final = {
    "id": ("#",),
    "title": ("Row title", "Row", "Defect", "Title"),
    "depends": ("Depends-on", "Depends on", "Depends"),
    "group": ("Parallel-group", "Group", "Phase"),
    "status": ("Status",),
    "worktree": ("Worktree",),
    "pr": ("PR", "Pull request"),
    "subagent": ("Subagent",),
}

#: The two columns that make a table a Status Reckoner rather than any table.
REQUIRED: Final = ("id", "status")

#: Status words, by the state they mean. Anything else is drift, because a
#: mistyped status makes a row invisible to every question below.
LANDED: Final = frozenset({"DONE", "LANDED", "CLOSED", "MERGED", "SHIPPED"})
DROPPED: Final = frozenset(
    {"DESCOPED", "RETIRED", "DEFERRED", "COLLAPSED", "SUPERSEDED", "WITHDRAWN"}
)
FLYING: Final = frozenset({"IN-FLIGHT", "INFLIGHT", "IN_FLIGHT", "WIP"})
STUCK: Final = frozenset({"BLOCKED"})
WAITING: Final = frozenset({"PENDING", "OPEN", "TODO", "QUEUED"})

#: What a cell says when it holds nothing. A Reckoner writes a dash, not a blank.
EMPTY: Final = frozenset({"", "-", "n/a", "none", "tbd"})

#: `plan 24 row #1` in a Depends-on cell. Everything else there is a local id.
CROSS_PLAN: Final = re.compile(r"plan\s+(\d+)\s+row\s*#?\s*([A-Za-z0-9.]+)", re.I)

#: A pull request number, wherever it is written.
PULL_NUMBER: Final = re.compile(r"#(\d+)")

#: How a pull request says which row it did - `(row #P1)` in the title, `# Row
#: #P1 - ...` as the first line of the body. Only those two places are read,
#: because further down a body names rows it unblocks rather than rows it did.
PULL_ROW: Final = re.compile(r"\brows?\s*#\s*([A-Za-z0-9.]+)", re.I)

#: How a pull request says which plan the row is in: the file, or `plan 23`.
PULL_PLAN_FILE: Final = re.compile(r"(\d{8}-[A-Za-z0-9.-]+\.md)")
PULL_PLAN_NUMBER: Final = re.compile(r"\bplan\s+(\d+)\b", re.I)

#: How many merged pull requests the unrecorded-merge rule looks back over. A
#: row's pull request updates that row's line in the same pull request, so a
#: drift can only be recent - a wider window costs more and finds the same
#: nothing. A person raises it with --merged-window when a queue has been left.
MERGED_WINDOW: Final = 20

#: `20260910-23-article-classification-plan.md` is plan 23. A plan-doc with no
#: number in its name is keyed by its stem instead, and cannot be cross-referred.
PLAN_NUMBER: Final = re.compile(r"^\d{8}-(\d+)-")

#: The day a plan-doc was written, from the front of its name. A pull request
#: that merged before that day cannot have done one of its rows, which is what
#: stops `row #12` in an old pull request from being read as a new plan's row.
PLAN_DATE: Final = re.compile(r"^(\d{8})-")

#: Markdown emphasis around a status word. Stripped before the word is read.
EMPHASIS: Final = re.compile(r"[*`_]")


@dataclass(frozen=True)
class Ref:
    """One entry of a Depends-on cell. `plan` is None when it means this plan."""

    plan: int | None
    row_id: str
    text: str


@dataclass(frozen=True)
class Row:
    """One line of one Status Reckoner."""

    plan: PurePosixPath
    plan_key: str
    plan_number: int | None
    plan_date: str
    line: int
    row_id: str
    title: str
    group: str
    depends: tuple[Ref, ...]
    status_word: str
    status_text: str
    worktree: str
    pull: int | None
    pull_text: str
    subagent: str

    @property
    def key(self) -> tuple[str, str]:
        return (self.plan_key, self.row_id.lower())

    @property
    def name(self) -> str:
        """How a person says this row out loud."""
        plan = f"plan {self.plan_number}" if self.plan_number is not None else self.plan_key
        return f"{plan} row #{self.row_id}"

    @property
    def where(self) -> str:
        return f"{self.plan}:{self.line}"

    @property
    def state(self) -> str:
        if self.status_word in LANDED:
            return "landed"
        if self.status_word in DROPPED:
            return "dropped"
        if self.status_word in FLYING:
            return "in-flight"
        if self.status_word in STUCK:
            return "blocked"
        if self.status_word in WAITING:
            return "pending"
        return "unknown"

    @property
    def live(self) -> bool:
        """Live means unfinished: still to do, doing, stuck, or unreadable."""
        return self.state not in ("landed", "dropped")

    @property
    def records_pull(self) -> bool:
        """True when the row says how it landed, by number or in words."""
        return self.pull is not None or self.pull_text.strip().lower() not in EMPTY


@dataclass(frozen=True)
class Plan:
    """One plan-doc and the Status Reckoner it carries."""

    path: PurePosixPath
    number: int | None
    key: str
    header_line: int
    rows: tuple[Row, ...]
    has_pull_column: bool

    @property
    def live(self) -> tuple[Row, ...]:
        return tuple(row for row in self.rows if row.live)


@dataclass(frozen=True)
class Drift:
    """One disagreement between a Reckoner and the repository."""

    rule: str
    row: str
    where: str
    detail: str


@dataclass(frozen=True)
class Worktree:
    """One checkout `git worktree list` names."""

    path: Path
    head: str
    branch: str | None


@dataclass(frozen=True)
class PullRequest:
    number: int
    state: str
    head: str
    title: str
    body: str = ""
    merged_at: str = ""

    @property
    def merged_day(self) -> str:
        """`20260911` from `2026-09-11T20:39:40Z`, or empty when gh did not say."""
        return self.merged_at[:10].replace("-", "")

    @property
    def claim(self) -> str:
        """Where a pull request declares its row: the title and the body's opening."""
        opening = [line for line in self.body.splitlines() if line.strip()][:5]
        return "\n".join([self.title, *opening])


@dataclass(frozen=True)
class TreeFacts:
    """What was read about one worktree. `None` anywhere means "could not read"."""

    tree: Worktree
    uncommitted: int | None
    ahead: int | None
    pull: PullRequest | None
    pull_read: bool


@dataclass(frozen=True)
class Note:
    """One thing that is part-done, and what to do about it."""

    subject: str
    detail: str


# ---------------------------------------------------------------- table reading


def cells(line: str) -> list[str]:
    """The cells of one markdown table line, or an empty list if it is not one."""
    body = line.strip()
    if not body.startswith("|"):
        return []
    parts = re.split(r"(?<!\\)\|", body.strip("|"))
    return [part.replace("\\|", "|").strip() for part in parts]


def is_divider(row: Sequence[str]) -> bool:
    """The `| --- | --- |` line directly under a markdown header."""
    return bool(row) and all(bool(c) and set(c) <= set("-: ") and "-" in c for c in row)


def header_columns(header: Sequence[str]) -> dict[str, int] | None:
    """Map each meaning to its column index, or None if this is not a Reckoner."""
    found: dict[str, int] = {}
    for meaning, spellings in COLUMNS.items():
        for spelling in spellings:
            for index, cell in enumerate(header):
                if cell.lower() == spelling.lower() and index not in found.values():
                    found[meaning] = index
                    break
            if meaning in found:
                break
    if any(meaning not in found for meaning in REQUIRED):
        return None
    return found


def find_reckoner(lines: Sequence[str]) -> tuple[int, dict[str, int]] | None:
    """The Reckoner table: the first `#`-and-`Status` table, preferring one that
    follows a line naming the Status Reckoner. Returns its header line index."""
    candidates: list[tuple[int, dict[str, int]]] = []
    for index, line in enumerate(lines):
        columns = header_columns(cells(line))
        if columns is None:
            continue
        if index + 1 >= len(lines) or not is_divider(cells(lines[index + 1])):
            continue
        candidates.append((index, columns))
    if not candidates:
        return None
    named = [
        index
        for index, line in enumerate(lines)
        if "status reckoner" in line.lower() and not line.strip().startswith("|")
    ]
    for start in named:
        for index, columns in candidates:
            if index > start:
                return index, columns
    return candidates[0]


def status_word(cell: str) -> str:
    """The first word of a status cell, stripped of emphasis and punctuation."""
    text = EMPHASIS.sub("", cell).strip()
    if not text:
        return ""
    return re.split(r"[\s,;:]", text, maxsplit=1)[0].strip(".()[]").upper()


def parse_depends(cell: str) -> tuple[Ref, ...]:
    """Read a Depends-on cell. `-` means nothing; `plan 24 row #1` crosses plans."""
    text = EMPHASIS.sub("", cell).strip()
    if text.lower() in EMPTY:
        return ()
    refs: list[Ref] = []
    for piece in re.split(r",|;| and ", text):
        entry = piece.strip()
        if not entry or entry.lower() in EMPTY:
            continue
        crossing = CROSS_PLAN.search(entry)
        if crossing is not None:
            refs.append(Ref(int(crossing.group(1)), crossing.group(2), entry))
            continue
        # A cell sometimes carries an aside - `8 (and 9 for the student)`. The
        # id is what is being depended on; the aside is for a person to read.
        bare = re.sub(r"\s*\([^)]*\)", "", entry).strip()
        local = re.fullmatch(r"#?\s*([A-Za-z0-9.]+)", bare)
        refs.append(Ref(None, local.group(1) if local else entry, entry))
    return tuple(refs)


def parse_pull(pull_cell: str, status_cell: str) -> int | None:
    """The pull request number, preferring the PR column over the status text."""
    for cell in (pull_cell, status_cell):
        found = PULL_NUMBER.search(cell)
        if found is not None:
            return int(found.group(1))
    return None


def cell_at(row: Sequence[str], columns: Mapping[str, int], meaning: str) -> str:
    index = columns.get(meaning)
    if index is None or index >= len(row):
        return ""
    return row[index]


def parse_plan(path: PurePosixPath, text: str) -> Plan | None:
    """Read one plan-doc. Returns None when it carries no Status Reckoner."""
    lines = text.splitlines()
    found = find_reckoner(lines)
    if found is None:
        return None
    header_index, columns = found
    width = len(cells(lines[header_index]))
    number_match = PLAN_NUMBER.match(path.name)
    number = int(number_match.group(1)) if number_match else None
    date_match = PLAN_DATE.match(path.name)
    date = date_match.group(1) if date_match else ""
    key = str(number) if number is not None else path.stem

    rows: list[Row] = []
    for offset, line in enumerate(lines[header_index + 2 :], start=header_index + 3):
        row = cells(line)
        if len(row) != width:
            break
        raw_status = cell_at(row, columns, "status")
        raw_pull = cell_at(row, columns, "pr")
        row_id = EMPHASIS.sub("", cell_at(row, columns, "id")).strip().lstrip("#").strip()
        if not row_id:
            continue
        rows.append(
            Row(
                plan=path,
                plan_key=key,
                plan_number=number,
                plan_date=date,
                line=offset,
                row_id=row_id,
                title=cell_at(row, columns, "title"),
                group=EMPHASIS.sub("", cell_at(row, columns, "group")).strip(),
                depends=parse_depends(cell_at(row, columns, "depends")),
                status_word=status_word(raw_status),
                status_text=raw_status,
                worktree=cell_at(row, columns, "worktree"),
                pull=parse_pull(raw_pull, raw_status),
                pull_text=raw_pull,
                subagent=cell_at(row, columns, "subagent"),
            )
        )
    if not rows:
        return None
    return Plan(
        path=path,
        number=number,
        key=key,
        header_line=header_index + 1,
        rows=tuple(rows),
        has_pull_column="pr" in columns,
    )


def read_plans(root: Path) -> list[Plan]:
    """Every plan-doc under `TODO/` that carries a Status Reckoner, in name order."""
    plans: list[Plan] = []
    folder = root / PLANS
    if not folder.is_dir():
        return plans
    for path in sorted(folder.glob("*.md")):
        plan = parse_plan(
            PurePosixPath(path.relative_to(root).as_posix()),
            path.read_text(encoding="utf-8"),
        )
        if plan is not None:
            plans.append(plan)
    return plans


# ------------------------------------------------------------------- the queue


def index_rows(plans: Iterable[Plan]) -> dict[tuple[str, str], Row]:
    """Every row by (plan key, lower-case row id). The first of a repeat wins."""
    found: dict[tuple[str, str], Row] = {}
    for plan in plans:
        for row in plan.rows:
            found.setdefault(row.key, row)
    return found


def resolve(row: Row, ref: Ref, index: Mapping[tuple[str, str], Row]) -> Row | None:
    key = (str(ref.plan) if ref.plan is not None else row.plan_key, ref.row_id.lower())
    return index.get(key)


def unmet(row: Row, index: Mapping[tuple[str, str], Row]) -> list[str]:
    """Why this row cannot start yet, one reason per dependency that is not landed."""
    reasons: list[str] = []
    for ref in row.depends:
        target = resolve(row, ref, index)
        if target is None:
            reasons.append(f"{ref.text} names no row")
        elif target.state != "landed":
            reasons.append(f"{ref.text} is {target.state.upper()}")
    return reasons


def ready(rows: Iterable[Row], index: Mapping[tuple[str, str], Row]) -> list[Row]:
    """Rows that can start now: still to do, and every dependency landed."""
    return [row for row in rows if row.state == "pending" and not unmet(row, index)]


def counts(rows: Iterable[Row]) -> dict[str, int]:
    tally = {
        "landed": 0,
        "dropped": 0,
        "pending": 0,
        "in-flight": 0,
        "blocked": 0,
        "unknown": 0,
    }
    for row in rows:
        tally[row.state] += 1
    return tally


# -------------------------------------------------------------------- the drift


def find_drift(
    plans: Sequence[Plan],
    index: Mapping[tuple[str, str], Row],
    pull_states: Mapping[int, str] | None,
) -> list[Drift]:
    """Every way a Reckoner disagrees with itself or with the repository.

    `pull_states` is what `gh` said about the pull requests these rows name, or
    None when `gh` could not be asked - in which case the first rule is skipped
    rather than guessed at.
    """
    drift: list[Drift] = []
    for plan in plans:
        for row in plan.rows:
            if row.state == "unknown":
                said = row.status_text.strip() or "(blank)"
                drift.append(
                    Drift("unknown-status", row.name, row.where, f"status reads {said!r}")
                )
            if (
                pull_states is not None
                and row.pull is not None
                and pull_states.get(row.pull) == MERGED
                and row.state != "landed"
            ):
                said = row.status_word or "(blank)"
                drift.append(
                    Drift(
                        "merged-but-not-done",
                        row.name,
                        row.where,
                        f"pull request {row.pull} merged, status reads {said}",
                    )
                )
            if row.state == "landed" and plan.has_pull_column and not row.records_pull:
                drift.append(
                    Drift(
                        "done-with-no-pr",
                        row.name,
                        row.where,
                        "status is done and the PR column is empty",
                    )
                )
            for ref in row.depends:
                target = resolve(row, ref, index)
                if target is None:
                    drift.append(
                        Drift(
                            "dependency-not-found",
                            row.name,
                            row.where,
                            f"depends on {ref.text!r}, which names no row",
                        )
                    )
                elif row.state == "landed" and target.state != "landed":
                    drift.append(
                        Drift(
                            "done-before-its-dependency",
                            row.name,
                            row.where,
                            f"is done, but {target.name} is {target.state.upper()}",
                        )
                    )
    return drift


def unrecorded_merges(pulls: Iterable[PullRequest], rows: Sequence[Row]) -> list[Drift]:
    """Merged pull requests whose row never learned they landed.

    This is the rule the queue actually needed. A row that forgot to record its
    own pull request has an empty PR column, so no other rule here can reach it
    - the only thing that still knows is the pull request, which says in its
    title and its opening line which row it did. Pull request 608 merged row
    `#P1` of the classification plan on 2026-09-11 and the row read `PENDING`
    for the rest of that day; nothing would have said so without this.
    """
    recorded = {row.pull for row in rows if row.pull is not None}
    drift: list[Drift] = []
    for pull in pulls:
        if pull.state != MERGED or pull.number in recorded:
            continue
        claim = pull.claim
        wanted = {found.lower() for found in PULL_ROW.findall(claim)}
        if not wanted:
            continue
        files = set(PULL_PLAN_FILE.findall(claim))
        numbers = {int(found) for found in PULL_PLAN_NUMBER.findall(claim)}
        for row_id in sorted(wanted):
            hits = [row for row in rows if row.row_id.lower() == row_id and row.state != "landed"]
            if pull.merged_day:
                # A pull request cannot have done a row of a plan that did not
                # exist when it merged. Without this, `row #12` in an old pull
                # request reads as row #12 of every plan written since.
                hits = [
                    row for row in hits if not row.plan_date or row.plan_date <= pull.merged_day
                ]
            if files or numbers:
                # The pull request said which plan. Believe it, even when that
                # leaves nothing - another plan's row with the same id is a
                # different row, and guessing at it is how a false report starts.
                hits = [row for row in hits if row.plan.name in files or row.plan_number in numbers]
            for row in hits:
                drift.append(
                    Drift(
                        "merged-but-row-not-updated",
                        row.name,
                        row.where,
                        f"pull request {pull.number} says it did row #{row.row_id} and merged, "
                        f"but this row still reads {row.state.upper()} with no pull request",
                    )
                )
    return drift


# --------------------------------------------------------------- git and gh I/O


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=False)


def _gh(repo: Path, *args: str) -> str:
    """Run `gh` and return its stdout. Raises LookupError when it cannot answer."""
    try:
        done = subprocess.run(
            ["gh", *args], cwd=repo, capture_output=True, text=True, check=False
        )
    except OSError as error:
        raise LookupError(str(error)) from error
    if done.returncode != 0:
        raise LookupError(done.stderr.strip() or "gh failed")
    return done.stdout


def read_worktrees(repo: Path) -> list[Worktree]:
    """Every worktree except the main one, which is the first block git prints."""
    done = _git(repo, "worktree", "list", "--porcelain")
    if done.returncode != 0:
        return []
    trees: list[Worktree] = []
    for block in done.stdout.split("\n\n"):
        path: Path | None = None
        head = ""
        branch: str | None = None
        bare = False
        for line in block.splitlines():
            entry = line.strip()
            if entry.startswith("worktree "):
                path = Path(entry.removeprefix("worktree "))
            elif entry.startswith("HEAD "):
                head = entry.removeprefix("HEAD ")
            elif entry.startswith("branch refs/heads/"):
                branch = entry.removeprefix("branch refs/heads/")
            elif entry == "bare":
                bare = True
        if path is not None and not bare:
            trees.append(Worktree(path=path, head=head, branch=branch))
    return trees[1:]


def read_uncommitted(tree: Path) -> int | None:
    done = _git(tree, "status", "--porcelain")
    if done.returncode != 0:
        return None
    return len([line for line in done.stdout.splitlines() if line.strip()])


def read_ahead(repo: Path, head: str, trunk: str) -> int | None:
    done = _git(repo, "rev-list", "--count", f"{trunk}..{head}")
    if done.returncode != 0:
        return None
    return int(done.stdout.strip() or 0)


def read_branches(repo: Path) -> list[str]:
    done = _git(repo, "branch", "--format=%(refname:short)")
    if done.returncode != 0:
        return []
    return [line.strip() for line in done.stdout.splitlines() if line.strip()]


def _as_pull(entry: Mapping[str, object]) -> PullRequest | None:
    number = entry.get("number")
    state = entry.get("state")
    if not isinstance(number, int) or not isinstance(state, str):
        return None
    head = entry.get("headRefName")
    title = entry.get("title")
    body = entry.get("body")
    merged_at = entry.get("mergedAt")
    return PullRequest(
        number=number,
        state=state,
        head=head if isinstance(head, str) else "",
        title=title if isinstance(title, str) else "",
        body=body if isinstance(body, str) else "",
        merged_at=merged_at if isinstance(merged_at, str) else "",
    )


def _pull_list(raw: str) -> list[PullRequest]:
    parsed: object = json.loads(raw or "[]")
    if not isinstance(parsed, list):
        raise LookupError("gh did not return a list of pull requests")
    pulls: list[PullRequest] = []
    for entry in parsed:
        if isinstance(entry, dict):
            pull = _as_pull(entry)
            if pull is not None:
                pulls.append(pull)
    return pulls


def read_open_pulls(repo: Path) -> list[PullRequest]:
    """Every open pull request. Bounded by open work, not by what the repo holds."""
    fields = "number,state,headRefName,title"
    return _pull_list(_gh(repo, "pr", "list", "--state", "open", "--json", fields))


def read_merged_pulls(repo: Path, window: int) -> list[PullRequest]:
    """The last `window` merged pull requests, newest first. The window is the
    cover a person set, so this never costs more as the repository grows."""
    fields = "number,state,headRefName,title,body,mergedAt"
    return _pull_list(
        _gh(repo, "pr", "list", "--state", "merged", "--limit", str(window), "--json", fields)
    )


def read_branch_pull(repo: Path, branch: str) -> PullRequest | None:
    """The pull request for one branch, preferring a merged one."""
    fields = "number,state,headRefName,title"
    pulls = _pull_list(
        _gh(repo, "pr", "list", "--state", "all", "--head", branch, "--json", fields)
    )
    merged = [pull for pull in pulls if pull.state == MERGED]
    if merged:
        return merged[0]
    return pulls[0] if pulls else None


def read_pull_states(repo: Path, numbers: Iterable[int]) -> dict[int, str]:
    """The state of each pull request a live row names. One `gh` call per number."""
    states: dict[int, str] = {}
    for number in sorted(set(numbers)):
        raw = _gh(repo, "pr", "view", str(number), "--json", "number,state")
        parsed: object = json.loads(raw or "{}")
        if isinstance(parsed, dict):
            state = parsed.get("state")
            if isinstance(state, str):
                states[number] = state
    return states


# ------------------------------------------------------------------- in flight


def rows_for_tree(tree: Worktree, rows: Iterable[Row]) -> list[Row]:
    """The plan rows that claim this worktree, by directory name or branch."""
    wanted = {tree.path.name.lower()}
    if tree.branch is not None:
        wanted.add(tree.branch.lower())
    found: list[Row] = []
    for row in rows:
        said = EMPHASIS.sub("", row.worktree).strip().lower()
        if said and said not in EMPTY and (said in wanted or said.rsplit("/", 1)[-1] in wanted):
            found.append(row)
    return found


def judge_tree(facts: TreeFacts, rows: Sequence[Row]) -> Note:
    """One worktree, said in a sentence: whose row it is and whether it finished."""
    tree = facts.tree
    claimed = rows_for_tree(tree, rows)
    if claimed:
        owner = ", ".join(row.name for row in claimed)
    elif tree.branch is None:
        owner = "detached, so no plan row can claim it"
    else:
        owner = "no plan row names it"

    parts = [owner]
    if facts.uncommitted:
        noun = "file" if facts.uncommitted == 1 else "files"
        parts.append(f"{facts.uncommitted} uncommitted {noun}")
    if facts.ahead:
        noun = "commit" if facts.ahead == 1 else "commits"
        parts.append(f"{facts.ahead} {noun} ahead of {TRUNK}")

    started = bool(facts.uncommitted) or bool(facts.ahead)
    if tree.branch is None:
        parts.append("ADOPT: a detached tree can hold work nothing tracks" if started else "REMOVE")
        return Note(subject=tree.path.name, detail="; ".join(parts))

    if not facts.pull_read:
        parts.append("its pull request could not be read, so no verdict")
    elif facts.pull is None:
        parts.append("no pull request was ever opened")
        parts.append("ADOPT: work here was never proposed" if started else "REMOVE: nothing in it")
    else:
        parts.append(f"pull request {facts.pull.number} is {facts.pull.state.lower()}")
        if facts.pull.state == MERGED and not started:
            parts.append("REMOVE: it landed")
        elif facts.pull.state == MERGED and started:
            parts.append("ADOPT: it landed and this tree has moved since")
    return Note(subject=tree.path.name, detail="; ".join(parts))


def stranded_rows(rows: Iterable[Row], trees: Sequence[Worktree]) -> list[Note]:
    """Rows that say they are being worked on where no worktree backs that up."""
    live = {tree.path.name.lower() for tree in trees}
    live |= {tree.branch.lower() for tree in trees if tree.branch is not None}
    notes: list[Note] = []
    for row in rows:
        said = EMPHASIS.sub("", row.worktree).strip().lower()
        if row.state == "in-flight" and (said in EMPTY or said not in live):
            where = f"names {said!r}, which" if said not in EMPTY else "names no worktree, and none"
            notes.append(Note(row.name, f"is IN-FLIGHT but {where} is on this box"))
    return notes


def open_pull_notes(
    pulls: Iterable[PullRequest], rows: Sequence[Row], trees: Sequence[Worktree]
) -> list[Note]:
    """Open pull requests, and which plan row each one is finishing.

    A worktree is not the only place half-done work hides. A pull request opened
    from a checkout that has since been removed is still outstanding, and it is
    invisible to every other question here.
    """
    held = {tree.branch for tree in trees if tree.branch is not None}
    notes: list[Note] = []
    for pull in pulls:
        claimed = [
            row.name
            for row in rows
            if row.pull == pull.number
            or EMPHASIS.sub("", row.worktree).strip().lower() == pull.head.lower()
        ]
        owner = ", ".join(claimed) if claimed else "no plan row records it"
        where = "a worktree still holds its branch" if pull.head in held else "no worktree holds it"
        notes.append(Note(f"#{pull.number}", f"{owner}; {where}; {pull.title}"))
    return notes


def idle_branches(branches: Iterable[str], trees: Sequence[Worktree], trunk: str) -> list[str]:
    """Local branches with no worktree. A dead agent often leaves exactly one."""
    held = {tree.branch for tree in trees if tree.branch is not None}
    trunk_name = trunk.rsplit("/", 1)[-1]
    return sorted(name for name in branches if name not in held and name != trunk_name)


# --------------------------------------------------------------------- printing


def _fit(text: str, width: int) -> str:
    return text if len(text) <= width else text[: width - 1] + "~"


def print_rows(plan: Plan, rows: Sequence[Row]) -> None:
    print(f"  {plan.path}")
    for row in rows:
        depends = ", ".join(ref.text for ref in row.depends) or "-"
        pull = f"#{row.pull}" if row.pull is not None else (row.pull_text.strip() or "-")
        tree = row.worktree.strip() or "-"
        print(
            f"    {('#' + row.row_id):<6} {_fit(row.group, 4):<4} "
            f"{row.state.upper():<9} {_fit(depends, 22):<22} "
            f"{_fit(pull, 8):<8} {_fit(tree, 14):<14} {_fit(row.title, 58)}"
        )


def print_report(
    plans: Sequence[Plan],
    skipped: Sequence[Plan],
    index: Mapping[tuple[str, str], Row],
    drift: Sequence[Drift],
    *,
    show_rows: bool,
    gh_said: str | None,
) -> None:
    live_rows = [row for plan in plans for row in plan.live]

    print("PLAN QUEUE")
    print(f"  {'plan':<52} {'rows':>5} {'done':>5} {'live':>5} {'ready':>6}")
    for plan in plans:
        tally = counts(plan.rows)
        can_start = len(ready(plan.rows, index))
        print(
            f"  {_fit(plan.path.name, 52):<52} {len(plan.rows):>5} "
            f"{tally['landed'] + tally['dropped']:>5} {len(plan.live):>5} {can_start:>6}"
        )
    total = counts(row for plan in plans for row in plan.rows)
    noun = "plan" if len(plans) == 1 else "plans"
    print(
        f"  {len(plans)} {noun} read: {total['pending']} pending, "
        f"{total['in-flight']} in flight, {total['blocked']} blocked, "
        f"{total['unknown']} unreadable, {total['landed']} done, {total['dropped']} dropped"
    )
    if skipped:
        names = ", ".join(plan.path.name for plan in skipped)
        print(f"  {len(skipped)} plans have no live row and are not listed: {names}")
        print("  re-run with --all to read them too")
    blind = [plan for plan in plans if not plan.has_pull_column]
    if blind:
        names = ", ".join(plan.path.name for plan in blind)
        print(f"  {len(blind)} plans have no PR column, so a done row proves nothing: {names}")

    if show_rows and live_rows:
        print("\nLIVE ROWS")
        print(
            f"    {'#':<6} {'grp':<4} {'state':<9} {'depends-on':<22} "
            f"{'pr':<8} {'worktree':<14} title"
        )
        for plan in plans:
            if plan.live:
                print_rows(plan, plan.live)

    print("\nREADY NOW - nothing it depends on is outstanding")
    startable = ready(live_rows, index)
    if not startable:
        print("  nothing. Every live row is waiting on another row.")
    for plan in plans:
        mine = [row for row in startable if row.plan == plan.path]
        if mine:
            print(f"  {plan.path}")
            for row in mine:
                print(f"    {('#' + row.row_id):<6} {_fit(row.group, 4):<4} {_fit(row.title, 84)}")
    print(f"  {len(startable)} rows can start now, out of {len(live_rows)} live")

    waiting = [row for row in live_rows if row.state == "pending" and unmet(row, index)]
    if waiting:
        print(f"  {len(waiting)} live rows are waiting on another row")

    print("\nDRIFT - where a Reckoner disagrees with the repository")
    if gh_said is not None:
        print(f"  {gh_said}")
    if not drift:
        print("  none")
        return
    for item in sorted(drift, key=lambda d: (d.rule, d.where)):
        print(f"  {item.rule:<26} {_fit(item.row, 22):<22} {item.where}")
        print(f"  {'':<26} {item.detail}")
    noun = "finding" if len(drift) == 1 else "findings"
    print(f"  {len(drift)} {noun}. A Reckoner line is corrected by hand, never by this tool.")


def print_in_flight(
    notes: Sequence[Note],
    pulls: Sequence[Note],
    stranded: Sequence[Note],
    idle: Sequence[str],
) -> None:
    print("\nIN FLIGHT - what a previous agent left behind")
    if not notes and not pulls and not stranded and not idle:
        print("  nothing. No extra worktree, no open pull request, no stranded row.")
        return
    for note in notes:
        print(f"  worktree {note.subject:<24} {note.detail}")
    for note in pulls:
        print(f"  open pr  {note.subject:<24} {note.detail}")
    for note in stranded:
        print(f"  row      {note.subject:<24} {note.detail}")
    if idle:
        print(f"  branches with no worktree: {', '.join(idle)}")


# ------------------------------------------------------------------------- main


def main() -> None:
    parser = argparse.ArgumentParser(description="Read the plan queue and its drift.")
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--trunk", default=TRUNK)
    parser.add_argument("--plan", default="", help="only plans whose filename holds this")
    parser.add_argument("--all", action="store_true", help="include plans with no live row")
    parser.add_argument("--ready", action="store_true", help="skip the per-row listing")
    parser.add_argument(
        "--in-flight", action="store_true", help="cross-check worktrees and branches"
    )
    parser.add_argument(
        "--merged-window",
        type=int,
        default=MERGED_WINDOW,
        help=f"how many merged pull requests to look back over (default {MERGED_WINDOW})",
    )
    parser.add_argument("--no-gh", action="store_true", help="ask git only, never gh")
    args = parser.parse_args()

    every = read_plans(args.repo)
    if args.plan:
        every = [plan for plan in every if args.plan.lower() in plan.path.name.lower()]
    index = index_rows(every)
    listed = every if args.all else [plan for plan in every if plan.live]
    skipped = [plan for plan in every if plan not in listed]

    pull_states: dict[int, str] | None = None
    gh_said: str | None = None
    # Only a row that has NOT landed can fail the merged-but-not-done rule, so
    # only those pull requests are asked about. That keeps the call count tied
    # to outstanding work rather than to everything the repository has merged.
    named = [
        row.pull
        for plan in listed
        for row in plan.rows
        if row.pull is not None and row.state != "landed"
    ]
    merged: list[PullRequest] = []
    if args.no_gh:
        gh_said = "gh not asked, so a merged pull request behind a PENDING row is not checked"
    else:
        try:
            if named:
                pull_states = read_pull_states(args.repo, named)
            merged = read_merged_pulls(args.repo, args.merged_window)
            gh_said = f"gh read the last {len(merged)} merged pull requests"
        except (LookupError, json.JSONDecodeError) as error:
            gh_said = f"gh could not be read ({error}), so pull request states were not checked"

    drift = find_drift(listed, index, pull_states)
    drift += unrecorded_merges(merged, [row for plan in listed for row in plan.rows])
    print_report(
        listed,
        skipped,
        index,
        drift,
        show_rows=not args.ready,
        gh_said=gh_said,
    )

    if args.in_flight:
        trees = read_worktrees(args.repo)
        rows = [row for plan in every for row in plan.rows]
        notes: list[Note] = []
        for tree in trees:
            pull: PullRequest | None = None
            pull_read = False
            if tree.branch is not None and not args.no_gh:
                try:
                    pull = read_branch_pull(args.repo, tree.branch)
                    pull_read = True
                except (LookupError, json.JSONDecodeError):
                    pull_read = False
            notes.append(
                judge_tree(
                    TreeFacts(
                        tree=tree,
                        uncommitted=read_uncommitted(tree.path),
                        ahead=read_ahead(args.repo, tree.head, args.trunk),
                        pull=pull,
                        pull_read=pull_read,
                    ),
                    rows,
                )
            )
        open_pulls: list[PullRequest] = []
        if not args.no_gh:
            try:
                open_pulls = read_open_pulls(args.repo)
            except (LookupError, json.JSONDecodeError):
                open_pulls = []
        print_in_flight(
            notes,
            open_pull_notes(open_pulls, rows, trees),
            stranded_rows(rows, trees),
            idle_branches(read_branches(args.repo), trees, args.trunk),
        )

    if drift:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
