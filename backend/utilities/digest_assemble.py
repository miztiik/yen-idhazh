"""How are derived digest outputs rebuilt from fresh data and completed incoming artifacts?"""

from __future__ import annotations

import dataclasses
import hashlib
import re
import shutil
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from datetime import date as date_type
from pathlib import Path
from uuid import uuid4

from idhazh import completed_writes, config, corpus
from idhazh.contracts.file_envelope import Period
from idhazh.contracts.knobs.collect import UNBOUNDED_WINDOW
from idhazh.contracts.ledger_index import CompactIndex, EntryState
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.ledgers import Grain
from idhazh.contracts.publication_inventory import PublicationInventory
from idhazh.ledger import paths, staging
from idhazh.path_classes import DERIVED
from utilities.publication_git import Repository
from utilities.publication_inputs import ledger_window, materialize
from utilities.publication_request import (
    IntegrityError,
    PublicationRequest,
    Write,
    contains,
    safe_file,
)

INVENTORY = "frontend/public/publication.json"


def _input_window(which: LedgerName, settings: config.Settings) -> int:
    window = max(
        settings.app.console.max_window_days,
        settings.appearance.console.max_window_days,
        max(settings.app.observability.full_grain_months().values()) * 31,
        settings.app.collect.reliability_window_days,
    )
    if which is LedgerName.SEEN:
        return max(window, settings.app.collect.seen_window_days + 1)
    if which is LedgerName.PUBLISHED:
        return max(window, settings.app.collect.published_window_days + 1)
    return window


def input_paths(*, date: str, settings: config.Settings) -> tuple[str, ...]:
    """A configured period window plus named records, indexes and current-month days."""
    through = date_type.fromisoformat(date)
    asked: set[str] = {
        INVENTORY,
        "corpus/corpus.jsonl",
        "corpus/corpus.meta.json",
        f"frontend/public/digest/{date[:7].replace('-', '/')}",
    }
    for which in staging.REGISTRY:
        grain = paths.entry(which).grain
        if grain is Grain.RAW_AND_COMPACT:
            asked.update(ledger_window(which, through=date, days=_input_window(which, settings)))
        elif grain is Grain.FLAT:
            asked.add(paths.relpath(which))
    # Search-index rebuilding opens only this month; same-story reads an earlier
    # configured day window. Days and manifests are concrete inputs, not the archive.
    earlier = max(31, int(settings.app.assemble.same_story_window_hours // 24) + 1)
    for offset in range(earlier):
        stamp = (through - timedelta(days=offset)).isoformat().replace("-", "/")
        asked.add(f"frontend/public/digest/{stamp}")
        asked.add(f"state/digest-fragments/{stamp}")
        asked.add(f"state/day-metrics/{stamp[:7]}")
    for path in DERIVED:
        rendered = path.format(day_dir=f"frontend/public/digest/{date.replace('-', '/')}")
        # The files inside these derived roots are named by the fresh inventory,
        # below. A root here must never expand into all historical month shards.
        if Path(rendered).suffix:
            asked.add(rendered)
    return tuple(sorted(asked))


def resolved_inputs(
    git: Repository, tree: str, *, date: str, settings: config.Settings
) -> tuple[str, ...]:
    """Resolve permanent heads and recorded-day windows from three named indexes."""
    from idhazh import ledger

    asked = set(input_paths(date=date, settings=settings))
    count = max(
        settings.app.console.max_window_days,
        settings.app.collect.reliability_window_days,
        ledger.HEALTH_WINDOW_DAYS,
    )
    through = max(date_type.fromisoformat(date), datetime.now(UTC).date())
    cutoff = through - timedelta(
        days=max(count, max(settings.app.observability.full_grain_months().values()) * 31) - 1
    )
    permanent = (LedgerName.FEED_RETIREMENTS, LedgerName.VISUAL_PRUNES)
    unbounded_published = settings.app.collect.published_window_days == UNBOUNDED_WINDOW
    if unbounded_published:
        # This existing configuration guarantees that no ledger row predates this year.
        first = date_type(int(config._gardener_config(git.repo / "config").first_ledger_year), 1, 1)
        if first > through:
            raise IntegrityError("configured first ledger year is after the input day")
        asked.update(
            ledger_window(
                LedgerName.PUBLISHED, through=through.isoformat(), days=(through - first).days + 1
            )
        )
    published = tuple(settings.app.ledger.published)
    promised: set[tuple[str, str]] = set()
    for which in dict.fromkeys(
        (
            *permanent,
            LedgerName.FEED_HEALTH,
            LedgerName.ITEM_HEALTH,
            LedgerName.PUBLISHED,
            *published,
        )
    ):
        asked.update(
            ledger_window(which, through=through.isoformat(), days=(through - cutoff).days + 1)
        )
        days: set[str] = set()
        newest: date_type | None = None
        compact_root = paths.compact_folder(Path("state"), which).as_posix()
        has_compact_tree = git.entry(tree, compact_root) is not None
        for period in Period:
            index_path = paths.compact_index_path(Path("state"), which, period).as_posix()
            entry = git.entry(tree, index_path)
            if entry is None:
                if has_compact_tree:
                    raise IntegrityError("required compact index is absent", (index_path,))
                continue
            git.parents_safe(tree, index_path)
            if entry.mode != "100644":
                raise IntegrityError("required index is not a plain data file", (index_path,))
            index = CompactIndex.model_validate_json(git.blob(entry.oid, fetches=True))
            if index.ledger != which or index.period != period:
                raise IntegrityError(
                    "required index declares another ledger or period", (index_path,)
                )
            for row in index.entries:
                covered_days = (
                    [row.covers]
                    if period is Period.DAILY
                    else ledger.month_days(row.covers)
                    if period is Period.MONTHLY
                    else ledger.month_days(f"{row.covers}-12")
                )
                last_day = date_type.fromisoformat(covered_days[-1])
                newest = max(newest, last_day) if newest is not None else last_day
                if row.state is not EntryState.PACKED:
                    continue
                compact = paths.compact_path(Path("state"), which, period, row.covers)
                pair = tuple(
                    compact.with_suffix(suffix).as_posix() for suffix in (".json", ".parquet")
                )
                promised.add((pair[0], pair[1]))
                if which in permanent or (which is LedgerName.PUBLISHED and unbounded_published):
                    asked.update(pair)
                if period is Period.DAILY:
                    days.add(row.covers)
                else:
                    months = (
                        [row.covers]
                        if period is Period.MONTHLY
                        else [f"{row.covers}-{month:02d}" for month in range(1, 13)]
                    )
                    for month in months:
                        days.update(ledger.month_days(month))
        for recorded_day in sorted(days)[-count:]:
            asked.update(ledger_window(which, through=recorded_day, days=1))
        if which in published and newest is not None:
            build_window = settings.appearance.console.max_window_days
            asked.update(ledger_window(which, through=newest.isoformat(), days=build_window))
            asked.update(
                ledger_window(
                    which,
                    through=(newest + timedelta(days=build_window)).isoformat(),
                    days=build_window,
                )
            )
    for pair in promised:
        if any(path in asked for path in pair) and not any(
            git.entry(tree, path) is not None for path in pair
        ):
            raise IntegrityError("required packed input is absent from its source tree", pair)
    return tuple(sorted(asked))


def preparation(
    repo: Path, original: PublicationRequest, *, date: str, settings: config.Settings
) -> Callable[[str, PublicationRequest], PublicationRequest]:
    """Keep incoming raw bytes; regenerate derived files without calling any judge/model."""
    from idhazh.stages import common

    git = Repository(repo)
    plan = common._load_plan(date, original.identity.run_id)
    if plan is None:
        raise IntegrityError("completed assemble has no own run plan")
    incoming = (
        corpus.harvest_rows(
            corpus.scored_from_items(common.VAR_ROOT / date / "items"),
            date=date,
            prompt_config=settings.app.summarize,
            evaluation=settings.app.evaluation,
        )
        if "corpus/corpus.jsonl" in original.writes
        else []
    )
    original_meta = (
        corpus.read_meta(repo / "corpus") if "corpus/corpus.jsonl" in original.writes else None
    )
    scopes = original.preparation_scopes
    immutable = {
        path: write
        for path, write in original.writes.items()
        if not any(contains(scope, path) for scope in scopes)
    }

    def prepare(base: str, active: PublicationRequest) -> PublicationRequest:
        from idhazh.cli import shard_count
        from idhazh.publication_checks import runner as checks
        from idhazh.stages import assemble as producer

        scratch = repo / "backend" / "var" / "publication" / f"assemble-{uuid4().hex}"
        scratch.mkdir(parents=True)
        try:
            materialize(
                git, base, resolved_inputs(git, base, date=date, settings=settings), scratch
            )
            inventory_file = scratch / INVENTORY
            if inventory_file.is_file():
                inventory = PublicationInventory.read(inventory_file)
                # Named projection shards in the configured window, not a directory census.
                names = [
                    f"frontend/public/{entry.path}"
                    for entry in inventory.entries
                    if entry.root == "public"
                    and not entry.path.startswith("digest/")
                    and any(
                        contains(scope.removeprefix("frontend/public/"), entry.path)
                        for scope in scopes
                        if scope.startswith("frontend/public/")
                    )
                    and (
                        not (period := re.search(r"(\d{4})[-/](\d{2})", entry.path))
                        or "-".join(period.groups())
                        >= (
                            date_type.fromisoformat(date)
                            - timedelta(
                                days=max(
                                    settings.app.console.max_window_days,
                                    max(settings.app.observability.full_grain_months().values())
                                    * 31,
                                )
                            )
                        ).isoformat()[:7]
                    )
                ]
                materialize(git, base, names, scratch)
            for path in original.writes:
                if any(contains(scope, path) for scope in scopes):
                    continue
                target = safe_file(scratch, path, exists=False)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((repo / path).read_bytes())
            assets = [
                path
                for path in original.writes
                if path.startswith(f"frontend/public/digest/{date.replace('-', '/')}/")
                and Path(path).name not in {"digest.json", "run.json"}
            ]
            for path in assets:
                # The first published asset for an item wins, even when this
                # invocation rendered other bytes for the same item.
                if git.entry(base, path) is None:
                    target = safe_file(scratch, path, exists=False)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes((repo / path).read_bytes())
            previous = common.STATE_ROOT, common.PUBLIC_ROOT
            common.STATE_ROOT = scratch / "state"
            common.PUBLIC_ROOT = scratch / "frontend" / "public" / "digest"
            try:
                with completed_writes.collect() as rebuilt:
                    producer.stage_assemble(
                        plan,
                        settings=settings,
                        commit_sha=original.identity.git_sha,
                        runner="ubuntu-latest",
                        shards=shard_count(len(plan.items), run=settings.app.run),
                        regenerate_only=True,
                    )
            finally:
                common.STATE_ROOT, common.PUBLIC_ROOT = previous
            if original_meta is not None:
                current = corpus.read_meta(scratch / "corpus")
                kept = corpus.roll(
                    corpus.read_rows(scratch / "corpus"),
                    incoming,
                    window=settings.app.finetune.corpus_rows,
                )
                dates = [
                    day
                    for day in (current.harvested_date, original_meta.harvested_date)
                    if day is not None
                ]
                meta = corpus.census(
                    kept,
                    previous=current.model_copy(
                        update={"harvested_date": max(dates) if dates else None}
                    ),
                    prompt_digest=original_meta.prompt_digest or "",
                )
                corpus.refuse_a_miscounted_census(kept, meta)
                with completed_writes.collect() as rolled:
                    corpus.write(scratch / "corpus", kept, meta)
                rebuilt.update(rolled)
            if checks.run_publication_checks(
                scratch / "frontend" / "public" / "digest", only=(date,)
            ):
                raise RuntimeError("rebuilt digest failed publication consistency checks")
            writes = {
                path: dataclasses.replace(write, baseline=git.entry(base, path), baseline_tip=base)
                for path, write in immutable.items()
            }
            for target, digest in rebuilt.items():
                path = target.relative_to(scratch).as_posix()
                if not any(contains(scope, path) for scope in scopes):
                    raise IntegrityError("rebuild wrote outside derived declaration", (path,))
                writes[path] = Write(digest, git.entry(base, path), baseline_tip=base)
            for path in assets:
                target = scratch / path
                if not target.is_file():
                    raise IntegrityError("completed asset disappeared during rebuild", (path,))
                writes[path] = Write(
                    hashlib.sha256(target.read_bytes()).hexdigest(),
                    git.entry(base, path),
                    baseline_tip=base,
                )
            # No partial derived set is copied into the publication source until
            # the producer and all consistency checks have succeeded.
            copied = writes.keys() - immutable.keys()
            head = git.git("rev-parse", "HEAD").strip()
            for path in copied:
                target = safe_file(repo, path, exists=False)
                baseline = git.entry(head, path)
                if git.index_entry(path) != baseline:
                    raise IntegrityError("rebuild would touch foreign staged output", (path,))
                if target.exists():
                    previous_write = active.writes.get(path)
                    expected = (
                        previous_write.sha256
                        if previous_write is not None
                        else hashlib.sha256(git.blob(baseline.oid, fetches=True)).hexdigest()
                        if baseline is not None
                        else None
                    )
                    if hashlib.sha256(target.read_bytes()).hexdigest() != expected:
                        raise IntegrityError("rebuild would replace foreign local output", (path,))
            for path in copied:
                (repo / path).parent.mkdir(parents=True, exist_ok=True)
                (repo / path).write_bytes((scratch / path).read_bytes())
            return dataclasses.replace(active, source_tip=base, writes=writes)
        finally:
            shutil.rmtree(scratch)

    return prepare
