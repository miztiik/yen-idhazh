"""Retire what the ledgers no longer answer for: an item-health month and the.

One stage, one module. `idhazh.cli` chooses which stage runs and holds no stage
body of its own (CLAUDE.md section 1a, "A router is the sharpest case").
"""

from __future__ import annotations

from datetime import date as date_type
from pathlib import Path

from idhazh import assemble, ledger, retention, telemetry
from idhazh.contracts.knobs.collect import CollectConfig
from idhazh.contracts.knobs.extract import ExtractConfig
from idhazh.contracts.knobs.observability import ObservabilityConfig
from idhazh.contracts.knobs.placement import LensWeightsConfig
from idhazh.contracts.knobs.retention import RetentionConfig
from idhazh.evals import archive as score_archive
from idhazh.stages import common
from idhazh.stages.common import LOG
from idhazh.telemetry.publish import day_metrics, public_telemetry


def stage_prune_state(
    *,
    observability: ObservabilityConfig,
    collect: CollectConfig,
    retention_config: RetentionConfig,
    run_id: str,
    today: date_type,
    extract_config: ExtractConfig | None = None,
    lens_weights: LensWeightsConfig | None = None,
    state_dir: Path | None = None,
    public_root: Path | None = None,
    digest_root: Path | None = None,
    dry_run: bool = False,
) -> int:
    """Retire what the ledgers no longer answer for: an item-health month and the
    browser's copy of it, a feed-health month, a host-fingerprint month, every
    seen day file below the window the planner reads, every committed span trace
    past its short window, and every score month past its full-grain window. Then
    clean the rendered visuals the archive policy has aged out, and record what
    that pass found.

    The item-health boundary is still a month, and only the files below it are
    days: `retention.prune_telemetry` folds a month whole from that month's day
    files and then unlinks them. Feed health files by day too and its boundary is
    a month for the same reason, so `retention.prune_feed_health` takes a month's
    day files whole - it just folds nothing first, because a total of what a feed
    did fourteen months ago has no reader. The host fingerprints file and delete
    the same way, and for the same reason.

    Every ledger above is in this one step because they share the one property
    that makes it safe: all of it runs after the day is committed, and none of it
    can cost a reader anything it has not already been given.

    **The visuals are the one thing here that does not share that property.**
    Deleting a picture costs a reader the picture. They are in this step because
    it is the step that runs after the commit and because the pass still removes
    nothing - `retention.dry_run` is true and the flag makes it report-only - so
    what runs today is a measurement of the backlog and nothing else.
    `retention.image_months` took its first value on 2026-09-13, so the pass now
    names a cutoff rather than declining to draw one; nothing published is old
    enough to sit behind it. Switching
    the deletion on is a separate change, and it needs two more things this step
    does not have: the commit call below it has to stage
    `frontend/public/digest` as well, because `git add` records a removal only
    for a path it is handed, and the promise in
    `docs/architecture/publishing/layout.md` about a workflow of its own has to
    be met or re-decided.

    Runs after the day is committed, never before. A fold that ran first and then
    failed would leave a month deleted from a tree nothing pushed, and the next
    run would fold a shard that had already been folded - so it sits behind the
    commit that makes the day real, where the worst it can cost is one run's
    worth of bytes.

    It reports rather than fails. What this job owes a reader is the published
    day; a fold that will not run must never be the thing that stops one.

    **Every file a live run would remove is named, one line each.** A count says
    a deletion happened and nothing about what it took, and the workflow ships
    this in dry run precisely so a person can read that list before the deletion
    is switched on.
    """
    state = state_dir if state_dir is not None else common.STATE_ROOT
    # The published tree only defaults beside the default state tree. A caller
    # that named its own `state_dir` and left this out gets no browser copy
    # rather than the committed one - deleting a published shard out of a test
    # run is the failure this pairing exists to stop.
    public = public_root
    if public is None and state_dir is None:
        public = public_telemetry.DEFAULT_PUBLIC_ROOT
    # The day payloads pair with the state tree the same way and for the same
    # reason: a test that named its own state must not have this one default to
    # the committed archive.
    digest = digest_root
    if digest is None and state_dir is None:
        digest = common.PUBLIC_ROOT

    removed: list[str] = []
    removed += _prune_seen_shards(state, collect, today, dry_run=dry_run)
    removed += _prune_counterfactual_shards(
        state, lens_weights or LensWeightsConfig(), today, dry_run=dry_run
    )
    removed += _prune_trace_shards(state, observability, today, dry_run=dry_run)
    removed += _prune_feed_health_shards(state, observability, today, dry_run=dry_run)
    removed += _prune_host_fingerprint_shards(state, observability, today, dry_run=dry_run)
    removed += _prune_score_shards(state, observability, today, dry_run=dry_run)
    removed += _prune_trial_shards(state, retention_config, today, dry_run=dry_run)
    removed += _prune_digest_fragments(state, retention_config, today, dry_run=dry_run)
    result = retention.prune_telemetry(
        state, observability, today, public_root=public, dry_run=dry_run
    )
    if not result.changed:
        LOG.info(
            "telemetry fold: nothing older than %s months, so every month is still at full grain",
            observability.item_health_full_grain_months,
        )
    else:
        LOG.info(
            "telemetry fold%s: %s folded %s rows into %s, dropped the browser copy of %s, "
            "hard-deleted %s",
            " (dry run)" if result.dry_run else "",
            ", ".join(result.folded) or "no month",
            result.rows_folded,
            result.aggregate_rows,
            ", ".join(result.public_deleted) or "no month",
            ", ".join(result.hard_deleted) or "no month",
        )
        removed += list(result.days_removed)
        removed += [public_telemetry.shard_relpath(stem) for stem in result.public_deleted]
        removed += [ledger.telemetry_aggregate_relpath(stem) for stem in result.hard_deleted]

    if digest is not None:
        _clean_the_visuals(
            digest,
            retention_config,
            today,
            run_id=run_id,
            state_dir=state,
            dry_run=dry_run,
        )

    _report_removals(sorted(removed), dry_run=dry_run)
    return 0


def _clean_the_visuals(
    digest_root: Path,
    config: RetentionConfig,
    today: date_type,
    *,
    run_id: str,
    state_dir: Path,
    dry_run: bool,
) -> None:
    """Run the archive cleanup over the day payloads and commit what it found.

    The row lands whatever happened, including the run where the policy is off
    and nothing was a candidate. A ledger written only on the interesting runs
    cannot show that a backlog is shrinking, because the runs it skips are the
    ones that would have been the baseline.
    """
    result = retention.prune(digest_root, config, today, dry_run=dry_run)
    row = retention.prune_row(result, config, date_stamp=today.isoformat(), run_id=run_id)
    landed = ledger.append_visual_prunes(state_dir, row.date, [row])
    LOG.info(
        "visual cleanup%s: %s candidates older than %s, %s deleted, %s held back by the "
        "%s-file fuse, %s bytes reclaimed, oldest picture still kept %s (%s row)",
        " (dry run)" if result.dry_run else "",
        result.considered,
        row.cutoff_date or "no cutoff - the policy is off",
        result.deleted,
        result.skipped_by_fuse,
        config.max_deletes_per_run,
        result.bytes_reclaimed,
        row.oldest_kept or "none",
        landed,
    )


def _report_removals(paths: list[str], *, dry_run: bool) -> None:
    """Name every file, one line each, in the POSIX form section 2 asks for.

    This list is the deliverable of a dry run: it is what a person reads before
    turning the deletion on, so it is the paths themselves and never a count.
    """
    if not paths:
        LOG.info("prune-state removes no file today")
        return
    verb = "would remove" if dry_run else "removed"
    LOG.info("prune-state %s %s files:", verb, len(paths))
    for path in paths:
        LOG.info("prune-state %s %s", verb, path)


def _prune_feed_health_shards(
    state: Path, observability: ObservabilityConfig, today: date_type, *, dry_run: bool
) -> list[str]:
    """Delete the feed-health months no quarantine and no console read reaches.

    Deleted rather than folded: a row here is one feed's result on one run, and
    a total over a month fourteen months back answers nothing anybody asks.

    Returns the day files it removed, taken from the result rather than spelled
    from the month stems: the ledger files by day, so a synthesised `<month>-01`
    would name a file it may never have held.
    """
    feed = retention.prune_feed_health(state, observability, today, dry_run=dry_run)
    if not feed.changed:
        LOG.info(
            "feed-health prune: every shard is inside the %s-month window, so none was deleted",
            observability.feed_health_keep_months,
        )
        return []
    LOG.info(
        "feed-health prune%s: deleted %s, freed %s bytes, kept %s",
        " (dry run)" if feed.dry_run else "",
        ", ".join(feed.deleted),
        feed.bytes_freed,
        ", ".join(feed.kept) or "no shard",
    )
    return list(feed.days_removed)


def _prune_host_fingerprint_shards(
    state: Path, observability: ObservabilityConfig, today: date_type, *, dry_run: bool
) -> list[str]:
    """Delete the host-fingerprint months no published machine shard reaches.

    Deleted rather than folded, the same shape as the feed-health prune above
    and for the same reason: a row is one job's silicon on one run, and a total
    over a month fourteen months back names no machine.

    `observability.host_fingerprint_keep_months` is null by default, and null
    means never - so until the committed config names a window this walks the
    tree, removes nothing, and says which age it measured against.

    Returns the day files it removed, taken from the result rather than spelled
    from the month stems: the ledger files by day, so a synthesised `<month>-01`
    would name a file it may never have held.
    """
    hosts = retention.prune_host_fingerprint(state, observability, today, dry_run=dry_run)
    if not hosts.changed:
        months = observability.host_fingerprint_keep_months
        LOG.info(
            "host-fingerprint prune: %s, so none was deleted",
            f"every shard is inside the {months}-month window"
            if months is not None
            else "the window is off and every shard is kept",
        )
        return []
    LOG.info(
        "host-fingerprint prune%s: deleted %s, freed %s bytes, kept %s",
        " (dry run)" if hosts.dry_run else "",
        ", ".join(hosts.deleted),
        hosts.bytes_freed,
        ", ".join(hosts.kept) or "no shard",
    )
    return list(hosts.days_removed)


def _prune_seen_shards(
    state: Path, collect: CollectConfig, today: date_type, *, dry_run: bool
) -> list[str]:
    """Delete the seen day files `rank` will not read again, and say what went.

    Separate from the fold above so a day that will not delete cannot stop a
    month being folded, and so the log line names one ledger at a time.

    **Counted rather than listed, which is the one thing that moved when the
    ledger went to day grain.** `deleted` and `kept` were at most a handful of
    month stems and the line named every one; the window is 90 days, so `kept`
    is now up to 91 paths and a line that joined them would be a wall nobody
    reads. `_report_removals` already prints every removed file one line each,
    so the count and the oldest file kept are what this line adds - and the
    oldest kept is the number that says whether the boundary landed where the
    reader needs it.
    """
    seen = retention.prune_seen(
        state,
        today=today.isoformat(),
        within_days=collect.seen_window_days,
        dry_run=dry_run,
    )
    if not seen.changed:
        LOG.info(
            "seen prune: every day file is inside the %s-day window, so none was deleted",
            collect.seen_window_days,
        )
        return []
    LOG.info(
        "seen prune%s: deleted %s day files, freed %s bytes, kept %s back to %s",
        " (dry run)" if seen.dry_run else "",
        len(seen.deleted),
        seen.bytes_freed,
        len(seen.kept),
        seen.kept[0] if seen.kept else "no day file",
    )
    return list(seen.deleted)


def _prune_counterfactual_shards(
    state: Path, lens_weights: LensWeightsConfig, today: date_type, *, dry_run: bool
) -> list[str]:
    """Delete the counterfactual day files outside the window anyone reads.

    Its own helper beside the seen one, for the reason that one gives: a day
    that will not delete in one ledger must not stop another being cleaned, and
    the log line names one ledger at a time.

    Counted rather than listed, the way the seen line is. The window is 30 days,
    so `kept` is up to 31 paths and joining them would be a wall nobody reads -
    `_report_removals` already names every removed file, one line each.
    """
    scores = retention.prune_counterfactual_scores(
        state,
        today=today.isoformat(),
        within_days=lens_weights.window_days,
        dry_run=dry_run,
    )
    if not scores.changed:
        LOG.info(
            "counterfactual prune: every day file is inside the %s-day window, so none was deleted",
            lens_weights.window_days,
        )
        return []
    LOG.info(
        "counterfactual prune%s: deleted %s day files, freed %s bytes, kept %s back to %s",
        " (dry run)" if scores.dry_run else "",
        len(scores.deleted),
        scores.bytes_freed,
        len(scores.kept),
        scores.kept[0] if scores.kept else "no day file",
    )
    return list(scores.deleted)


def _prune_trace_shards(
    state: Path, observability: ObservabilityConfig, today: date_type, *, dry_run: bool
) -> list[str]:
    """Delete the committed span traces past their window, and say what went.

    A trace is a lookup an operator opens for a recent run, so it deletes rather
    than folds - the same shape as the seen prune above and for the same reason.
    `state/traces/` does not exist until tracing is switched on, so until then
    this names the window it measured against and removes nothing.
    """
    traces = retention.prune_traces(
        state,
        today=today,
        within_days=observability.trace_window_days,
        dry_run=dry_run,
    )
    if not traces.changed:
        LOG.info(
            "trace prune: every committed trace is inside the %s-day window, so none was deleted",
            observability.trace_window_days,
        )
        return []
    LOG.info(
        "trace prune%s: deleted %s files, freed %s bytes, kept %s inside the window",
        " (dry run)" if traces.dry_run else "",
        len(traces.deleted),
        traces.bytes_freed,
        traces.kept,
    )
    return list(traces.deleted)


def _prune_digest_fragments(
    state: Path, retention_config: RetentionConfig, today: date_type, *, dry_run: bool
) -> list[str]:
    """Delete the per-run blocks of every day past the window, and say what went.

    A block is one run's half of a published day. The day is assembled from all
    of them, so they are live while the date can still gain a run and are a
    second full copy of every story once it cannot. The published day is never
    touched.
    """
    fragments = retention.prune_digest_fragments(state, retention_config, today, dry_run=dry_run)
    if not fragments.changed:
        LOG.info(
            "digest fragment prune: every day's blocks are inside the %s-month window, "
            "so none was deleted",
            retention_config.image_months,
        )
        return []
    LOG.info(
        "digest fragment prune%s: deleted %s files, freed %s bytes",
        " (dry run)" if fragments.dry_run else "",
        len(fragments.deleted),
        fragments.bytes_freed,
    )
    return list(fragments.deleted)


def _trial_roots(state: Path) -> list[str]:
    """Every child of `state/` that is a trial run's tree rather than a store.

    Read off the tree, not off `run.trial_state_dirname`. That knob is null in
    production and cannot be set there: `idhazh.cli` redirects
    `common.STATE_ROOT` into `state/<trial_state_dirname>/` on every stage but
    this one, so a production value would move the daily pipeline's own ledgers
    into the trial root. Nothing had ever pruned `state/pipeline-tests/`
    because of it.

    A store is created through its directory constant, so the names subtracted
    here gain a member in the same commit that adds a store and discovery
    cannot fall out of step. The four below are the stores `ledger` does not
    own; each is read from its owning module rather than retyped, and they are
    imported here rather than into `ledger` because two of those modules import
    `ledger` themselves.
    """
    if not state.is_dir():
        return []
    stores = ledger.STORE_DIRNAMES | {
        telemetry.TRACES_DIRNAME,
        day_metrics.DIRNAME,
        assemble.FRAGMENTS_DIRNAME,
        score_archive.ARCHIVE_DIRNAME,
    }
    return sorted(
        child.name for child in state.iterdir() if child.is_dir() and child.name not in stores
    )


def _prune_trial_shards(
    state: Path,
    retention_config: RetentionConfig,
    today: date_type,
    *,
    dry_run: bool,
) -> list[str]:
    """Empty every trial run's ledgers past their window, and say what went.

    One call per trial root, and the root itself goes once the pass has emptied
    it - without that the child count under `state/` only ever rises
    (Guardrail #12). A trial renamed since its last run is cleaned like any
    other, because nothing here is matched against a name anybody remembered.
    """
    removed: list[str] = []
    for dirname in _trial_roots(state):
        trial = retention.prune_trial_state(
            state,
            dirname=dirname,
            today=today,
            within_days=retention_config.trial_state_days,
            dry_run=dry_run,
        )
        if not trial.changed:
            LOG.info(
                "trial prune: every file under state/%s is inside the %s-day window, "
                "so none was deleted",
                dirname,
                retention_config.trial_state_days,
            )
            continue
        LOG.info(
            "trial prune%s: deleted %s files under state/%s, freed %s bytes, kept %s",
            " (dry run)" if trial.dry_run else "",
            len(trial.deleted),
            dirname,
            trial.bytes_freed,
            trial.kept,
        )
        removed += list(trial.deleted)
    return removed


def _prune_score_shards(
    state: Path, observability: ObservabilityConfig, today: date_type, *, dry_run: bool
) -> list[str]:
    """Archive the score months past their full-grain window, then delete their days.

    The one store here whose deletion is preceded by a summary that is written,
    read back and reconciled against the files it replaces. The log says what the
    archive weighs against what those files weighed, because that ratio is the
    measurement this policy rests on and a dry run is where a person reads it.

    The files come from the result rather than being spelled here. A month is a
    directory of day files, so a caller that synthesised `<month>-01` would name
    a file the ledger may never have held - and the list a dry run prints has to
    be the list a live run removes, file for file.
    """
    scores = retention.prune_scores(state, observability, today, dry_run=dry_run)
    if not scores.changed:
        LOG.info(
            "score archive: every month is inside the %s-month window, so none was summarised",
            observability.scores_full_grain_months,
        )
        return []
    LOG.info(
        "score archive%s: summarised %s - %s rows and %s distinct measurements over "
        "%s day files, %s bytes of rows into %s bytes of archive - dropped %s index "
        "day files beside them - and hard-deleted %s",
        " (dry run)" if scores.dry_run else "",
        ", ".join(scores.archived) or "no month",
        scores.rows_archived,
        scores.observations_indexed,
        len(scores.days_removed),
        scores.source_bytes,
        scores.archive_bytes,
        len(scores.index_days_removed),
        ", ".join(scores.hard_deleted) or "no month",
    )
    removed = list(scores.days_removed) + list(scores.index_days_removed)
    removed += [score_archive.archive_relpath(stem) for stem in scores.hard_deleted]
    return removed
