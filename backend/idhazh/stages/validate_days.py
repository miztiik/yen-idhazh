"""Committed days against the two contracts their readers hold.

One stage, one module. `idhazh.cli` chooses which stage runs and holds no stage
body of its own (CLAUDE.md section 1a, "A router is the sharpest case").
"""

from __future__ import annotations

import csv
import hashlib
import inspect
import json
from collections import Counter
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Final

from pydantic import ValidationError

from idhazh import (
    ledger,
    publish_console,
    publish_console_band,
    publish_day_metrics,
    publish_feed_health,
    publish_machine,
    publish_run_days,
    publish_scores,
    publish_span_rollup,
    publish_telemetry,
)
from idhazh.contracts.base import canonical_json
from idhazh.contracts.day_validation import DayValidationReceipt
from idhazh.contracts.digest_day import DigestDay
from idhazh.contracts.digest_view import DigestView
from idhazh.render.write import assets_in_day
from idhazh.stages.common import LOG, published_days


def _picture_faults(public_root: Path, day: DigestDay) -> list[str]:
    """Where a day's payload and its picture directory disagree.

    The defect this exists for shipped on 2026-08-24. A per-process counter that
    restarted at 1 let a later run of the day overwrite an earlier run's
    `india-01.svg` while the payload still named both items, so 32 declared
    visuals sat over 18 files and 14 files were each claimed by two stories. 28
    readers saw a picture and 14 of those were drawn from another article's
    numbers, under alt text describing figures that were not in the image.
    Nothing failed: every file existed, every item validated, the page rendered.

    Three disagreements, three different faults. Two stories on one path means
    one of them shows the other's chart. A path with no file is a broken image.
    A file no story names is weight against the 1 GB Pages cap (Guardrail #2) that
    renders nowhere, and it is what a repaired collision leaves behind.

    **A visual's data file is held to the same three** now that it is the only
    file a visual publishes: it is filed under the item's id in the day
    directory and fetched by the reader's browser, so every way a drawing and
    its payload could disagree is a way these can (2026-09-13).

    It is checked here rather than by a test per committed day because the day
    that can still be wrong is the one being written. A day already published is
    frozen, and re-checking every one of them costs more every day the pipeline
    runs (Guardrail #12).

    **The 24 days published before the browser drew anything declare no data
    file at all**, so they report nothing here and that is the correct reading:
    their drawings are deleted and no payload names one.
    """
    declared = [
        item.visual.data_path
        for item in day.items
        if item.visual is not None and item.visual.data_path is not None
    ]
    faults: list[str] = []
    shared = sorted(name for name, claims in Counter(declared).items() if claims > 1)
    if shared:
        faults.append(f"names one picture on two stories: {shared}")
    absent = sorted(name for name in declared if not (public_root / name).is_file())
    if absent:
        faults.append(f"names a picture file that is not there: {absent}")
    orphans = sorted(assets_in_day(public_root, day.date) - set(declared))
    if orphans:
        faults.append(f"carries picture files no story names: {orphans}")
    return faults


def _census_faults(day: DigestDay) -> list[str]:
    """A day whose planned stories are neither published nor counted as failed.

    **An empty day is not a fault, and two of them are normal.** A day that
    planned nothing published nothing: the pipeline found no new article, so
    `partial` is false and the console paints it amber, which is the correct
    reading (`backend/utilities/build_canary_day.py::quiet_day`). A day where
    everything failed publishes empty and says `partial`, because a run that
    publishes nothing on a bad day is a run whose bad days are invisible
    (`idhazh.stages.assemble`). 2026-09-14 is the second kind and stays
    published - refusing it would delete the only record that the day went
    wrong.

    The third empty day is the one nothing can write honestly: stories were
    planned, none failed, and none came out. `ItemOutcome` has two members, so
    every story the pipeline touched is `ok` or `failed`, and `items_planned` is
    never below `len(items) + items_failed` - a day holding neither has lost its
    whole plan with nothing recording where it went. On a reader's page and on
    the console it is indistinguishable from a quiet day, which is what makes it
    worth refusing rather than merely counting.

    `DigestDay` pins `partial` to `items_failed > 0` on its own. It cannot pin
    this one: what makes the day wrong is a plan the day itself is silent about,
    so the arithmetic only closes once, here, over the whole payload.
    """
    if day.items or not day.items_planned or day.items_failed:
        return []
    return [
        f"planned {day.items_planned} stories and accounts for none of them: "
        f"nothing published and nothing failed"
    ]


def _day_faults(path: Path, public_root: Path, *, payload: bytes | None = None) -> list[str]:
    """What is wrong with one committed day, in sentences, or an empty list.

    Both shapes are asked for, because a day has two readers and they read
    different files. `DigestDay` is what the build opens off disk. `DigestView`
    is the projection a reader's browser fetches, and a day that is fine on disk
    can still project to something the served contract refuses - a story with no
    key point, say, which the build never looked at because that story sits past
    the document's seed.

    `payload` is the file's bytes when the caller already holds them.
    `stage_validate_days` digests the same bytes it validates, and reading one
    file twice to answer two questions about one payload is the kind of cost
    this stage exists to remove. Passing nothing reads the file here, which is
    the only place that sentence about an unreadable day is written.
    """
    if payload is None:
        try:
            payload = path.read_bytes()
        except OSError as error:
            return [f"cannot be read: {error.strerror or error}"]
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError as error:
        return [f"is not JSON: {error}"]
    if not isinstance(parsed, dict):
        return [f"is a {type(parsed).__name__}, not a day"]

    faults: list[str] = []
    try:
        day = DigestDay.model_validate(parsed)
    except ValidationError as error:
        faults.append(f"fails digest-day.schema.json: {error.error_count()} problems\n{error}")
    else:
        faults.extend(_picture_faults(public_root, day))
        faults.extend(_census_faults(day))
    try:
        DigestView.project(parsed)
    except ValidationError as error:
        faults.append(f"fails digest-view.schema.json: {error.error_count()} problems\n{error}")
    except (TypeError, AttributeError, ValueError) as error:
        # A shape nobody anticipated. It still fails, and it still names the day
        # - a stack trace on day three of twelve says neither which day nor why.
        faults.append(f"cannot be projected for serving: {type(error).__name__}: {error}")
    return faults


DAY_VALIDATIONS_FILENAME: Final = "day-validations.csv"


def day_validations_path(state_dir: Path) -> Path:
    """`state/day-validations.csv`: which days have passed, and against what."""
    return state_dir / DAY_VALIDATIONS_FILENAME


def _validator_identity() -> str:
    """A digest of everything a committed day is checked against.

    A published day is frozen, so the only thing that can turn a pass into a
    failure is a move in the rules. This is what "the rules" means, spelled out
    so that nobody has to remember to bump it: the two generated schemas, and
    the source of the five functions that do the checking. Change a field, a
    constraint, an enum member or a line of `_day_faults`, `_picture_faults`,
    `_census_faults`, `assets_in_day` or `DigestView.project`, and this moves -
    which invalidates every receipt at once and re-validates the whole archive,
    once.

    It is derived rather than declared on purpose. A hand-maintained constant is
    a check that silently stops checking on the day somebody forgets it, and the
    failure would be invisible: the gate keeps printing a pass.

    The cost of deriving it is that a comment or a reformat inside one of those
    functions moves it too. That buys one full re-validation, which is what this
    stage did on every run before the receipt existed - the error is on the side
    of doing the work again rather than skipping it.
    """
    rules = (_picture_faults, _census_faults, _day_faults, assets_in_day, DigestView.project)
    material = canonical_json(
        {
            "digest_day": DigestDay.json_schema(),
            "digest_view": DigestView.json_schema(),
            "rules": [inspect.getsource(rule) for rule in rules],
        }
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _receipts_for(state_dir: Path, identity: str) -> dict[str, tuple[DayValidationReceipt, ...]]:
    """Every receipt each day carries under this validator.

    Only rows written under `identity` are kept: a row about an older validator
    says nothing about the rules in force, and dropping it here is what makes a
    rule change re-validate everything rather than nothing.

    A day can carry more than one row and both readings are legitimate. A closed
    day that `backfill.yml` re-encoded leaves a truthful new row beside a row
    about the payload that used to be there, and `merge=union` concatenates, so
    two branches that each validated one day leave two rows as well. The file
    cannot tell those apart and does not try - `_proved` asks the only question
    that settles it, which is what is on disk now.

    A row that will not parse is counted and skipped rather than raised on. The
    worst it can cost is the validation this record exists to avoid, and a
    publication must not be stopped by a bookkeeping file.
    """
    path = day_validations_path(state_dir)
    if not path.is_file():
        return {}
    held: dict[str, list[DayValidationReceipt]] = {}
    unreadable = 0
    with path.open("r", encoding="utf-8", newline="") as handle:
        for record in csv.DictReader(handle):
            try:
                receipt = DayValidationReceipt.from_csv_row(record)
            except (ValidationError, KeyError):
                unreadable += 1
                continue
            if receipt.validator_version == identity:
                held.setdefault(receipt.date, []).append(receipt)
    if unreadable:
        LOG.warning(
            "%s holds %s rows this build cannot read - those days will be opened again",
            path.name,
            unreadable,
        )
    return {date: tuple(rows) for date, rows in held.items()}


def _proved(held: Sequence[DayValidationReceipt], payload_bytes: int) -> bool:
    """Whether these receipts settle what is on disk at this length.

    The length comes from `os.stat`, which answers without opening the file -
    that is the whole saving, so the digest a receipt carries cannot be the
    thing consulted here. What the digest does is make a real contradiction
    visible: two rows claiming the same length and different bytes cannot both
    be about the payload that is there, so the day is read rather than trusted.

    A row whose length does not match is about a payload that is no longer
    there. It is ignored rather than held against the day, which is what lets a
    re-encoded day settle down again instead of being read for ever.
    """
    matching = {row.payload_digest for row in held if row.payload_bytes == payload_bytes}
    return len(matching) == 1


def _record_receipts(state_dir: Path, earned: list[DayValidationReceipt]) -> int:
    """Append what this run proved, skipping any row the file already carries.

    Append-only because `state/*.csv` is `merge=union` (`.gitattributes`): a
    rewrite that removed rows would be resolved by a union that puts them back,
    so the removal would silently not happen.
    """
    if not earned:
        return 0
    path = day_validations_path(state_dir)
    columns = DayValidationReceipt.csv_columns()
    already: set[tuple[str, ...]] = set()
    exists = path.is_file()
    if exists:
        ledger.require_matching_header(path, columns)
        with path.open("r", encoding="utf-8", newline="") as handle:
            already = {
                tuple(record.get(name, "") for name in columns) for record in csv.DictReader(handle)
            }
    rows = [receipt.csv_row() for receipt in earned]
    fresh = [row for row in rows if tuple(row[name] for name in columns) not in already]
    if not fresh:
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        if not exists:
            writer.writeheader()
        writer.writerows(fresh)
    return len(fresh)


def stage_validate_days(
    root: Path, only: Sequence[str] = (), *, state_dir: Path | None = None
) -> int:
    """Committed days against the two contracts their readers hold.

    **This exists because prerendering stopped proving it.** Until the reading
    decisions were split on 2026-09-01, every story a day published was serialised
    into a document at build time, so a story the contract refused took the
    build down before it could be merged. A reading document now carries a seed
    and a browser fetches the rest, so the build never opens the stories past
    the seed and a broken one reaches a reader instead of a log. The guarantee
    is weaker than it was and it is written down rather than hidden: a broken
    day can no longer be built, it can only no longer be merged.

    `only` names the days to open, as `YYYY-MM-DD`. Naming a day is how a run
    says it just wrote that day, so a named day is always opened and its receipt
    is never consulted. Empty means every committed day.

    **A frozen day is not re-validated, and that is a receipt rather than a
    clock.** A published day cannot stop matching a contract on its own - the
    only thing that can happen to it is deletion - so what invalidates a pass is
    a move in the rules, not the passage of time. `state/day-validations.csv`
    records the day, the length and digest of the payload that passed, and
    `_validator_identity`. A later run skips a day whose receipt names this
    validator and whose recorded length still matches `os.stat`, and never opens
    the payload. `state_dir` is where those receipts live; pass nothing and every
    day named is validated, which is what this did before the receipt existed.

    **On the first run against a tree with no receipts every day is validated**,
    exactly as before, and every day that passes earns a receipt. Nothing is
    skipped on trust it has not earned, so the machinery costs a full sweep once
    and then costs a `stat` a day. The same thing happens after a rule change,
    which is the whole point: the archive is re-validated once, not on a window.

    Measured 2026-09-08 on an Intel Core i7-1265U: 18 committed days,
    19,867,266 bytes, 0.45 s median over three runs against 0.02 s with every
    receipt current, and one day more every day nobody writes any code
    (Guardrail #12).

    An empty tree fails, and so does a named day that is not there. A validator
    that checked nothing prints the same line as one that checked every day,
    which is the failure `site-weight` already has a rule about.
    """
    days = published_days(root)
    if not days:
        LOG.error(
            "validate-days found no digest.json under %s - a run over nothing passes "
            "every contract",
            root.as_posix(),
        )
        return 1

    if only:
        wanted = set(only)
        days = [path for path in days if _day_of(path) in wanted]
        missing = sorted(wanted - {_day_of(path) for path in days})
        if missing:
            LOG.error("validate-days was asked for days that are not committed: %s", missing)
            return 1

    identity = _validator_identity() if state_dir is not None else ""
    # A named day was just written by this run, so its receipt is about the
    # payload that stood there before it. Nothing to consult.
    held = _receipts_for(state_dir, identity) if state_dir is not None and not only else {}

    broken = 0
    skipped = 0
    earned: list[DayValidationReceipt] = []
    for path in days:
        date = _day_of(path)
        if _proved(held.get(date, ()), path.stat().st_size):
            skipped += 1
            continue
        try:
            payload: bytes | None = path.read_bytes()
        except OSError:
            payload = None
        faults = _day_faults(path, root.parent, payload=payload)
        broken += bool(faults)
        for fault in faults:
            LOG.error("%s %s", date, fault)
        if not faults and payload is not None and state_dir is not None:
            earned.append(
                DayValidationReceipt(
                    version=DayValidationReceipt.schema_version(),
                    date=date,
                    payload_bytes=len(payload),
                    payload_digest=hashlib.sha256(payload).hexdigest(),
                    validator_version=identity,
                )
            )

    if broken:
        LOG.error(
            "validate-days: %s of %s committed days do not match the contracts their "
            "readers hold. A reader's browser fetches this file and cannot be upgraded",
            broken,
            len(days),
        )
        return 1

    touched = {_day_of(path)[:7] for path in days} if only else None
    console_faults = _console_payload_faults(root, touched)
    for fault in console_faults:
        LOG.error("validate-days %s", fault)
    if console_faults:
        LOG.error(
            "validate-days: %s console payload(s) do not match the schema the console "
            "fetches them under",
            len(console_faults),
        )
        return 1

    if state_dir is not None:
        LOG.info("validate-days: recorded %s receipts", _record_receipts(state_dir, earned))
    LOG.info(
        "validate-days: %s committed days match both contracts, %s of them opened",
        len(days),
        len(days) - skipped,
    )
    return 0


def _console_payload_faults(root: Path, months: set[str] | None) -> list[str]:
    """The console's own payloads, read back through the shapes that wrote them.

    Data hygiene belongs here and not in pytest (`CLAUDE.md` section 13): this
    is the producer's own gate on what it just wrote, and it runs where the
    payload is - in CI, against the committed tree.

    `months` names the months this run touched, which is what the day workflow
    passes. None means every month still on disk, which is the sweep `ci.yml`
    takes on a change that can move a contract - and reading everything is the
    point of that case, because a contract change can invalidate any file.

    Six of the seven directories are trimmed on every assemble by
    `publish_console.prune_months`, so the sweep opens at most their own
    `public_*_keep_months` files. `telemetry` is the exception and says so here
    rather than in a sentence that would be wrong: its deletion lives in
    `retention.prune_telemetry`, inside the workflow step that ships
    `--dry-run`, so `public_telemetry_keep_months` is declared and not yet
    enforced and that directory gains one file a month. The daily case is
    unaffected - it opens only the months the run wrote.

    The band is checked every time whatever `months` says. It is one small file
    and it is the first thing the console asks for, so a band that will not load
    is a console with no verdict at all.
    """
    faults: list[str] = []
    readers: tuple[tuple[str, str, Callable[[Path], object]], ...] = (
        (publish_scores.DIRNAME, publish_scores.SUFFIX, publish_scores.read_shard),
        (publish_feed_health.DIRNAME, publish_feed_health.SUFFIX, publish_feed_health.read_shard),
        (publish_machine.DIRNAME, publish_machine.SUFFIX, publish_machine.read_shard),
        (publish_span_rollup.DIRNAME, publish_span_rollup.SUFFIX, publish_span_rollup.read_shard),
        (
            publish_day_metrics.PUBLIC_DIRNAME,
            publish_day_metrics.PUBLIC_SUFFIX,
            publish_day_metrics.read_public_shard,
        ),
        (publish_run_days.DIRNAME, publish_run_days.SUFFIX, publish_run_days.read_shard),
        (publish_telemetry.PUBLIC_TELEMETRY_DIRNAME, ".csv", publish_telemetry.read_shard),
    )
    for dirname, suffix, read in readers:
        for month in publish_console.published_months(root, dirname, suffix):
            if months is not None and month not in months:
                continue
            path = publish_console.month_path(root, dirname, month, suffix)
            try:
                read(path)
            except (ValueError, ValidationError, OSError) as fault:
                faults.append(f"{publish_console.relpath(dirname, path.name)}: {fault}")
    band = publish_console_band.band_path(root)
    if band.is_file():
        try:
            publish_console_band.read_band(band)
        except (ValueError, ValidationError, OSError) as fault:
            faults.append(f"{publish_console_band.BAND_RELPATH}: {fault}")
    elif band.parent.is_dir():
        # A console directory with no band in it is a producer that ran and
        # wrote nothing, which is a fault. No console directory at all is a tree
        # no producer has ever run over - a fixture, or a checkout mid-migration -
        # and this gate cannot tell that from broken, so it says nothing. What
        # guarantees the real tree has one is the committed seed, which
        # `test_every_path_the_day_stages_exists_in_a_fresh_checkout` asks for.
        faults.append(f"{publish_console_band.BAND_RELPATH} is missing")
    return faults


def _day_of(path: Path) -> str:
    """`2026-09-01` out of `.../2026/09/01/digest.json`, for a log line."""
    parts = path.parts[-4:-1]
    return "-".join(parts) if len(parts) == 3 else path.as_posix()
