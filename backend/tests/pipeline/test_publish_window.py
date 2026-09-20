"""What survives a crash between the day being written and the ledger being published?"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest
from conftest import CONFIG_DIR, CONTRACT_FIXTURES_DIR, FIXTURES_DIR, REPO_ROOT, read_text
from pydantic import ValidationError
from pytest import MonkeyPatch

from idhazh import assemble, config, ledger, rank, telemetry
from idhazh.contracts.article import Article
from idhazh.contracts.base import StalePayloadError
from idhazh.contracts.digest_day import DigestDay
from idhazh.contracts.feed_health import FetchOutcome
from idhazh.contracts.item_health import FailureCode, ItemHealthRow, ItemOutcome, TimeSource
from idhazh.contracts.run_manifest import RunManifest
from idhazh.contracts.run_plan import RunPlan, VerticalPlan
from idhazh.contracts.sources import FeedDef, SourceForm
from idhazh.contracts.taxonomy import LifecycleStatus, SourceKind, SourceTier
from idhazh.contracts.visual_decision import VisualDecision
from idhazh.fetch import FetchResult
from idhazh.stages import common
from idhazh.stages.assemble import _published_rows, stage_assemble
from idhazh.stages.common import _item_payloads, _load_manifest, shard_of
from idhazh.stages.compact import stage_compact
from idhazh.stages.plan import _next_run_n, stage_plan
from idhazh.stages.record import stage_record
from idhazh.stages.work import stage_work
from idhazh.telemetry.silicon import stage_job_clock

from ._builders import (
    FULL_TEXT,
    article,
    captured_article_fetch,
    closed_loopback_endpoint,
    digest_item,
    isolate_ledgers,
    plan,
    row,
    score_one_item,
    summary,
)

pytestmark = pytest.mark.slow


def test_a_crash_before_the_published_ledger_costs_the_replay_nothing(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """`stage_assemble` writes `digest.json` and appends the published ledger tens
    of lines later, so a run that dies in that gap leaves a committed day the
    ledger never heard of. The plan-time guard reads that ledger, so the next run
    offers every one of those addresses again - and `build_day`'s `already` set is
    what makes the replay cost nothing.

    That is the reason the two docstrings give since 2026-09-12. The reason they
    used to give was link stability, and it is retired: both render paths re-sort
    the day, so the published order reaches no reader.

    The crash is the on-disk state a crash leaves rather than a patched function:
    the day file stays and the day's ledger file is removed. Driven from the
    committed run-plan fixture and never from the archive (CLAUDE.md section 13).
    """
    run_plan = plan()
    settings = config.load(CONFIG_DIR)
    isolate_ledgers(tmp_path, monkeypatch)
    items_dir = tmp_path / "run" / run_plan.date / "items"
    state = tmp_path / "state"

    stage_work(
        run_plan,
        settings=settings,
        scorer=None,
        fetcher=captured_article_fetch,
        model_endpoint=closed_loopback_endpoint(),
    )
    score_one_item(items_dir, run_plan)
    stage_assemble(run_plan, settings=settings, commit_sha="a" * 40, runner="fixture")

    day_path = assemble.day_dir(common.PUBLIC_ROOT, run_plan.date) / "digest.json"
    published = DigestDay.from_json(read_text(day_path))
    assert published.items, "run 1 published nothing, so there is no window to test"

    ledger.published_path(state, run_plan.date).unlink()
    window = settings.app.collect.published_window_days
    assert not ledger.load_published(state, today=run_plan.date, within_days=window), (
        "the guard still holds these addresses, so this is not the crash the window leaves"
    )

    stage_assemble(
        run_plan.model_copy(update={"run_id": f"{run_plan.date}-2"}),
        settings=settings,
        commit_sha="a" * 40,
        runner="fixture",
    )

    replayed = DigestDay.from_json(read_text(day_path))
    assert [item.item_id for item in replayed.items] == [item.item_id for item in published.items]
    assert {item.introduced_by_run for item in replayed.items} == {1}


def stage_visual_payloads(run_plan: RunPlan, items_dir: Path, *, text: str) -> None:
    """One article and one OK summary per planned item, sharing one body."""
    items_dir.mkdir(parents=True, exist_ok=True)
    for item in run_plan.items:
        base_article = article().model_copy(
            update={
                "item_id": item.item_id,
                "url_key": item.url_key,
                "canonical_url": item.canonical_url,
                "source_url": item.canonical_url,
                "vertical": item.vertical,
                "rank_score": item.rank_score,
                "text": text,
            }
        )
        base_summary = summary().model_copy(
            update={"item_id": item.item_id, "url_key": item.url_key}
        )
        (items_dir / f"{item.item_id}.article.json").write_text(
            base_article.to_json(), encoding="utf-8"
        )
        (items_dir / f"{item.item_id}.summary.json").write_text(
            base_summary.to_json(), encoding="utf-8"
        )


def test_a_retired_feed_still_labels_the_items_it_published() -> None:
    """Splitting the feed lists must not cost an older item its name or its kind.

    A published item carries a `source_id` forever, and a feed can retire
    between the plan and the assemble of the same day - four times more often
    once the schedule moves to every six hours. Both label maps read the union,
    so the maps that would otherwise fall back to the raw slug and to
    `reporting` never get the chance.

    The fallback is the failure: publishing an announcement as reporting is the
    one thing `kind` was added to prevent.
    """
    sources = config.load(CONFIG_DIR).sources.model_copy(
        update={
            "feeds": [],
            "retired": [
                FeedDef(
                    id="defunct-daily",
                    vertical="ai",
                    title="Defunct Daily",
                    url="https://defunct.example.com/rss",
                    tier=SourceTier.INSTITUTION,
                    kind=SourceKind.ANNOUNCEMENT,
                    status=LifecycleStatus.RETIRED,
                    retired_on="2026-07-04",
                    weight=0.0,
                )
            ],
        }
    )
    assert assemble.source_names(sources)["defunct-daily"] == "Defunct Daily"
    assert assemble.source_kinds(sources)["defunct-daily"] is SourceKind.ANNOUNCEMENT


def test_abstract_items_publish_a_sentence_not_a_badge() -> None:
    item = assemble.to_digest_item(
        article=article().model_copy(update={"source_form": SourceForm.ABSTRACT}),
        summary=summary(),
        band=row().band,
        source_name="NBER",
        source_kind=SourceKind.RESEARCH,
        run_n=1,
    )

    assert item.source_form is SourceForm.ABSTRACT
    assert (
        item.reader_note
        == "This is a summary of the paper's abstract. The full paper is a PDF."
    )


def test_truncated_items_publish_the_partial_read_sentence() -> None:
    item = assemble.to_digest_item(
        article=article().model_copy(update={"truncated": True, "truncated_at_tokens": 2500}),
        summary=summary(),
        band=row().band,
        source_name="Example Lab",
        source_kind=SourceKind.REPORTING,
        run_n=1,
    )

    assert item.reader_note == "We could only read the first part of this page."


def test_the_published_item_carries_the_plan_rows_own_ranking_signal() -> None:
    """Nothing is recomputed at assemble: the four numbers are the plan's own.

    The published item is built from an article and a summary, and neither of
    them knows why the story was chosen. The plan row is the only place that
    fact still exists by this stage.
    """
    planned = plan().items[0].model_copy(update={"time_source": TimeSource.FEED})
    item = assemble.to_digest_item(
        article=article(),
        summary=summary(),
        band=row().band,
        source_name="Example Lab",
        source_kind=SourceKind.REPORTING,
        run_n=1,
        planned=planned,
    )

    assert item.carried_by == planned.carried_by == 3
    assert item.watchlist_hit == planned.watchlist_hit
    assert item.on_front_page == planned.on_front_page
    assert item.rank_score == planned.rank_score == 3.4
    assert item.on_front_page, "the fixture's first item did get an aggregator vote"
    assert item.time_source is TimeSource.FEED


def test_an_item_built_without_a_plan_row_publishes_no_signal_at_all() -> None:
    """Absent is unknown. A default here would be a claim nobody measured."""
    item = assemble.to_digest_item(
        article=article(),
        summary=summary(),
        band=row().band,
        source_name="Example Lab",
        source_kind=SourceKind.REPORTING,
        run_n=1,
    )

    assert item.carried_by is None, "1 would claim a count the run never took"
    assert item.watchlist_hit is None
    assert item.on_front_page is None, "false would deny a vote nobody counted"
    assert item.rank_score is None, "0.0 would put the story bottom of its desk"
    assert item.time_source is None


def cut_article(*, read: int, total: int | None, abstract: bool = False) -> Article:
    """One article cut at `read` words out of `total` before the cap."""
    return article().model_copy(
        update={
            "truncated": True,
            "truncated_at_tokens": 2500,
            "word_count": read,
            "source_word_count": total,
            "source_form": SourceForm.ABSTRACT if abstract else SourceForm.ARTICLE,
        }
    )


def test_the_cut_sentence_names_how_much_of_the_page_we_read() -> None:
    """One word cannot cover both ends of the real range, so the note carries a number.

    Both pairs are measured rows of `state/scores.csv` on 2026-08-29, the
    smallest and the largest of the 22 genuinely cut items: 1,923 words of
    1,948 is a 1.3 percent loss, and 1,923 of 8,442 is a 77.2 percent loss.
    Today both print the same sentence, which is the defect.
    """
    barely = assemble.reader_note(cut_article(read=1923, total=1948))
    mostly = assemble.reader_note(cut_article(read=1923, total=8442))

    assert barely == "We could only read the first 99 percent of this page."
    assert mostly == "We could only read the first 23 percent of this page."
    assert barely != mostly


def test_an_abstract_that_was_also_cut_carries_both_facts() -> None:
    """Returning on the first branch is the exact shape of a silent cut.

    Nothing in extract exempts an abstract from the cap: `truncate_to_tokens`
    runs on every body. It has never fired on one - the longest body the single
    abstract feed produced across 28 rows of `state/item-health/2026-08.csv` on
    2026-08-29 was 330 words against a 1,923-word cut point - so this is latent,
    not live. Latent is not a reason to leave it standing.
    """
    note = assemble.reader_note(cut_article(read=1320, total=5280, abstract=True))

    assert note == (
        "This is a summary of the paper's abstract. The full paper is a PDF. "
        "We could only read the first 25 percent of this page."
    )


def test_a_cut_page_of_unknown_length_states_no_scale() -> None:
    """A payload written before `source_word_count` existed cannot name a share.

    142 of the 2,683 rows in `state/scores.csv` carry no pre-cap length on
    2026-08-29. The note degrades to the sentence it already shipped rather
    than inventing a number or dropping the fact.
    """
    assert (
        assemble.reader_note(cut_article(read=1320, total=None))
        == "We could only read the first part of this page."
    )


def test_the_note_never_claims_we_read_the_first_100_percent() -> None:
    """A scale that rounds to all of it says the opposite of what happened."""
    assert (
        assemble.reader_note(cut_article(read=748, total=748))
        == "We could only read the first part of this page."
    )
    assert (
        assemble.reader_note(cut_article(read=1996, total=2000))
        == "We could only read the first part of this page."
    )


def test_an_uncut_article_of_full_length_says_nothing() -> None:
    assert assemble.reader_note(article()) is None


def test_a_day_publishes_even_when_items_failed() -> None:
    """A run that publishes nothing on a bad day is a run whose bad days are invisible."""
    day = assemble.build_day(
        plan=plan(),
        items=[digest_item()],
        previous=None,
        taxonomy=config.load(CONFIG_DIR).taxonomy,
        run_n=1,
        generated_at="2026-08-21T07:00:00Z",
        retention_window_months=-1,
    )
    assert day.partial
    assert day.items_failed > 0
    assert len(day.items) == 1


def test_item_payloads_include_an_article_without_a_summary(tmp_path: Path) -> None:
    items_dir = tmp_path / "items"
    items_dir.mkdir()
    (items_dir / "ai-01.article.json").write_text(article().to_json(), encoding="utf-8")

    payloads = list(_item_payloads(plan(), items_dir))

    assert [payload.planned.item_id for payload in payloads] == [
        item.item_id for item in plan().items
    ]
    assert payloads[0].article == article()
    assert payloads[0].summary is None


def test_an_item_written_before_a_contract_moved_says_so_at_the_stage_that_reads_it(
    tmp_path: Path,
) -> None:
    """The check that would have caught run 33951249328, where it actually bit.

    The visuals job wrote its payloads at 08:23, a field rename merged, and the
    rebuild opened them at 09:03 with the new contract. The stage reported that
    the payloads were invalid. They were not - they were written eight hundred
    seconds before the shape changed under them, and only the stamp can say so.
    """
    items_dir = tmp_path / "items"
    items_dir.mkdir()
    stale = json.loads(article().to_json())
    stale["version"] = "2026-01-01"
    stale["body"] = stale.pop("text")
    (items_dir / "ai-01.article.json").write_text(json.dumps(stale), encoding="utf-8")

    with pytest.raises(StalePayloadError) as raised:
        list(_item_payloads(plan(), items_dir))

    assert "2026-01-01" in str(raised.value)
    assert Article.schema_version() in str(raised.value)


def test_assemble_writes_one_item_health_row_per_planned_item(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    run_plan = plan()
    monkeypatch.setattr(common, "VAR_ROOT", tmp_path / "run")
    monkeypatch.setattr(common, "PUBLIC_ROOT", tmp_path / "public" / "digest")
    monkeypatch.setattr(common, "STATE_ROOT", tmp_path / "state")
    items_dir = tmp_path / "run" / run_plan.date / "items"
    items_dir.mkdir(parents=True)
    (items_dir / f"{run_plan.items[0].item_id}.article.json").write_text(
        article().to_json(), encoding="utf-8"
    )
    (items_dir / f"{run_plan.items[0].item_id}.summary.json").write_text(
        summary()
        .model_copy(update={"fetch_ms": 111, "extract_ms": 22, "summarize_ms": 333})
        .to_json(),
        encoding="utf-8",
    )

    day = stage_assemble(
        run_plan,
        settings=config.load(CONFIG_DIR),
        commit_sha="a" * 40,
        runner="fixture",
    )

    health_path = ledger.item_health_path(tmp_path / "state", run_plan.date)
    with health_path.open(encoding="utf-8", newline="") as handle:
        rows = [ItemHealthRow.from_csv_row(row) for row in csv.DictReader(handle)]
    failed = sum(1 for row in rows if row.outcome is ItemOutcome.FAILED)
    ok = sum(1 for row in rows if row.outcome is ItemOutcome.OK)
    manifest = RunManifest.from_json(
        read_text(tmp_path / "public" / "digest" / "2026" / "08" / "21" / "run.json")
    )

    with health_path.open(encoding="utf-8", newline="") as handle:
        assert tuple(csv.DictReader(handle).fieldnames or ()) == ItemHealthRow.csv_columns()
    assert len(rows) == len(run_plan.items)
    assert ok > 0
    assert failed > 0
    assert rows[0].fetch_ms == 111
    assert rows[0].extract_ms == 22
    assert rows[0].summarize_ms == 333
    assert {row.code for row in rows if row.outcome is ItemOutcome.FAILED} == {
        FailureCode.NOT_ATTEMPTED
    }
    assert day.items_planned == ok + failed == len(run_plan.items)
    assert manifest.runs[-1].items_planned == ok + failed
    assert manifest.runs[-1].items_failed == failed


def health_rows(state_dir: Path, date: str) -> list[ItemHealthRow]:
    """Every item-health row the committed shard holds, in file order."""
    path = ledger.item_health_path(state_dir, date)
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return [ItemHealthRow.from_csv_row(record) for record in csv.DictReader(handle)]


def test_a_run_that_dies_before_assemble_keeps_what_its_workers_measured(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """The Oracle, first half: assemble never runs and the rows are still there.

    Until this stage existed, a shard's verdicts left the runner only inside an
    `items-<shard>` artifact that expires in a day and is skipped entirely when
    the job is cancelled. A run stopped here had measured every item and
    recorded none of it.

    The shard leaves them in its own segment, which it commits. The fold that
    puts them in the head is `assemble`'s, and the next run's `plan` job runs the
    same fold for exactly this case - a run that died before its assemble.
    """
    run_plan = plan()
    settings = config.load(CONFIG_DIR)
    isolate_ledgers(tmp_path, monkeypatch)
    state = tmp_path / "state"

    stage_work(
        run_plan,
        settings=settings,
        scorer=None,
        fetcher=captured_article_fetch,
        model_endpoint=closed_loopback_endpoint(),
    )
    recorded, _ = stage_record(run_plan, settings=settings)

    assert ledger.segment_files(state, ledger.SegmentLedger.ITEM_HEALTH), (
        "the shard committed nothing, so the catch-up fold would have nothing to read"
    )
    stage_compact(state)

    rows = health_rows(state, run_plan.date)
    assert recorded == len(rows) == len(run_plan.items)
    assert {row.run_id for row in rows} == {run_plan.run_id}
    assert [row.item_id for row in rows] == [item.item_id for item in run_plan.items]
    assert ledger.read_header(ledger.item_health_path(state, run_plan.date)) == (
        ItemHealthRow.csv_columns()
    )


def test_the_assemble_that_follows_appends_nothing_the_worker_already_recorded(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """The Oracle, second half: two writers, one row per item per run.

    A repeat is not free. `public_telemetry` copies every row into the file the
    console reads, and `merge=union` keeps the lines from both sides rather than
    collapsing them - so a second copy is one item counted twice on the
    dashboard, forever, in a ledger that cannot correct a row.
    """
    run_plan = plan()
    settings = config.load(CONFIG_DIR)
    isolate_ledgers(tmp_path, monkeypatch)
    state = tmp_path / "state"
    stage_work(
        run_plan,
        settings=settings,
        scorer=None,
        fetcher=captured_article_fetch,
        model_endpoint=closed_loopback_endpoint(),
    )
    stage_record(run_plan, settings=settings)
    stage_compact(state)
    after_the_worker = health_rows(state, run_plan.date)

    stage_assemble(run_plan, settings=settings, commit_sha="a" * 40, runner="fixture")

    rows = health_rows(state, run_plan.date)
    keys = [(row.date, row.run_id, row.item_id) for row in rows]
    assert rows == after_the_worker, "assemble re-wrote rows the worker had already committed"
    assert len(keys) == len(set(keys)) == len(run_plan.items)
    # The dedupe only bites because both writers file under one run id. If the
    # two derivations ever part, every row lands twice.
    assert {row.run_id for row in rows} == {run_plan.run_id}


def test_replaying_a_day_the_worker_already_recorded_appends_no_duplicate(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """A run cancelled after its workers is re-run, and the shard files nothing new.

    Nothing published in between, so `_next_run_n` hands the replay the same run
    id - which is exactly what makes its rows the same rows.
    """
    run_plan = plan()
    settings = config.load(CONFIG_DIR)
    isolate_ledgers(tmp_path, monkeypatch)
    committed = ledger.item_health_path(tmp_path / "state", run_plan.date)
    stage_work(
        run_plan,
        settings=settings,
        scorer=None,
        fetcher=captured_article_fetch,
        model_endpoint=closed_loopback_endpoint(),
    )
    stage_record(run_plan, settings=settings)
    stage_compact(tmp_path / "state")
    after_one_run = committed.read_bytes()

    stage_record(run_plan, settings=settings)
    stage_compact(tmp_path / "state")

    assert committed.read_bytes() == after_one_run


def test_two_runs_that_start_before_either_publishes_cannot_share_a_run_id(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """The defect, and the fix, on the tree that produced it.

    `actions/checkout` pins a job to the commit its run was triggered at, so a
    run that starts while another is still working reads the day exactly as it
    stood before that one published. Counting the runs off it therefore gives
    both of them the same answer - which is what happened on 2026-08-29, when
    runs 33270983446 and 33274853468 both derived `2026-08-29-3` and the ledgers
    keyed on it ended up with six counter rows for four shards.

    Naming the execution is what makes that impossible: GitHub allocates the
    number and nothing a second run can read reproduces it.
    """
    isolate_ledgers(tmp_path, monkeypatch)
    settings = config.load(CONFIG_DIR)
    date = plan().date
    frozen = assemble.day_dir(common.PUBLIC_ROOT, date)
    frozen.mkdir(parents=True, exist_ok=True)
    day = assemble.build_day(
        plan=plan(),
        items=[digest_item()],
        previous=None,
        taxonomy=settings.taxonomy,
        run_n=1,
        generated_at="2026-08-21T07:00:00Z",
        retention_window_months=-1,
    )
    assemble.write_atomic(frozen / "digest.json", day.to_json())
    assemble.write_atomic(
        frozen / "run.json",
        assemble.build_manifest(
            plan=plan(),
            day=day,
            previous=None,
            summaries=[summary()],
            models=[],
            commit_sha="a" * 40,
            runner="local",
            started_at="2026-08-21T06:00:00Z",
            completed_at="2026-08-21T07:00:00Z",
            config_digests=settings.digests,
            site_bytes=1,
            site_files=1,
        ).to_json(),
    )

    def planned(execution: int | None) -> str:
        return stage_plan(
            date,
            settings=settings,
            fetcher=lambda _url: FetchResult(outcome=FetchOutcome.TRANSIENT, detail="offline"),
            now=lambda: "2026-08-21T09:00:00Z",
            execution=execution,
            state_dir=tmp_path / "state",
        ).run_id

    # Neither run has published, so the count is the same answer for both.
    assert _next_run_n(date) == _next_run_n(date) == 2
    assert planned(None) == planned(None), "the count cannot tell two executions apart"

    assert planned(33270983446) == f"{date}-33270983446"
    assert planned(33270983446) != planned(33274853468)


def test_a_shard_records_its_own_items_and_nobody_else_s(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """Eight workers run at once, so a shard that recorded the day would file
    rows for items the other seven are still holding."""
    run_plan = plan()
    settings = config.load(CONFIG_DIR)
    isolate_ledgers(tmp_path, monkeypatch)
    stage_work(
        run_plan,
        settings=settings,
        scorer=None,
        fetcher=captured_article_fetch,
        shard=0,
        shards=2,
        model_endpoint=closed_loopback_endpoint(),
    )

    stage_record(run_plan, settings=settings, shard=0, shards=2)
    stage_compact(tmp_path / "state")

    mine = [item.item_id for item in shard_of(run_plan, shard=0, shards=2)]
    assert [row.item_id for row in health_rows(tmp_path / "state", run_plan.date)] == mine
    assert len(mine) < len(run_plan.items)


def test_an_item_whose_summary_is_not_written_yet_is_not_recorded(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """An interruption is not a failure, and this ledger cannot correct a row.

    The worker writes an article payload for every item it reaches and a summary
    payload for every item that got as far as the model. An accepted article with
    no summary beside it means the shard stopped mid-item.
    """
    run_plan = plan()
    isolate_ledgers(tmp_path, monkeypatch)
    items_dir = tmp_path / "run" / run_plan.date / "items"
    stage_visual_payloads(run_plan, items_dir, text=FULL_TEXT)
    interrupted = run_plan.items[1]
    (items_dir / f"{interrupted.item_id}.summary.json").unlink()

    recorded, _ = stage_record(run_plan, settings=config.load(CONFIG_DIR))
    stage_compact(tmp_path / "state")

    settled = [item.item_id for item in run_plan.items if item.item_id != interrupted.item_id]
    assert recorded == len(settled)
    assert [row.item_id for row in health_rows(tmp_path / "state", run_plan.date)] == settled
    assert telemetry.is_final(article(), None) is False
    assert telemetry.is_final(None, None) is False


def test_the_two_ledgers_agree_about_which_shards_ran(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """The Oracle for the shard column: the per-item file joins the per-job file.

    Read speed varied 1.10x to 4.19x between the shards of one run over the seven
    runs committed on 2026-08-30, so a rate pooled over a run averages away the
    thing an operator needs to see. The join is `(run_id, shard)`, and it only
    works if both files name the same set of workers - two ledgers that disagree
    about how many machines ran cannot be put on one chart.
    """
    run_plan = plan()
    settings = config.load(CONFIG_DIR)
    isolate_ledgers(tmp_path, monkeypatch)
    state = tmp_path / "state"
    capture = FIXTURES_DIR / "runtime" / "2026-08-26-5-shard-3.prom"

    for shard in (0, 1):
        stage_work(
            run_plan,
            settings=settings,
            scorer=None,
            fetcher=captured_article_fetch,
            shard=shard,
            shards=2,
            model_endpoint=closed_loopback_endpoint(),
        )
        stage_record(run_plan, settings=settings, shard=shard, shards=2)
        stage_job_clock(
            run_plan,
            settings=settings,
            state_root=common.STATE_ROOT,
            shard=shard,
            metrics_path=capture,
        )

    stage_compact(state)
    rows = health_rows(state, run_plan.date)
    counted = ledger.load_host_fingerprint_shard(
        ledger.host_fingerprint_path(state, run_plan.date)
    )

    assert {row.shard for row in rows} == {row.shard for row in counted} == {0, 1}
    assert [row.server_prompt_tokens for row in counted] == [23411, 23411], (
        "each shard files what its own server counted"
    )
    assert len(rows) == len(run_plan.items)
    for shard in (0, 1):
        mine = {item.item_id for item in shard_of(run_plan, shard=shard, shards=2)}
        assert {row.item_id for row in rows if row.shard == shard} == mine
        assert mine, "a shard with no items would make the set comparison pass on nothing"


def test_the_census_assemble_adds_names_no_machine(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """One worker of two ran, and the rows for the other half stay unclaimed.

    `shard_of` is deterministic, so assemble could work out which machine each
    missing item was meant for. It must not: the item was not worked, and a
    number there would put items on a machine's bar that the machine never
    touched. Empty is the honest cell, and it is the same cell every row written
    before 2026-08-30 holds.
    """
    run_plan = plan()
    settings = config.load(CONFIG_DIR)
    isolate_ledgers(tmp_path, monkeypatch)
    state = tmp_path / "state"
    stage_work(
        run_plan,
        settings=settings,
        scorer=None,
        fetcher=captured_article_fetch,
        shard=0,
        shards=2,
        model_endpoint=closed_loopback_endpoint(),
    )
    stage_record(run_plan, settings=settings, shard=0, shards=2)

    stage_assemble(run_plan, settings=settings, commit_sha="a" * 40, runner="fixture")

    rows = health_rows(state, run_plan.date)
    worked = {item.item_id for item in shard_of(run_plan, shard=0, shards=2)}
    assert len(rows) == len(run_plan.items)
    assert {row.item_id for row in rows if row.shard == 0} == worked
    assert {row.item_id for row in rows if row.shard is None} == {
        item.item_id for item in run_plan.items
    } - worked
    assert any(row.shard is None for row in rows), "the run left nothing for assemble to census"


def test_a_later_run_appends_and_never_reorders() -> None:
    """Run 2 offers a better story and the one already published, and both rules hold.

    The better story goes under what the day already carried, because a reader
    who read at breakfast must find it where they left it. The one already
    published is dropped whole rather than published a second time.
    """
    settings = config.load(CONFIG_DIR)
    carried = digest_item(run_n=1)
    added = digest_item(run_n=2)
    first = assemble.build_day(
        plan=plan(),
        items=[carried],
        previous=None,
        taxonomy=settings.taxonomy,
        run_n=1,
        generated_at="2026-08-21T07:00:00Z",
        retention_window_months=-1,
    )
    second = assemble.build_day(
        plan=plan(),
        items=[added, carried],
        previous=first,
        taxonomy=settings.taxonomy,
        run_n=2,
        generated_at="2026-08-21T19:00:00Z",
        retention_window_months=-1,
    )
    assert [item.item_id for item in second.items] == [carried.item_id, added.item_id]
    assert [item.introduced_by_run for item in second.items] == [1, 2], (
        "the better story moved under a reader who had already read the day"
    )
    assert second.runs[-1].items_added == 1, "an item already published is not published twice"


def test_a_desk_publishes_why_it_ran_what_it_ran() -> None:
    """The plan counted what the feeds offered and the day used to throw it away.

    Without it a desk that published three stories and a desk whose feeds broke
    look identical on the page, and the reader has no way to tell them apart.
    """
    settings = config.load(CONFIG_DIR)
    day = assemble.build_day(
        plan=plan(),
        items=[digest_item(run_n=1)],
        previous=None,
        taxonomy=settings.taxonomy,
        run_n=1,
        generated_at="2026-08-21T07:00:00Z",
        retention_window_months=-1,
    )

    desk = next(ref for ref in day.verticals if ref.id == "ai")
    assert desk.considered == 5, "the day dropped what the plan already counted"
    assert desk.too_old == 0
    assert desk.below_feed_floor is False


def test_a_desk_no_run_ever_planned_invents_no_shortfall() -> None:
    """Absent reads as unknown, never as zero.

    A zero would say the feeds offered this desk nothing, which on a desk that
    published a story is a claim the payload itself contradicts.
    """
    settings = config.load(CONFIG_DIR)
    day = assemble.build_day(
        plan=plan().model_copy(update={"verticals": []}),
        items=[digest_item(run_n=1)],
        previous=None,
        taxonomy=settings.taxonomy,
        run_n=1,
        generated_at="2026-08-21T07:00:00Z",
        retention_window_months=-1,
    )

    desk = next(ref for ref in day.verticals if ref.id == "ai")
    assert desk.considered is None
    assert desk.too_old is None
    assert desk.below_feed_floor is None


def test_a_desk_keeps_the_strongest_shortfall_any_run_recorded() -> None:
    """The strongest and not the sum, and this is the case that says why.

    Run 2 drops what run 1 published before it counts anything, so it sees a
    smaller pool of the same back-catalogue stories. Summing the runs would
    print a number the feeds never offered.
    """
    settings = config.load(CONFIG_DIR)
    base = plan()
    wide = base.model_copy(
        update={
            "verticals": [
                VerticalPlan(id="ai", considered=40, planned=5, eligible_feeds=3, too_old=28)
            ]
        }
    )
    narrow = base.model_copy(
        update={
            "verticals": [
                VerticalPlan(id="ai", considered=35, planned=0, eligible_feeds=3, too_old=31)
            ]
        }
    )

    first = assemble.build_day(
        plan=wide,
        items=[digest_item(run_n=1)],
        previous=None,
        taxonomy=settings.taxonomy,
        run_n=1,
        generated_at="2026-08-21T07:00:00Z",
        retention_window_months=-1,
    )
    second = assemble.build_day(
        plan=narrow,
        items=[digest_item(run_n=2)],
        previous=first,
        taxonomy=settings.taxonomy,
        run_n=2,
        generated_at="2026-08-21T19:00:00Z",
        retention_window_months=-1,
    )

    desk = next(ref for ref in second.verticals if ref.id == "ai")
    assert desk.considered == 40, "the second run's smaller pool overwrote the first"
    assert desk.too_old == 31, "a run that found more of the day stale must raise the count"
    assert desk.too_old <= desk.considered, "the sentence would name more dropped than offered"


def test_a_second_runs_better_story_is_published_below_what_the_day_already_had() -> None:
    """The crash of 2026-09-13, held at the stage that caused it.

    The fresh story outscores the published one, which is the ordinary case: a
    run publishes what the earlier run could not see yet. `DigestDay` refuses a
    day whose `introduced_by_run` decreases, so an order taken over the whole
    day fails here exactly as it failed in production - `ValidationError`, not a
    wrong assertion.

    Every field this needs comes off `digest_item`, which is the whole of the
    control: the case is the fixture's default, so a test written next year
    without a thought for ordering still meets it.
    """
    settings = config.load(CONFIG_DIR)
    published = digest_item(run_n=1)
    fresh = digest_item(run_n=2)
    assert fresh.rank_score is not None and published.rank_score is not None
    assert fresh.rank_score > published.rank_score, "the fixture stopped being the hard case"

    morning = assemble.build_day(
        plan=plan(),
        items=[published],
        previous=None,
        taxonomy=settings.taxonomy,
        run_n=1,
        generated_at="2026-08-21T07:00:00Z",
        retention_window_months=-1,
    )
    evening = assemble.build_day(
        plan=plan(),
        items=[fresh],
        previous=morning,
        taxonomy=settings.taxonomy,
        run_n=2,
        generated_at="2026-08-21T19:00:00Z",
        retention_window_months=-1,
    )

    introduced = [item.introduced_by_run for item in evening.items]
    assert introduced == [1, 2], "a story a reader read at breakfast moved under them"
    assert [item.item_id for item in evening.items] == [published.item_id, fresh.item_id]


def test_a_desk_retired_mid_day_keeps_the_explanation_it_already_had() -> None:
    """A desk with items and no entry in today's plan is not a desk with no answer.

    It happens when `config/taxonomy.json` retires a vertical between runs. The
    stories stay on the day, so the sentence under them has to stay true.
    """
    settings = config.load(CONFIG_DIR)
    base = plan()
    first = assemble.build_day(
        plan=base,
        items=[digest_item(run_n=1)],
        previous=None,
        taxonomy=settings.taxonomy,
        run_n=1,
        generated_at="2026-08-21T07:00:00Z",
        retention_window_months=-1,
    )
    second = assemble.build_day(
        plan=base.model_copy(update={"verticals": []}),
        items=[digest_item(run_n=2)],
        previous=first,
        taxonomy=settings.taxonomy,
        run_n=2,
        generated_at="2026-08-21T19:00:00Z",
        retention_window_months=-1,
    )

    desk = next(ref for ref in second.verticals if ref.id == "ai")
    assert desk.considered == 5
    assert desk.below_feed_floor is False


def test_a_run_that_comes_back_as_itself_still_produces_a_day() -> None:
    """`stage_assemble` writes the day, then builds the manifest, then writes it.

    A run that dies in that gap leaves a day carrying its items and a manifest
    that never heard of it, so the next run reads the same number off the
    manifest and appends to a day that already holds work under that number.
    The run reference has to count every item the number introduced, because
    that is what `DigestDay` validates it against.
    """
    settings = config.load(CONFIG_DIR)
    base = plan()
    crashed = assemble.build_day(
        plan=base,
        items=[digest_item(run_n=1).model_copy(update={"item_id": base.items[0].item_id})],
        previous=None,
        taxonomy=settings.taxonomy,
        run_n=1,
        generated_at="2026-08-21T07:00:00Z",
        retention_window_months=-1,
    )
    replayed = assemble.build_day(
        plan=base,
        items=[digest_item(run_n=1).model_copy(update={"item_id": base.items[1].item_id})],
        previous=crashed,
        taxonomy=settings.taxonomy,
        run_n=1,
        generated_at="2026-08-21T13:00:00Z",
        retention_window_months=-1,
    )

    assert len(replayed.items) == 2, "the replay keeps what its own first attempt published"
    assert [run.n for run in replayed.runs] == [1], "one attempt and its replay are one run"
    assert replayed.runs[0].items_added == 2, (
        "the reference counts what run 1 introduced, not what this attempt added"
    )


def test_a_carried_item_is_not_recorded_as_published_twice() -> None:
    """The join in `_published_rows` is the only thing keeping `published.csv` clean.

    `ledger._append` writes every row it is handed, so a second row for one
    address would stay in the file forever. A day carries yesterday's items
    forward, and the plan a later run built has already dropped their addresses,
    so they fall out of the join instead of being recorded again.
    """
    settings = config.load(CONFIG_DIR)
    base = plan()
    first, second = base.items[0], base.items[1]
    first_plan = base.model_copy(update={"items": [first]})
    later_plan = base.model_copy(update={"items": [second], "run_id": f"{base.date}-2"})

    day_one = assemble.build_day(
        plan=first_plan,
        items=[digest_item(run_n=1).model_copy(update={"item_id": first.item_id})],
        previous=None,
        taxonomy=settings.taxonomy,
        run_n=1,
        generated_at="2026-08-21T07:00:00Z",
        retention_window_months=-1,
    )
    day_two = assemble.build_day(
        plan=later_plan,
        items=[digest_item(run_n=2).model_copy(update={"item_id": second.item_id})],
        previous=day_one,
        taxonomy=settings.taxonomy,
        run_n=2,
        generated_at="2026-08-21T13:00:00Z",
        retention_window_months=-1,
    )

    assert [item.item_id for item in day_two.items] == [first.item_id, second.item_id]
    assert [row.url_key for row in _published_rows(day_one, first_plan)] == [first.url_key]
    assert [row.url_key for row in _published_rows(day_two, later_plan)] == [second.url_key]


def test_a_later_run_cannot_rewrite_the_words_a_reader_already_read() -> None:
    """The gate that makes `updated_at` and `updated_by_run` reserved rather than live.

    An item the day already holds is dropped whole, so a second run carrying
    different words for the same address changes nothing a reader can see. If
    this ever stops holding, docs/architecture/publishing/layout.md is wrong and
    has to be corrected in the same commit.
    """
    settings = config.load(CONFIG_DIR)
    original = digest_item(run_n=1)
    first = assemble.build_day(
        plan=plan(),
        items=[original],
        previous=None,
        taxonomy=settings.taxonomy,
        run_n=1,
        generated_at="2026-08-21T07:00:00Z",
        retention_window_months=-1,
    )
    rewritten = original.model_copy(
        update={"summary": "Different words for the same address.", "key_points": ["Rewritten."]}
    )
    second = assemble.build_day(
        plan=plan(),
        items=[rewritten],
        previous=first,
        taxonomy=settings.taxonomy,
        run_n=2,
        generated_at="2026-08-21T19:00:00Z",
        retention_window_months=-1,
    )

    kept = second.items[0]
    assert kept.summary == original.summary
    assert kept.key_points == original.key_points
    assert kept.introduced_by_run == 1
    assert kept.updated_at is None
    assert kept.updated_by_run is None


def test_the_run_that_wrote_an_item_resolves_to_a_recorded_run() -> None:
    """The join to the manifest that names the model lands on a run the day recorded."""
    day = DigestDay.from_json(read_text(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json"))
    recorded = {run.n for run in day.runs}

    assert day.items
    for item in day.items:
        assert assemble.run_that_wrote(item) in recorded
        assert assemble.run_that_wrote(item) == item.introduced_by_run

    revised = day.items[0].model_copy(
        update={"updated_at": "2026-08-21T18:00:00Z", "updated_by_run": 2}
    )

    assert assemble.run_that_wrote(revised) == 2, "a revision is joined to the run that revised it"


def test_the_published_path_carries_no_digest() -> None:
    target = assemble.day_dir(Path("frontend/public/digest"), "2026-08-21")
    assert target.as_posix().endswith("digest/2026/08/21")


def test_a_write_is_atomic(tmp_path: Path) -> None:
    """A file either exists complete or does not exist. There is no half-written item."""
    target = tmp_path / "deep" / "digest.json"
    assemble.write_atomic(target, '{"a": 1}\n')
    assert target.read_bytes() == b'{"a": 1}\n'


def test_the_manifest_records_what_ran_against_what() -> None:
    settings = config.load(CONFIG_DIR)
    day = assemble.build_day(
        plan=plan(),
        items=[digest_item()],
        previous=None,
        taxonomy=settings.taxonomy,
        run_n=1,
        generated_at="2026-08-21T07:00:00Z",
        retention_window_months=-1,
    )
    manifest = assemble.build_manifest(
        plan=plan(),
        day=day,
        previous=None,
        summaries=[summary()],
        models=[],
        commit_sha="a" * 40,
        runner="local",
        started_at="2026-08-21T06:00:00Z",
        completed_at="2026-08-21T07:00:00Z",
        config_digests=settings.digests,
        site_bytes=1024,
        site_files=2,
    )
    assert isinstance(manifest, RunManifest)
    assert manifest.runs[-1].run_id == "2026-08-21-1"
    assert manifest.runs[-1].config_digests
    assert manifest.runs[-1].inputs is None, "no work shard recorded any, so none is recorded"


def test_the_run_records_the_scoring_shape_that_decided_its_order() -> None:
    """`RANK_VERSION` was read by nothing, so no run had ever recorded it.

    The stage that publishes the order is the stage that names the shape it was
    published under, and it names the constant rather than a string of its own -
    two spellings of one version is the failure this field exists to close.
    """
    settings = config.load(CONFIG_DIR)
    source = read_text(REPO_ROOT / "backend" / "idhazh" / "stages" / "assemble.py")
    assert "rank_version=rank.RANK_VERSION" in source, (
        "the assemble stage stopped recording the scoring shape"
    )

    manifest = assemble.build_manifest(
        plan=plan(),
        day=assemble.build_day(
            plan=plan(),
            items=[digest_item()],
            previous=None,
            taxonomy=settings.taxonomy,
            run_n=1,
            generated_at="2026-08-21T07:00:00Z",
            retention_window_months=-1,
        ),
        previous=None,
        summaries=[summary()],
        models=[],
        commit_sha="a" * 40,
        runner="local",
        started_at="2026-08-21T06:00:00Z",
        completed_at="2026-08-21T07:00:00Z",
        config_digests=settings.digests,
        site_bytes=1024,
        site_files=2,
        rank_version=rank.RANK_VERSION,
    )
    assert manifest.runs[-1].rank_version == rank.RANK_VERSION

    # A caller that records nothing writes null, which reads as unknown. It must
    # never read as "the shape this build happens to carry".
    silent = assemble.build_manifest(
        plan=plan(),
        day=manifest_day(settings),
        previous=None,
        summaries=[summary()],
        models=[],
        commit_sha="a" * 40,
        runner="local",
        started_at="2026-08-21T06:00:00Z",
        completed_at="2026-08-21T07:00:00Z",
        config_digests=settings.digests,
        site_bytes=1024,
        site_files=2,
    )
    assert silent.runs[-1].rank_version is None


def test_a_run_records_how_many_feeds_a_desk_could_ask_and_against_what_floor() -> None:
    """`below_feed_floor` alone says a desk went dark and neither number that decided it.

    The manifest is the only committed record of a plan - `plan.json` is a
    one-day artifact - so a reader looking at why a desk was absent has nothing
    else to read. Both numbers are carried straight from the plan and computed
    nowhere else, so the run that published cannot disagree with the run that
    decided. A desk whose plan carried no floor writes null, which is unknown
    rather than a floor of zero.
    """
    settings = config.load(CONFIG_DIR)
    base = plan()
    floored = base.model_copy(
        update={
            "verticals": [
                vertical.model_copy(update={"feed_floor": 35})
                if vertical.id == "ai"
                else vertical
                for vertical in base.verticals
            ]
        }
    )
    manifest = assemble.build_manifest(
        plan=floored,
        day=manifest_day(settings),
        previous=None,
        summaries=[summary()],
        models=[],
        commit_sha="a" * 40,
        runner="local",
        started_at="2026-08-21T06:00:00Z",
        completed_at="2026-08-21T07:00:00Z",
        config_digests=settings.digests,
        site_bytes=1024,
        site_files=2,
    )

    counts = {count.id: count for count in manifest.runs[-1].verticals}
    planned = {vertical.id: vertical for vertical in floored.verticals}
    assert counts["ai"].eligible_feeds == planned["ai"].eligible_feeds
    assert counts["ai"].feed_floor == 35
    assert counts["energy"].feed_floor is None


def manifest_day(settings: config.Settings) -> DigestDay:
    return assemble.build_day(
        plan=plan(),
        items=[digest_item()],
        previous=None,
        taxonomy=settings.taxonomy,
        run_n=1,
        generated_at="2026-08-21T07:00:00Z",
        retention_window_months=-1,
    )


def test_the_manifest_cannot_record_one_run_twice() -> None:
    """One execution is one record, however many times it reaches this stage.

    `run_id` is the identity of the execution rather than a count of what is
    committed, so an assemble job that runs again reads the same plan and
    computes the same id. It replaces its own record instead of appending a
    second one that planned nothing - the rule `build_day` already applies to
    the day's own run list. The contract refuses the shape either way.
    """
    settings = config.load(CONFIG_DIR)
    day = assemble.build_day(
        plan=plan(),
        items=[digest_item()],
        previous=None,
        taxonomy=settings.taxonomy,
        run_n=1,
        generated_at="2026-08-21T07:00:00Z",
        retention_window_months=-1,
    )

    def manifest_after(previous: RunManifest | None, run_id: str) -> RunManifest:
        return assemble.build_manifest(
            plan=plan().model_copy(update={"run_id": run_id}),
            day=day,
            previous=previous,
            summaries=[summary()],
            models=[],
            commit_sha="a" * 40,
            runner="local",
            started_at="2026-08-21T06:00:00Z",
            completed_at="2026-08-21T07:00:00Z",
            config_digests=settings.digests,
            site_bytes=1024,
            site_files=2,
        )

    first = manifest_after(None, "2026-08-21-33270983446")
    replayed = manifest_after(first, "2026-08-21-33270983446")
    assert [run.n for run in replayed.runs] == [1], "one execution and its replay are one run"
    assert [run.run_id for run in replayed.runs] == ["2026-08-21-33270983446"]

    # A different execution is a different run, and takes the next number.
    second = manifest_after(first, "2026-08-21-33274853468")
    assert [run.n for run in second.runs] == [1, 2]

    with pytest.raises(ValidationError, match="numbered from 1 without gaps"):
        RunManifest(
            version=RunManifest.schema_version(),
            date=first.date,
            runs=[first.runs[0], first.runs[0]],
        )
    with pytest.raises(ValidationError, match="numbered from 1 without gaps"):
        RunManifest(
            version=RunManifest.schema_version(),
            date=second.date,
            runs=[second.runs[1], second.runs[0]],
        )
    # And the shape the collision made: two records, correctly numbered, that
    # name one execution between them.
    with pytest.raises(ValidationError, match="cannot share a run_id"):
        RunManifest(
            version=RunManifest.schema_version(),
            date=second.date,
            runs=[
                second.runs[0],
                second.runs[1].model_copy(update={"run_id": second.runs[0].run_id}),
            ],
        )


def test_the_manifest_records_what_the_planner_cost() -> None:
    """The visuals job runs against a 60-minute bound and nothing recorded its cost.

    The stage total and the item count are committed together, because either
    one alone answers no question about the budget (Guardrail #10).
    """
    settings = config.load(CONFIG_DIR)
    decided = VisualDecision.from_json(read_text(CONTRACT_FIXTURES_DIR / "visual-decision" / "chart-rendered.json"))
    day = assemble.build_day(
        plan=plan(),
        items=[digest_item()],
        previous=None,
        taxonomy=settings.taxonomy,
        run_n=1,
        generated_at="2026-08-21T07:00:00Z",
        retention_window_months=-1,
    )

    def manifest_for(decisions: list[VisualDecision]) -> RunManifest:
        return assemble.build_manifest(
            plan=plan(),
            day=day,
            previous=None,
            summaries=[summary()],
            models=[],
            commit_sha="a" * 40,
            runner="local",
            started_at="2026-08-21T06:00:00Z",
            completed_at="2026-08-21T07:00:00Z",
            config_digests=settings.digests,
            site_bytes=1024,
            site_files=2,
            decisions=decisions,
        )

    timed = manifest_for(
        [
            decided.model_copy(update={"decision_ms": 4000}),
            decided.model_copy(update={"decision_ms": 11000}),
        ]
    )
    assert timed.runs[-1].items_decided == 2
    assert timed.runs[-1].decision_ms == 15000

    # The Python names moved on 2026-09-05 and the published keys did not, so the
    # serialised record is checked here rather than only the attributes above.
    written = json.loads(timed.to_json())["runs"][-1]
    assert written["items_routed"] == 2
    assert written["route_ms"] == 15000
    assert "items_decided" not in written and "decision_ms" not in written

    # A planner that never started is not a planner that took no time.
    absent = manifest_for([])
    assert absent.runs[-1].items_decided == 0
    assert absent.runs[-1].decision_ms is None

    # Neither is a payload written before the clock existed.
    unclocked = manifest_for([decided.model_copy(update={"decision_ms": None})])
    assert unclocked.runs[-1].items_decided == 1
    assert unclocked.runs[-1].decision_ms is None

    # The gate changes every denominator: the same charts sit over a smaller
    # decided set. Counting the skips keeps a chart rate from climbing on its own.
    gated = manifest_for(
        [
            decided.model_copy(update={"decision_ms": 4000}),
            decided.model_copy(update={"decision_ms": 1, "asked_the_model": False}),
            decided.model_copy(update={"decision_ms": 1, "asked_the_model": False}),
        ]
    )
    assert gated.runs[-1].items_decided == 3
    assert gated.runs[-1].items_prefiltered == 2

    # A payload written before the gate existed was always asked.
    assert timed.runs[-1].items_prefiltered == 0


def test_a_later_manifest_counts_verticals_for_its_own_run(tmp_path: Path) -> None:
    settings = config.load(CONFIG_DIR)
    base_plan = plan()
    first_item = base_plan.items[0]
    second_item = base_plan.items[1]
    first_plan = base_plan.model_copy(
        update={
            "items": [first_item],
            "verticals": [base_plan.verticals[0].model_copy(update={"planned": 1})],
        }
    )
    second_plan = base_plan.model_copy(
        update={
            "items": [second_item],
            "run_id": f"{base_plan.date}-2",
            "verticals": [base_plan.verticals[0].model_copy(update={"planned": 1})],
        }
    )
    first_summary = summary().model_copy(
        update={"item_id": first_item.item_id, "url_key": first_item.url_key}
    )
    second_summary = summary().model_copy(
        update={"item_id": second_item.item_id, "url_key": second_item.url_key}
    )
    first_day = assemble.build_day(
        plan=first_plan,
        items=[digest_item(run_n=1).model_copy(update={"item_id": first_item.item_id})],
        previous=None,
        taxonomy=settings.taxonomy,
        run_n=1,
        generated_at="2026-08-21T07:00:00Z",
        retention_window_months=-1,
    )
    first_manifest = assemble.build_manifest(
        plan=first_plan,
        day=first_day,
        previous=None,
        summaries=[first_summary],
        models=[],
        commit_sha="a" * 40,
        runner="local",
        started_at="2026-08-21T06:00:00Z",
        completed_at="2026-08-21T07:00:00Z",
        config_digests=settings.digests,
        site_bytes=1024,
        site_files=2,
    )
    second_day = assemble.build_day(
        plan=second_plan,
        items=[digest_item(run_n=2).model_copy(update={"item_id": second_item.item_id})],
        previous=first_day,
        taxonomy=settings.taxonomy,
        run_n=2,
        generated_at="2026-08-21T13:00:00Z",
        retention_window_months=-1,
    )
    second_manifest = assemble.build_manifest(
        plan=second_plan,
        day=second_day,
        previous=first_manifest,
        summaries=[second_summary],
        models=[],
        commit_sha="b" * 40,
        runner="local",
        started_at="2026-08-21T12:00:00Z",
        completed_at="2026-08-21T13:00:00Z",
        config_digests=settings.digests,
        site_bytes=2048,
        site_files=3,
    )

    assert len(second_day.items) == 2
    assert second_manifest.runs[-1].verticals[0].planned == 1
    assert second_manifest.runs[-1].verticals[0].published == 1

    old_payload = second_manifest.model_dump(mode="json")
    old_payload["version"] = "2026-08-21T02:00"
    old_payload["runs"][1]["verticals"][0]["published"] = 2
    old_path = tmp_path / "run.json"
    old_path.write_text(json.dumps(old_payload), encoding="utf-8")

    migrated = _load_manifest(old_path, day=second_day)

    assert migrated is not None
    assert migrated.version == RunManifest.schema_version()
    assert migrated.runs[-1].verticals[0].published == 1


def test_the_committed_day_fixture_still_loads() -> None:
    day = DigestDay.from_json(read_text(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json"))
    assert day.items
