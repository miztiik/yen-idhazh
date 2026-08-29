"""Build the work queue for the hand-authored reference set, and check what came back.

Two verbs and no third. This tool does not write summaries and it does not call
a model - a person does that in their editor, with whatever expert model they
have, and commits the result (plan row 5 decision 1).

    python backend/utilities/reference_set.py queue
    python backend/utilities/reference_set.py check
    python backend/utilities/reference_set.py check --write

`queue` turns an unstructured task into a checked one. It samples articles out of
the committed corpus, stratified on the three things the prompt actually branches
on, and writes one line per article carrying the exact system turn and the exact
user turn a run would have sent. The authoring session fills in `assistant` and
nothing else, so a reference row cannot be written against a prompt we do not
serve - the same oracle `idhazh.corpus` uses, for the same reason.

`check` reads the queue back and refuses what a run would refuse: a target the
constrained decoder would reject, a summary outside its own band's word range, an
article that is in the training window as well, or a `url_key` on both sides of
the train/test line. With `--write` it emits the rows that passed to
`tests/fixtures/reference/reference.jsonl`, in the same `CorpusRow` shape as
`corpus/corpus.jsonl` so a notebook can concatenate the two files and nothing has
to know which is which.

**The reference set and the training window must not share an article.** They are
different files on different lifecycles (plan section 4), but disjointness is a
separate property and this is what enforces it: one article gets one target, and
where both exist the hand-written one is the one worth keeping. `check` fails on
an overlap and names the keys, which `data_wrangler.py remove` then drops.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Final, NamedTuple

from pydantic import ValidationError

from idhazh import config, corpus, summarize
from idhazh.contracts.app_config import SummarizeConfig
from idhazh.contracts.corpus import ChatRole, ChatTurn, CorpusRow

REPO_ROOT: Final = Path(__file__).resolve().parents[2]
REFERENCE_ROOT_RELPATH: Final = "tests/fixtures/reference"
QUEUE_FILENAME: Final = "queue.jsonl"
ROWS_FILENAME: Final = "reference.jsonl"
#: What a table is padded to, matching `data_wrangler.py`.
_WIDTH: Final = 26
#: The line `summarize.user_turn` puts first, which is where the form is readable.
_FORM_PREFIX: Final = "Source form: "

TRAIN: Final = "train"
TEST: Final = "test"


class Task(NamedTuple):
    """One article waiting for a summary, plus what the run would have asked for.

    The system turn is deliberately absent: it is 3.8 KB of template that
    `band` already determines, so carrying it would put a second copy of the
    prompt on all 500 lines and let a stale copy outlive a prompt edit. `check`
    re-renders it from `band` at the moment it builds the row - the same
    identity-by-construction rule `idhazh.corpus` follows. What the author needs
    from it is the word range, and that is here.
    """

    url_key: str
    date: str
    vertical: str
    slice_: str
    band: int
    target_words_min: int
    target_words_max: int
    source_form: str
    user: str
    assistant: str | None

    def to_payload(self) -> dict[str, Any]:
        return {
            "url_key": self.url_key,
            "date": self.date,
            "vertical": self.vertical,
            "slice": self.slice_,
            "band": self.band,
            "target_words_min": self.target_words_min,
            "target_words_max": self.target_words_max,
            "source_form": self.source_form,
            "user": self.user,
            "assistant": self.assistant,
        }

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> Task:
        return cls(
            url_key=payload["url_key"],
            date=payload["date"],
            vertical=payload["vertical"],
            slice_=payload["slice"],
            band=payload["band"],
            target_words_min=payload["target_words_min"],
            target_words_max=payload["target_words_max"],
            source_form=payload["source_form"],
            user=payload["user"],
            assistant=payload.get("assistant"),
        )


def queue_path(reference_dir: Path) -> Path:
    return reference_dir / QUEUE_FILENAME


def rows_path(reference_dir: Path) -> Path:
    return reference_dir / ROWS_FILENAME


def shown(path: Path) -> str:
    """Repo-relative and POSIX where it can be (CLAUDE.md section 2).

    A caller may point `--reference-dir` anywhere, and a test points it at a temp
    directory, so this falls back instead of raising on a path outside the repo.
    """
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def read_queue(reference_dir: Path) -> list[Task]:
    path = queue_path(reference_dir)
    if not path.is_file():
        return []
    return [
        Task.from_payload(json.loads(line))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_queue(reference_dir: Path, tasks: Sequence[Task]) -> None:
    """Temp-file-plus-rename, so an interrupted write cannot truncate the queue."""
    reference_dir.mkdir(parents=True, exist_ok=True)
    body = "".join(json.dumps(task.to_payload(), sort_keys=True) + "\n" for task in tasks)
    temp = queue_path(reference_dir).with_suffix(".jsonl.tmp")
    temp.write_text(body, encoding="utf-8", newline="")
    temp.replace(queue_path(reference_dir))


# --- reading the stratification off a row ----------------------------------


def band_prompts(prompt_config: SummarizeConfig) -> list[str]:
    """The rendered system turn for each band, in band order.

    Rendered rather than described, so a band's identity here is the exact string
    a run would have sent. That is what makes `band_of` an equality test instead
    of a parse of prose that could drift from the template.
    """
    return [
        summarize.system_prompt(prompt_config, source_words=band.min_source_words)
        for band in prompt_config.bands
    ]


def band_of(system: str, prompts: Sequence[str]) -> int | None:
    """Which band this row was asked for, or None if the prompt has moved since."""
    for index, rendered in enumerate(prompts):
        if rendered == system:
            return index
    return None


def source_form_of(user: str) -> str:
    """The curator-declared form, read off the line `user_turn` writes first."""
    head = user.split("\n", 1)[0]
    return head.removeprefix(_FORM_PREFIX).strip() if head.startswith(_FORM_PREFIX) else "unknown"


def stratum(task: Task) -> tuple[str, int, str]:
    """What a sample must spread across: the two things the prompt branches on, plus vertical.

    Word-count band and source form are what `system_prompt` and `user_turn` read,
    so a set that is thin in one of them trains a model that is thin there too.
    Vertical is the third because it is the one diversity column that is fully
    populated on every row.
    """
    return (task.vertical, task.band, task.source_form)


# --- queue -----------------------------------------------------------------


def _tasks_from_corpus(rows: Sequence[CorpusRow], prompt_config: SummarizeConfig) -> list[Task]:
    """Every corpus row that still matches a live band, as an unassigned task."""
    prompts = band_prompts(prompt_config)
    found: list[Task] = []
    for row in rows:
        system, user = row.messages[0].content, row.messages[1].content
        band = band_of(system, prompts)
        if band is None:
            continue
        asked = prompt_config.bands[band]
        found.append(
            Task(
                url_key=row.url_key,
                date=row.date,
                vertical=row.vertical,
                slice_=TRAIN,
                band=band,
                target_words_min=asked.target_words_min,
                target_words_max=asked.target_words_max,
                source_form=source_form_of(user),
                user=user,
                assistant=None,
            )
        )
    return found


def spread(candidates: Sequence[Task], *, want: int) -> list[Task]:
    """`want` tasks, taken round-robin across strata so no stratum is starved.

    Deterministic: strata in sorted order, rows sorted by `url_key` inside each,
    no random number anywhere. Re-running `queue` on an unchanged corpus returns
    the same set, which is what lets the queue be extended rather than reshuffled.
    """
    buckets: dict[tuple[str, int, str], list[Task]] = defaultdict(list)
    for task in candidates:
        buckets[stratum(task)].append(task)
    for bucket in buckets.values():
        bucket.sort(key=lambda task: task.url_key)

    picked: list[Task] = []
    depth = 0
    while len(picked) < want:
        took = False
        for key in sorted(buckets):
            bucket = buckets[key]
            if depth < len(bucket):
                picked.append(bucket[depth])
                took = True
                if len(picked) == want:
                    break
        if not took:
            break
        depth += 1
    return picked


def assign_slices(tasks: Sequence[Task], *, test_rows: int) -> list[Task]:
    """Hold back a proportional share of every stratum as the test slice.

    Sorted by stratum first, then strided. Striding the arrival order instead
    would alias: `spread` emits round-robin with a period equal to the number of
    strata, so every k-th task can land in the same stratum every time and the
    held-back slice ends up measuring one band. Sorting first makes the stride
    walk through the strata in proportion to their size, which is what a test
    reference has to do to be a test of anything.
    """
    if test_rows <= 0 or not tasks:
        return list(tasks)
    ordered = sorted(range(len(tasks)), key=lambda i: (stratum(tasks[i]), tasks[i].url_key))
    step = max(1, len(ordered) / min(test_rows, len(ordered)))
    held = {ordered[min(len(ordered) - 1, int(n * step))] for n in range(test_rows)}
    return [
        task._replace(slice_=TEST if index in held else TRAIN)
        for index, task in enumerate(tasks)
    ]


def queue(
    reference_dir: Path, corpus_dir: Path, settings: config.Settings, *, count: int | None
) -> int:
    """Write the work queue: which articles to summarize, and the turns to answer.

    Extends rather than replaces. Anything already written into `assistant` is
    carried across untouched, so running this again after the corpus rolls tops
    the queue up instead of throwing away an afternoon of authoring.
    """
    finetune = settings.app.finetune
    want = finetune.reference_rows if count is None else count
    rows = corpus.read_rows(corpus_dir)
    if not rows:
        print(f"no corpus rows under {corpus_dir.as_posix()}")
        return 1

    held = read_queue(reference_dir)
    done = {task.url_key: task for task in held}
    candidates = [
        task
        for task in _tasks_from_corpus(rows, settings.app.summarize)
        if task.url_key not in done
    ]
    picked = spread(candidates, want=max(0, want - len(held)))
    tasks = assign_slices([*held, *picked], test_rows=finetune.reference_test_rows)
    # A task somebody has already answered keeps the answer and the slice it was
    # answered under; re-slicing it would move a read row into the training half.
    tasks = [done.get(task.url_key, task) if done.get(task.url_key) else task for task in tasks]
    write_queue(reference_dir, tasks)

    print(f"{'corpus rows read':<{_WIDTH}} {len(rows)}")
    print(f"{'already queued':<{_WIDTH}} {len(held)}")
    print(f"{'added':<{_WIDTH}} {len(picked)}")
    print(f"{'queue now':<{_WIDTH}} {len(tasks)} of a {want}-row target")
    print(f"{'answered':<{_WIDTH}} {sum(1 for task in tasks if task.assistant)}")
    _print_spread(tasks)
    print(f"queue is {shown(queue_path(reference_dir))}")
    return 0


def _print_spread(tasks: Sequence[Task]) -> None:
    for label, counts in (
        ("slice", Counter(task.slice_ for task in tasks)),
        ("band", Counter(str(task.band) for task in tasks)),
        ("source_form", Counter(task.source_form for task in tasks)),
        ("vertical", Counter(task.vertical for task in tasks)),
    ):
        for name, count in sorted(counts.items(), key=lambda pair: (-pair[1], pair[0])):
            print(f"  {label} {name:<24} {count:>5}")


# --- check -----------------------------------------------------------------


class Fault(NamedTuple):
    url_key: str
    reason: str


def target_is_shaped_right(
    task: Task, *, settings: config.Settings
) -> tuple[CorpusRow | None, str | None]:
    """The authored answer as a row, or the reason a run would have refused it.

    Held to the same two rails production is: `draft_model` is the shape the
    constrained decoder is allowed to emit, and the band's word range is what the
    system turn asked for. A reference the decoder would reject teaches the model
    to be rejected; a reference outside its band teaches it to ignore the ask.
    """
    if not task.assistant:
        return None, "not answered yet"
    try:
        drafted = json.loads(task.assistant)
    except json.JSONDecodeError as error:
        return None, f"assistant is not JSON: {error.msg}"

    shape = summarize.draft_model(settings.app.summarize, settings.app.evaluation)
    try:
        draft = shape(**drafted)
    except (ValidationError, TypeError) as error:
        return None, f"the decoder would reject it: {type(error).__name__}"

    band = settings.app.summarize.bands[task.band]
    words = len((draft.summary or "").split())
    if not band.target_words_min <= words <= band.target_words_max:
        return None, (
            f"{words} words, outside band {task.band}'s "
            f"{band.target_words_min}-{band.target_words_max}"
        )

    system = summarize.system_prompt(
        settings.app.summarize, source_words=band.min_source_words
    )
    return (
        CorpusRow(
            version=CorpusRow.schema_version(),
            messages=[
                ChatTurn(role=ChatRole.SYSTEM, content=system),
                ChatTurn(role=ChatRole.USER, content=task.user),
                ChatTurn(
                    role=ChatRole.ASSISTANT,
                    content=json.dumps(
                        draft.model_dump(), ensure_ascii=False, separators=(", ", ": ")
                    ),
                ),
            ],
            url_key=task.url_key,
            date=task.date,
            model_id=settings.app.finetune.teacher,
            vertical=task.vertical,
        ),
        None,
    )


def check(
    reference_dir: Path, corpus_dir: Path, settings: config.Settings, *, write: bool
) -> int:
    """Refuse what a run would refuse, then say how much is left to write."""
    tasks = read_queue(reference_dir)
    if not tasks:
        print(f"no queue under {reference_dir.as_posix()}. Run `queue` first")
        return 1

    built: dict[str, CorpusRow] = {}
    faults: list[Fault] = []
    unanswered = 0
    for task in tasks:
        row, reason = target_is_shaped_right(task, settings=settings)
        if row is not None:
            built[task.url_key] = row
        elif reason == "not answered yet":
            unanswered += 1
        else:
            faults.append(Fault(task.url_key, reason or "unknown"))

    answered = [task for task in tasks if task.url_key in built]
    train = {task.url_key for task in answered if task.slice_ == TRAIN}
    test = {task.url_key for task in answered if task.slice_ == TEST}
    both = train & test
    shared = {row.url_key for row in corpus.read_rows(corpus_dir)} & set(built)
    held_out = corpus.read_holdout(corpus_dir) & train

    finetune = settings.app.finetune
    print(f"{'queued':<{_WIDTH}} {len(tasks)} of a {finetune.reference_rows}-row target")
    print(f"{'answered and valid':<{_WIDTH}} {len(built)}")
    print(f"{'still to write':<{_WIDTH}} {unanswered}")
    print(f"{'train / test':<{_WIDTH}} {len(train)} / {len(test)}")
    for fault in faults[:20]:
        print(f"  refused {fault.url_key[:12]} {fault.reason}")
    if len(faults) > 20:
        print(f"  ... and {len(faults) - 20} more")

    failed = False
    if both:
        print(f"a url_key is on both sides of the train/test line: {sorted(both)[:3]}")
        failed = True
    if shared:
        print(
            f"{len(shared)} articles are in the training window as well. One article "
            f"gets one target - drop them with:\n"
            f"  python backend/utilities/data_wrangler.py remove --yes "
            + " ".join(f"--url-key {key}" for key in sorted(shared)[:3])
            + (" ..." if len(shared) > 3 else "")
        )
        failed = True
    if held_out:
        print(f"{len(held_out)} reference-train keys are in the corpus holdout")
        failed = True
    if faults:
        failed = True

    _print_spread(answered)

    if write and not failed:
        ordered = sorted(built.values(), key=lambda row: (row.date, row.url_key))
        path = rows_path(reference_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(".jsonl.tmp")
        temp.write_text(
            "".join(corpus.to_line(row) for row in ordered), encoding="utf-8", newline=""
        )
        temp.replace(path)
        print(f"wrote {len(ordered)} rows to {shown(path)}")
    elif write:
        print("refusing to write while anything above is unresolved")

    return 1 if failed else 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reference-dir", type=Path, default=REPO_ROOT / REFERENCE_ROOT_RELPATH
    )
    parser.add_argument(
        "--corpus-dir", type=Path, default=REPO_ROOT / corpus.CORPUS_ROOT_RELPATH
    )
    parser.add_argument("--config", type=Path, default=config.DEFAULT_CONFIG_DIR)
    verbs = parser.add_subparsers(dest="verb", required=True)

    asked = verbs.add_parser("queue", help="Sample articles to summarize. Extends, never replaces.")
    asked.add_argument(
        "--count",
        type=int,
        default=None,
        help="Queue length to aim for. Defaults to finetune.reference_rows.",
    )

    checked = verbs.add_parser(
        "check", help="Refuse what a run would refuse, and count what is left."
    )
    checked.add_argument(
        "--write",
        action="store_true",
        help="Also write reference.jsonl, if nothing is unresolved.",
    )

    args = parser.parse_args(argv)
    settings = config.load(args.config)
    if args.verb == "queue":
        return queue(args.reference_dir, args.corpus_dir, settings, count=args.count)
    return check(args.reference_dir, args.corpus_dir, settings, write=args.write)


if __name__ == "__main__":
    sys.exit(main())
