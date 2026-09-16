"""Collect whatever finished, publish it, and append the ledger.

One stage, one module. `idhazh.cli` chooses which stage runs and holds no stage
body of its own (CLAUDE.md section 1a, "A router is the sharpest case").
"""

from __future__ import annotations

from datetime import date as date_type
from pathlib import Path

from idhazh import assemble, config, ledger, rank, telemetry
from idhazh.contracts.digest_day import DigestDay
from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.fingerprint import PipelineInputs
from idhazh.contracts.run_manifest import ModelRole, ModelUse, RunManifest
from idhazh.contracts.run_plan import RunPlan
from idhazh.contracts.seen import PublishedRow
from idhazh.contracts.summary import Summary, SummaryStatus
from idhazh.contracts.taxonomy import SourceKind
from idhazh.contracts.visual_decision import VisualDecision
from idhazh.embed import Embedder
from idhazh.evals import metrics, sampling, score, writer
from idhazh.fingerprint import (
    prose_changed_alone,
)
from idhazh.stages import common
from idhazh.stages.common import (
    INPUTS_PAYLOAD,
    LOG,
    _extraction_health,
    _item_payloads,
    _load_day,
    _load_manifest,
    _run_dir,
)
from idhazh.telemetry.publish import day_metrics, dispatch, source_health


def _index_root() -> Path:
    """Where a month's search index goes, derived from the digest root it projects.

    Derived rather than a constant of its own, because a constant does not move
    when a caller moves the days. A test that redirects `PUBLIC_ROOT` at a
    temporary tree used to leave this pointing at the repository, so the suite
    rebuilt the committed shard out of fixture days - which is how the shard on
    `main` came to name one item no published day holds. `public_telemetry` is
    passed its root the same way and for the same reason.
    """
    return common.PUBLIC_ROOT.parent / "assist" / "index"


def _recorded_inputs(items_dir: Path) -> PipelineInputs | None:
    """What the shards recorded, or nothing when no shard summarized anything."""
    path = items_dir / INPUTS_PAYLOAD
    if not path.is_file():
        return None
    return PipelineInputs.model_validate_json(path.read_text(encoding="utf-8"))


def _report_prose_change(
    inputs: PipelineInputs | None, previous: RunManifest | None
) -> None:
    """Say when the words we asked for moved and the machine reading them did not.

    The one alarm that survives the retired stamp (owner decision, 2026-09-10).
    It reports and never blocks: the run publishes, every number is read, and
    the operator is told which input moved.

    The comparison is against the newest earlier run on the same manifest, which
    the caller already holds in memory - one payload, whatever the archive has
    grown to (Guardrail #12).
    """
    if inputs is None or previous is None:
        return
    earlier = next(
        (run.inputs for run in reversed(previous.runs) if run.inputs is not None), None
    )
    moved = prose_changed_alone(earlier, inputs)
    if not moved:
        return
    message = (
        f"the words we ask for moved and the model and the binary did not: "
        f"{', '.join(moved)}. Summaries written before and after this run answer "
        f"a different ask."
    )
    print(f"::warning title=Prose changed, model did not::{message}")
    LOG.warning("%s", message)


def _report_nothing_published(day: DigestDay, plan: RunPlan) -> None:
    """A run that had stories to write and wrote none says so on the summary.

    This stage runs on a bad day on purpose - `digest.yml` gives it
    `if: always()`, because a run that publishes nothing on a bad day is a run
    whose bad days are invisible. The cost of that is a stage that can decide
    nothing and still exit 0, and on 2026-09-14 it did: 80 stories planned, 80
    recorded `not_attempted`, an empty day committed, exit 0, and the only
    sentence naming the cause was in a work-job log that expires. The published
    record keeps the symptom for ever and kept the cause for ninety days.

    So it speaks, and it does not exit non-zero. Failing here would skip the
    steps that commit the day, which is the invisibility the `if: always()` was
    put there to prevent - the day has to land AND the run summary has to carry
    a red line saying the day is empty and where the reason is. Raising instead
    would trade one silence for another.

    A day that planned nothing is not this: the pipeline found no new article,
    which is a quiet day and not a fault.
    """
    if day.items or not day.items_planned:
        return
    message = (
        f"{plan.date} planned {day.items_planned} stories and published none of them "
        f"({day.items_failed} recorded as failed). The day is still committed, so the "
        f"reader sees an empty day and the console sees the counts. The reason is in "
        f"the work jobs of this run, not in anything this run published"
    )
    print(f"::error title=The run published nothing::{message}")
    LOG.error("%s", message)


def stage_assemble(
    plan: RunPlan, *, settings: config.Settings, commit_sha: str, runner: str = "local"
) -> DigestDay:
    """Collect whatever finished, publish it, and append the ledger."""
    items_dir = _run_dir(plan.date) / "items"
    names = assemble.source_names(settings.sources)
    kinds = assemble.source_kinds(settings.sources)
    target = assemble.day_dir(common.PUBLIC_ROOT, plan.date)
    previous_day = _load_day(target / "digest.json")
    previous_manifest = _load_manifest(target / "run.json", day=previous_day)
    # The plan's own id, because the work shards filed their ledger rows under it
    # and this stage writes the day's census into the same files. Deriving a
    # second one here would key assemble's rows differently from the shards' and
    # land every item twice.
    run_id = plan.run_id
    run_n = assemble.run_n_for(previous_manifest, run_id)
    # The names this run collected but will not render. A story relabelled onto
    # one of them publishes under its feed's vertical instead, so the page and
    # the operator surface cannot say opposite things about the same name.
    below_floor_desks = rank.desks_below_floor(plan.verticals)
    digest_items = []
    summaries: list[Summary] = []
    rows = []
    decisions: list[VisualDecision] = []
    # Every planned item's census row. A shard that reached the item sealed the
    # row itself and left it beside the payloads, so this prefers that row: it
    # carries 113 cells where the article and the summary between them carry 40,
    # and it names the worker that ran the item. The rebuild is what an item no
    # shard reached gets, which is what keeps the denominator in this file.
    item_health_rows = [
        telemetry.census_row(
            recorded=payload.recorded,
            planned=payload.planned,
            article=payload.article,
            summary=payload.summary,
            date=plan.date,
            run_id=run_id,
            extraction=_extraction_health(payload.article, settings),
        )
        for payload in _item_payloads(plan, items_dir)
    ]

    for payload in _item_payloads(plan, items_dir, require_summary=True):
        article = payload.article
        summary = payload.summary
        if article is None or summary is None:
            continue
        summaries.append(summary)
        if summary.status is not SummaryStatus.OK:
            continue

        # An item publishes with a band whether or not the faithfulness scorer
        # ran. The counterweights are free and always available, and they never
        # claim the top band on their own.
        if payload.eval_path.exists():
            row = EvalRow.read(payload.eval_path)
            rows.append(row)
            decided = score.verdict(
                row.hhem,
                unsupported_numbers=row.unsupported_numbers,
                lead_coverage=row.coverage,
                hedge_dropped=row.hedge_dropped,
                config=settings.app.evaluation,
            )
        else:
            text = summary.summary or ""
            full_text = article.text or ""
            decided = score.verdict(
                None,
                unsupported_numbers=metrics.unsupported_numbers(text, full_text),
                lead_coverage=metrics.lead_coverage(text, full_text),
                hedge_dropped=metrics.hedge_dropped(text, full_text),
                config=settings.app.evaluation,
            )
        decision = (
            VisualDecision.read(payload.decision_path)
            if payload.decision_path.exists()
            else None
        )
        if decision is not None:
            decisions.append(decision)
        digest_items.append(
            assemble.to_digest_item(
                article=article,
                summary=summary,
                band=decided.band,
                band_reason=decided.reason,
                source_name=names.get(article.source_id, article.source_id),
                source_kind=kinds.get(article.source_id, SourceKind.REPORTING),
                run_n=1,
                decision=decision,
                planned=payload.planned,
                below_floor_desks=below_floor_desks,
            )
        )

    digest_items = [item.model_copy(update={"introduced_by_run": run_n}) for item in digest_items]

    generated_at = assemble.utc_now()
    day = assemble.build_day(
        plan=plan,
        items=digest_items,
        previous=previous_day,
        taxonomy=settings.taxonomy,
        run_n=run_n,
        generated_at=generated_at,
        retention_window_months=settings.app.retention.image_months,
        embeddings=assemble.build_embeddings(
            digest_items, Embedder(config.REPO_ROOT, settings.app.assist)
        ),
        item_health_rows=item_health_rows,
        watchlist=settings.watchlist,
        ui=settings.app.ui,
        placement=settings.app.placement,
        same_story=settings.app.assemble.same_story,
        group_identical_titles=settings.app.assemble.group_identical_titles,
    )
    assemble.write_atomic(target / "digest.json", day.to_json())

    # The month shard is a projection of the days on disk, so it is rebuilt after
    # the day is written and never patched in place.
    index = assemble.rebuild_search_index(
        digest_root=common.PUBLIC_ROOT, index_root=_index_root(), month=assemble.month_of(plan.date)
    )

    # The committed payload tree, which is what this stage can see. It is not the
    # published site and the Pages cap is not measured here - the site is built
    # by a later step in this same job, and `idhazh site-weight` measures it
    # there. See docs/architecture/publishing/layout.md.
    site_bytes, site_files = assemble.site_size(common.PUBLIC_ROOT)
    observability = settings.app.observability
    # The instrument that actually wrote this run's rows. No rows means no
    # instrument, which is what tells a run that was switched off or not drawn
    # apart from one whose weights would not load.
    instruments = sorted({row.scorer_version for row in rows})
    recorded_inputs = _recorded_inputs(items_dir)
    manifest = assemble.build_manifest(
        plan=plan,
        day=day,
        previous=previous_manifest,
        summaries=summaries,
        models=[
            ModelUse(role=ModelRole.SUMMARIZE, model_ref=settings.models.summarize),
        ],
        commit_sha=commit_sha,
        runner=runner,
        started_at=plan.generated_at,
        completed_at=generated_at,
        config_digests=settings.digests,
        site_bytes=site_bytes,
        site_files=site_files,
        inputs=recorded_inputs,
        item_health_rows=item_health_rows,
        decisions=decisions,
        evaluation_enabled=observability.evaluation_enabled,
        evaluation_sample_rate=observability.sample_rate,
        evaluation_sampled=sampling.run_is_sampled(run_id, observability.sample_rate),
        scorer_version=instruments[0] if len(instruments) == 1 else None,
        rank_version=rank.RANK_VERSION,
    )
    _report_prose_change(recorded_inputs, previous_manifest)
    assemble.write_atomic(target / "run.json", manifest.to_json())
    landed = writer.append(common.STATE_ROOT, rows)
    published = ledger.append_published(common.STATE_ROOT, day.date, _published_rows(day, plan))
    item_health = ledger.append_item_health(common.STATE_ROOT, plan.date, item_health_rows)
    # Every projection of the instrument, in the one order `dispatch` names. It
    # runs after the ledgers this stage appended and reads those files rather
    # than anything in memory here, so a run that failed to append publishes the
    # record as it stands rather than as it hoped.
    #
    # The label vectors are read here rather than inside a producer, so a stale
    # file fails the run at the place the config is read and never half way
    # through a record. Absent is not stale: a checkout without the file records
    # no label similarity and publishes exactly as before.
    instrument = dispatch.publish_all(
        state_root=common.STATE_ROOT,
        digest_root=common.PUBLIC_ROOT,
        date=plan.date,
        # The run appended to one month, so that is the only one that can have
        # changed. Every other shard is rebuilt only if it is missing.
        month=assemble.month_of(plan.date),
        # The day this run publishes, not the wall clock. A run that crosses
        # midnight UTC would otherwise prune against one month and write into
        # another.
        today=date_type.fromisoformat(plan.date),
        run_id=run_id,
        generated_at=generated_at,
        day=day,
        manifest=manifest,
        settings=settings,
        taxonomy_vectors=assemble.read_taxonomy_vectors(config.REPO_ROOT, settings.taxonomy),
    )
    yield_alarm = source_health.yield_alarm(
        instrument.sources,
        alarm_point=settings.app.collect.source_yield_alarm_point,
        min_decisions=settings.app.collect.source_yield_alarm_min_decisions,
    )
    if yield_alarm is not None:
        # Same shape as the site-budget alarm below: an Actions workflow command,
        # so a person sees it on the run summary. The console has carried these
        # counts all along and nobody read them, which is why this speaks.
        print(f"::warning title=Sources answering but not reading::{yield_alarm}")
        LOG.warning("%s", yield_alarm)
    _report_nothing_published(day, plan)
    LOG.info(
        "published date=%s items=%s partial=%s eval_rows=%s addresses=%s item_health_rows=%s "
        "search_index=%s/%s day_metrics=%s projections=%s",
        plan.date,
        len(day.items),
        day.partial,
        landed,
        published,
        item_health,
        len(index.entries),
        index.vector_bytes // index.dimensions,
        day_metrics.day_metrics_relpath(plan.date),
        ",".join(instrument.dispatched),
    )
    return day


def _published_rows(day: DigestDay, plan: RunPlan) -> list[PublishedRow]:
    """What this digest actually carried, as addresses a later run can skip.

    The digest item knows the item id and the plan knows the key, so the two are
    joined here rather than widening the published payload with anything the
    skip read does not open.

    That join is also the filter, and it is load-bearing: `ledger._append`
    writes every row it is handed, so nothing downstream would collapse a
    repeat. A day carries yesterday's items forward, and re-recording them would
    move their published date every morning. They do not survive the join
    because `rank.plan_vertical` has already dropped every address
    `load_published` returned, and an item id comes from its address - so a
    carried item's id is absent from this run's plan and it is skipped. The
    filter reads as "everything the day holds" and behaves as "what this run
    added", and the two only agree while those upstream facts hold.
    """
    addresses = {item.item_id: item for item in plan.items}
    rows: list[PublishedRow] = []
    for item in day.items:
        planned = addresses.get(item.item_id)
        if planned is None:
            continue
        rows.append(
            PublishedRow(
                version=PublishedRow.schema_version(),
                url_key=planned.url_key,
                published_on=day.date,
                item_id=item.item_id,
            )
        )
    return rows
