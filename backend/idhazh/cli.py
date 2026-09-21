"""The pipeline, as three stages a person can run one at a time.

Each stage takes a file and writes a file, which is the whole reason the
pipeline can be sharded across disposable machines and re-run cheaply. A stage
that only works as part of the whole is a stage nobody can debug.

    idhazh plan       read feeds, rank, record      -> run/<date>/plan.json
    idhazh work       fetch, extract, summarize, score -> run/<date>/items/*
    idhazh record     commit what one shard settled -> state/
    idhazh assemble   collect what finished        -> frontend/public/... + state/

`idhazh run` is the three in order, which is what a developer wants and what
the daily workflow calls. `record` is not among the three: the daily workflow
runs it inside the worker job so a run that dies before it publishes still
keeps what it measured.

    idhazh backfill-vectors   re-encode closed days whose vectors are short

That last one is a repair, not a stage. Nothing schedules it.

    idhazh telemetry <subcommand>   read or republish one day's instrument

`telemetry` is the one verb whose line is `<verb> <subcommand> ...` rather than
`<verb> --flags`. Its subcommands belong to the package that owns the
instrument, so `idhazh.telemetry.cli` parses them and this file hands over the
rest of the line unread.

Each stage is a module under `idhazh.stages`, and this router imports the
module rather than the names inside it. So `cli.stage_work` does not resolve,
and the only way to a stage is the module that defines it. A router that also
republished its workers' names would be a second import path nobody declared,
and every caller reaching through it would name the router as the home of code
the router does not contain.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from collections.abc import Sequence
from datetime import date as date_type
from pathlib import Path
from typing import Final

from idhazh import (
    assemble,
    config,
)
from idhazh.contracts.base import WORK_JOB, ServerJob
from idhazh.contracts.knobs.observability import ObservabilityConfig
from idhazh.contracts.knobs.run import RunConfig
from idhazh.contracts.qualification import (
    CandidateIdentity,
)
from idhazh.council import session as council_session
from idhazh.embed import Embedder
from idhazh.evals import sampling
from idhazh.evals.hhem import (
    HhemScorer,
)
from idhazh.fingerprint import (
    file_digest,
    runtime_build,
)
from idhazh.llm.server import DEFAULT_ENDPOINT
from idhazh.stages import (
    assemble as assemble_stage,
)
from idhazh.stages import (
    backfill_vectors,
    common,
    compact,
    decide,
    harvest,
    prune_stamp,
    prune_state,
    qualify,
    qualify_canaries,
    qualify_decide,
    rebuild_score_index,
    record,
    score_merge_line_holdout,
    site_weight,
    validate,
    validate_days,
    work,
)
from idhazh.stages import (
    plan as plan_stage,
)
from idhazh.telemetry import (
    cli as telemetry_cli,
)
from idhazh.telemetry import (
    silicon,
)


def _today() -> str:
    return assemble.utc_now()[:10]


def _council_run(parser: argparse.ArgumentParser, stage: str, given: str | None) -> str:
    """The run a council verb is, refused rather than invented when a step forgets it.

    Refused here and not defaulted, because every value this could reach for
    belongs to somebody else: a digest run's id claims a machine and a clock the
    council never drew, and a name minted per verb splits one night's rows across
    as many addresses as there are verbs.
    """
    if given is None:
        parser.error(
            f"{stage} needs --run-id: the council mints its own in its planning job, "
            "and a row filed under a digest run's id claims a machine and a clock "
            "this night never drew"
        )
    return given


#: Every verb this router accepts, and the whole of what `--help` lists. Named
#: here rather than inline so that the workflows can be held against it: a
#: workflow step spelling a verb this tuple does not carry is a run that dies
#: mid-pipeline, and the only way to catch that before the runner does is to
#: read both sides.
STAGES: Final[tuple[str, ...]] = (
    "plan",
    "shards",
    "work",
    "record",
    "fingerprint",
    "job-clock",
    "assemble",
    "harvest",
    "compact",
    "rebuild-score-index",
    "prune-stamp",
    "prune-state",
    "run",
    "validate",
    "decide",
    "qualify",
    "qualify-canaries",
    "qualify-decide",
    "backfill-vectors",
    "site-weight",
    "validate-days",
    "score-merge-line-holdout",
    "council-prepare",
    "council-settle",
    "council-shard",
    # Listed so `--help` names every verb, and never parsed: `main` hands the
    # line to the telemetry package before this parser is built.
    telemetry_cli.VERB,
)


def shard_count(items: int, *, run: RunConfig) -> int:
    """How many worker jobs a day of `items` earns.

    `run.shard_size` is what one worker is sized to carry, so a day that needs
    fewer workers gets fewer. Every extra job restores the weights again, and
    that restore is the largest fixed cost in the pipeline (Guardrail #2). The count
    never passes `run.max_parallel` and never falls below one, so an empty day
    still runs a worker that exits cleanly rather than an empty matrix.

    This is what a run derives for itself. An operator dispatching `digest.yml`
    names a count instead, and may name a larger one than this will ever return.

    The bound this has to clear is the worst case, not the day in hand: at
    `run.safety_ceiling_per_run` items the shard each worker draws must still
    finish inside the `work` job's timeout.
    """
    return max(1, min(-(-items // run.shard_size), run.max_parallel))


def _candidate_identity(settings: config.Settings, args: argparse.Namespace) -> CandidateIdentity:
    """Which bytes are about to run, read off the disk rather than off config.

    Config states an expectation and the file states a fact. The identity gate
    exists because those two can disagree - a mirror can serve a same-named file
    with different bytes - so the digest here is taken from the file the runtime
    will open (Guardrail #10).

    Every expectation comes from the entry, so a dispatch that named them
    separately could not drift from the file it was qualifying. A `byte_count`
    the entry does not declare falls back to the observed size, which makes that
    one comparison inert rather than false - the digest is the check either way.
    """
    model = settings.models.summarize
    weights = args.weights or (config.REPO_ROOT / "backend" / "models" / model.file)
    if not weights.exists():
        raise SystemExit(f"the candidate weights are not on disk: {model.file}")
    if not model.sha256:
        raise SystemExit(f"{model.id} declares no sha256, so nothing can verify what ran")
    return CandidateIdentity(
        model_id=model.id,
        repo=model.repo,
        revision=model.revision or "revision-not-recorded",
        file=model.file,
        quantisation=model.quantisation,
        sha256_expected=model.sha256,
        sha256_observed=file_digest(weights),
        bytes_expected=model.byte_count or weights.stat().st_size,
        bytes_observed=weights.stat().st_size,
        runtime_build=runtime_build(),
    )


def _scorer(enabled: bool) -> object | None:
    """The faithfulness scorer, or nothing at all.

    A scorer that will not load costs the run its eval rows. It must never cost
    the run its digest: `stage_assemble` already bands every item from the
    model-free counterweights when no row exists. The first real runner attempt
    died here - a transformers upgrade broke the checkpoint's own modelling code
    and all four workers exited before summarizing a single article.
    """
    if not enabled:
        common.LOG.warning("faithfulness scoring disabled - no eval rows will be written")
        return None
    scorer = HhemScorer()
    try:
        scorer.load()
    except Exception as error:
        common.LOG.error(
            "the faithfulness scorer did not load, so this run writes no eval rows: %s: %s",
            type(error).__name__,
            error,
        )
        return None
    return scorer


def _scores_this_run(
    observability: ObservabilityConfig, *, run_id: str, flag_allows: bool
) -> bool:
    """Whether the work stage should load a scorer for this run at all.

    Three things have to agree. `observability.evaluation_enabled` is the
    standing decision and is the default; `--no-faithfulness` overrides it for
    one invocation, because a flag beats a file and no flag turns the scorer
    back on; and at a rate below one the run has to be drawn.

    The draw is per run, so it is taken here rather than inside the item loop -
    a run scores everything or nothing (`evals/sampling.py`).
    """
    if not observability.evaluation_enabled:
        common.LOG.info("faithfulness scoring is off in config")
        return False
    if not flag_allows:
        return False
    if not sampling.run_is_sampled(run_id, observability.sample_rate):
        common.LOG.info(
            "run not drawn for scoring run_id=%s sample_rate=%s",
            run_id,
            observability.sample_rate,
        )
        return False
    return True


def main(argv: Sequence[str] | None = None) -> int:
    words = list(sys.argv[1:]) if argv is None else list(argv)
    if words and words[0] == telemetry_cli.VERB:
        # The one verb whose rest-of-line belongs to somebody else. Its
        # subcommands are the telemetry package's own surface, so handing over
        # here is what keeps this file a router: the alternative is a second
        # positional that every other verb would also have to carry.
        #
        # The roots come from here because this file is where they are resolved
        # for every other verb. The committed tree is the one an operator means;
        # a trial run's swap below is deliberately not applied, because the
        # question `telemetry show` answers is about the day that published.
        return telemetry_cli.main(
            words[1:], state_root=common.STATE_ROOT, digest_root=common.PUBLIC_ROOT
        )

    parser = argparse.ArgumentParser(prog="idhazh", description=__doc__)
    parser.add_argument("stage", choices=STAGES)
    parser.add_argument("--date", default=None, help="Defaults to today, UTC.")
    parser.add_argument("--config", type=Path, default=config.DEFAULT_CONFIG_DIR)
    parser.add_argument("--commit", default="0" * 40)
    parser.add_argument("--shard", type=int, default=0)
    parser.add_argument("--shards", type=int, default=1)
    parser.add_argument(
        "--execution",
        type=int,
        default=None,
        help=(
            "The identity of this execution, which becomes the run id after the date. "
            "CI passes the GitHub run id: GitHub allocates it, it is unique across "
            "every run of every workflow here, and no second execution can compute "
            "it. Left out, the run counts off the last committed manifest, which two "
            "overlapping runs were able to read the same answer from."
        ),
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help=(
            "Which run this is, for the council's verbs. The council mints its own "
            "name once in its planning job and hands it to every verb that writes a "
            "row, so a night's rows cannot arrive under two addresses. A digest run "
            "computes its own from --execution instead."
        ),
    )
    parser.add_argument(
        "--labeller",
        default=None,
        help=(
            "Who marked the holdout, for score-merge-line-holdout. The same name "
            "sample_sheet.py was given when it harvested the marks, because the row "
            "records what a reading is worth and a mark is worth what its labeller is."
        ),
    )
    parser.add_argument(
        "--no-faithfulness",
        action="store_true",
        help="Skip the scorer. The digest still publishes; the ledger stays empty.",
    )
    parser.add_argument(
        "--leaderboard",
        type=float,
        default=0.0,
        help="The published faithfulness score for the model being validated. A prior only.",
    )
    parser.add_argument(
        "--runner",
        default="local",
        help="Where the run happened. A laptop number is not a gate.",
    )
    parser.add_argument(
        "--cap",
        type=int,
        default=None,
        help=(
            "Take at most this many stories from each vertical when planning. For "
            "validation only: how big a day is is what a reader wants, not what a "
            "measurement needs."
        ),
    )
    parser.add_argument(
        "--repeats",
        type=int,
        default=3,
        help="How many times each frozen article is summarized. `wording_spread` reads them.",
    )
    parser.add_argument(
        "--corpus-per-shard",
        type=int,
        default=10,
        help="How many frozen articles one qualification shard replays.",
    )
    parser.add_argument(
        "--weights",
        type=Path,
        default=None,
        help="The GGUF the runtime opened. Its bytes are digested, not the config's claim.",
    )
    parser.add_argument(
        "--job-budget-minutes",
        type=float,
        default=330.0,
        help="The dispatch's own per-job bound. The budget gate is measured against it.",
    )
    parser.add_argument(
        "--counters-file",
        type=Path,
        default=Path("llama-metrics.prom"),
        help=(
            "The GET /metrics body this shard's model server returned at job end. "
            "Not spelled --metrics: that is llama-server's own flag, and no workflow "
            "step may write one by hand."
        ),
    )
    parser.add_argument(
        "--job",
        type=ServerJob,
        default=WORK_JOB,
        help=(
            "The workflow job writing this row. Two jobs stand a model server up and "
            "they serve different weights, so a row that cannot say which one wrote it "
            "proves nothing. The default is the job that wrote every row committed "
            "before the cell existed. Converted here rather than downstream: the "
            "readers are typed for the enum, and a bare string reached one of them as "
            "soon as a segment name asked for `.value`."
        ),
    )
    parser.add_argument(
        "--job-started-at",
        default="",
        help=(
            "Epoch seconds stamped by the first step of the shard job. The host row "
            "records the difference against its own scrape time. Empty means no "
            "stamp, and the cell then stays empty rather than reading zero."
        ),
    )
    parser.add_argument(
        "--server-log",
        type=Path,
        default=Path("llama-server.log"),
        help=(
            "llama-server's own log. The two lines it brackets a model load with give the "
            "fixed cost `run.shard_size` exists to amortise."
        ),
    )
    parser.add_argument(
        "--site-tree",
        type=Path,
        default=None,
        help=(
            "The built bundle `site-weight` measures - the directory the Pages deploy "
            "uploads. Required, and deliberately without a default: a default is how "
            "this came to measure the committed payloads instead of the site."
        ),
    )
    parser.add_argument(
        "--day",
        action="append",
        default=[],
        metavar="YYYY-MM-DD",
        help=(
            "A day for `validate-days` to open, repeatable. Every committed day when "
            "this is not given, which is what a contract change needs and nothing else "
            "does - a published day is frozen, so only the shape it is read through can "
            "invalidate it. A run that wrote one day names that day."
        ),
    )
    parser.add_argument(
        "--digest-root",
        type=Path,
        default=common.PUBLIC_ROOT,
        help=(
            "The committed day payloads `validate-days` reads. It defaults to the "
            "real tree, unlike --site-tree, because there is exactly one committed "
            "tree and a run against the wrong one cannot silently pass."
        ),
    )
    parser.add_argument(
        "--state-root",
        type=Path,
        default=None,
        help=(
            "Where `validate-days` keeps its receipts and where `compact` finds the "
            "segments waiting. For `validate-days` it moves with --digest-root, and "
            "the pairing is enforced rather than remembered: a receipt is a claim about "
            "a payload in that tree, so pointing one at a copy and leaving the other at "
            "the real state lets a day be skipped on a receipt earned by a different "
            "file. Reading the committed tree defaults this to the committed state; "
            "point --digest-root anywhere else and this has to be named."
        ),
    )
    parser.add_argument(
        "--corpus-dir",
        type=Path,
        default=common.CORPUS_ROOT,
        help="The training window `harvest` rolls. Never the reference set.",
    )
    parser.add_argument(
        "--tenant",
        default=None,
        help=(
            "Which registered tenant `council-shard` runs a shard of, by the slug "
            "`council.tenants` names. One cell of the matrix is one tenant: two sharing "
            "a job would each be handed the whole span the venue meant for one of them."
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Harvest even when finetune.harvest_every_days says it is not due yet.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what the telemetry fold would do and change nothing on disk.",
    )
    parser.add_argument(
        "--month",
        action="append",
        default=[],
        metavar="YYYY-MM",
        help=(
            "A month for `rebuild-score-index` to write again from the rows beside it, "
            "repeatable. Every committed day of that month is rewritten. A month that "
            "is not committed is an error, not a skip."
        ),
    )
    parser.add_argument(
        "--every-shard",
        action="store_true",
        help=(
            "The operator's full pass over every committed shard, and the only one that "
            "costs more every month. `rebuild-score-index` rewrites every month's index "
            "rather than the months named."
        ),
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_ENDPOINT,
        help=(
            "The llama-server one judging shard talks to. Every route it needs is derived "
            "from this one address, so a shard cannot ask one server for a tokenisation "
            "and another for a verdict."
        ),
    )
    args = parser.parse_args(argv)

    settings = config.load(args.config)
    logging.basicConfig(
        level=settings.app.logging.level.value,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stderr,
    )
    # One place, once, before any stage opens a ledger. A trial run exercises
    # production's code path and must not be readable as a production day, and
    # the only way to guarantee that for every ledger at once is to move the
    # root they all hang off (Guardrail #6).
    #
    # `prune-state` is the exception, and it is the only one: it is the stage
    # that EMPTIES the trial tree, so it has to see the tree that contains it.
    if settings.app.run.trial_state_dirname and args.stage != "prune-state":
        common.STATE_ROOT = common.STATE_ROOT / settings.app.run.trial_state_dirname
        logging.getLogger(__name__).warning(
            "trial run: every ledger goes to %s and no published series reads it",
            common.STATE_ROOT.relative_to(config.REPO_ROOT).as_posix(),
        )
    if args.stage == "site-weight":
        # Placed above the fetcher because measuring a directory reads no socket,
        # and starting one to do it would read every host's robots.txt for nothing.
        if args.site_tree is None:
            parser.error("site-weight needs --site-tree: the built bundle to measure")
        return site_weight.stage_site_weight(
            args.site_tree,
            settings.app.retention,
            items_per_day=settings.app.run.safety_ceiling_per_run,
        )

    if args.stage == "validate-days":
        # Above the fetcher for the same reason site-weight is: reading committed
        # files decides nothing about the open web, and starting a fetcher to do
        # it would read every host's robots.txt for nothing.
        #
        # The receipt store travels with the tree it is about. A receipt records
        # a payload's length and a day is settled on that length alone, never on
        # a re-read, so a receipt earned over the committed tree will settle a
        # same-length day in a scratch copy without opening it - measured
        # 2026-09-13: a copy of the newest day with `"items"` overwritten by
        # `"itemz"`, one byte for one byte, passed against the committed store
        # and was refused against an empty one. Forgetting the pair is therefore
        # a wrong answer rather than an untidy one, and this refuses it.
        if args.state_root is None and args.digest_root.resolve() != common.PUBLIC_ROOT.resolve():
            parser.error(
                "validate-days was given a --digest-root that is not the committed tree "
                f"({args.digest_root}) and no --state-root. A receipt is a claim about a "
                "payload in the tree it was earned over, and a day is settled on the "
                "length that receipt recorded - so the committed receipts would settle a "
                "day in this tree without opening it, and a pass here would mean nothing. "
                "Name --state-root as well, or read the committed tree."
            )
        state_dir = common.STATE_ROOT if args.state_root is None else args.state_root
        return validate_days.stage_validate_days(args.digest_root, args.day, state_dir=state_dir)

    if args.stage == "score-merge-line-holdout":
        # Above the fetcher for the reason validate-days is: it reads the marked
        # file and the published days that file names, and starting a fetcher to
        # do it would read every host's robots.txt for nothing.
        #
        # A person types this verb. Nothing schedules it, because the marked file
        # changes when somebody labels more pairs and not when a day publishes.
        if args.labeller is None:
            parser.error(
                "score-merge-line-holdout needs --labeller: the row records who marked "
                "the holdout, and a reading nobody can attribute is a reading nobody "
                "can argue with later"
            )
        if args.run_id is None:
            parser.error(
                "score-merge-line-holdout needs --run-id: the row says which run took "
                "the reading, and a digest run's id would claim a machine and a clock "
                "that scored nothing"
            )
        scored = score_merge_line_holdout.stage_score_merge_line_holdout(
            args.date or _today(),
            run_id=args.run_id,
            labeller=args.labeller,
            settings=settings,
            state_dir=None if args.state_root is None else args.state_root,
            digest_root=args.digest_root,
        )
        return 0 if scored is not None else 1

    if args.stage == "council-prepare":
        # Above the fetcher because picking the work is the council resolving its
        # own config and handing a date to whatever answers to a slug. Starting a
        # fetcher here would read every host's robots.txt for nothing.
        council_session.prepare(
            settings.app.council,
            date=args.date or _today(),
            run_id=_council_run(parser, args.stage, args.run_id),
        )
        return 0

    if args.stage == "council-settle":
        # Beside its siblings: it runs after every shard has reported and calls
        # no model of its own. It is also the one council verb that writes under
        # `state/`, so it is the one that is handed the root.
        council_session.settle(
            settings.app.council,
            date=args.date or _today(),
            run_id=_council_run(parser, args.stage, args.run_id),
            state_dir=common.STATE_ROOT if args.state_root is None else args.state_root,
        )
        return 0

    if args.stage == "prune-stamp":
        # Above the fetcher for the same reason: it rewrites one committed field.
        return prune_stamp.stage_prune_stamp(corpus_dir=args.corpus_dir, date=args.date or _today())

    if args.stage == "council-shard":
        # Above the fetcher because a hosted unit reads committed files and posts
        # to loopback. Starting a fetcher here would read every host's robots.txt
        # to answer a question about files already on disk.
        if args.tenant is None:
            parser.error(
                "council-shard needs --tenant: a cell of the matrix names which "
                "registered tenant it is a shard of, and a shard with no tenant would "
                "spend a whole runner deciding it had nothing to do"
            )
        council_session.run_shard(
            settings.app.council,
            slug=args.tenant,
            date=args.date or _today(),
            run_id=_council_run(parser, args.stage, args.run_id),
            shard=args.shard,
            shards=args.shards,
            # Read here rather than at the top of this file: the checkout, the
            # install and the weights restore ran before this process, and the
            # council's own preamble knob is what accounts for them.
            started=time.monotonic(),
        )
        return 0

    if args.stage == "compact":
        # Above the fetcher because it reads and rewrites committed files only.
        # It is also the catch-up for a run that died before its own assemble
        # drained the store, so a step that opened a socket here would read the
        # open web to decide what to fold.
        #
        # No --date. The head a row lands in is named by the row's own date cell,
        # and a run three days dead is exactly the one this has to reach.
        compact.stage_compact(common.STATE_ROOT if args.state_root is None else args.state_root)
        return 0

    if args.stage == "rebuild-score-index":
        # Above the fetcher for the same reason `compact` is: it reads and
        # rewrites committed files only.
        #
        # The cover is stated, never defaulted. `--month` names what to rewrite;
        # `--every-shard` reads every score row on record, which is the read the
        # index exists to avoid, so it is a person's decision (Guardrail #12).
        if bool(args.month) == args.every_shard:
            parser.error(
                "rebuild-score-index needs --month (the months to rewrite) "
                "or --every-shard (the operator's full pass), and not both"
            )
        return rebuild_score_index.stage_rebuild_score_index(
            months=None if args.every_shard else args.month
        )

    if args.stage == "prune-state":
        # And this one only reads and deletes committed files. A fold that opened
        # a socket would be reading the open web to decide what to delete.
        pruned_on = args.date or _today()
        return prune_state.stage_prune_state(
            observability=settings.app.observability,
            collect=settings.app.collect,
            extract_config=settings.app.extract,
            retention_config=settings.app.retention,
            lens_weights=settings.app.lens_weights,
            run=settings.app.run,
            run_id=plan_stage._run_id(pruned_on, args.execution),
            today=date_type.fromisoformat(pruned_on),
            dry_run=args.dry_run,
        )

    date = args.date or _today()
    # One fetcher for the whole invocation, so `idhazh run` reads each host's
    # robots.txt once across all three stages rather than once per stage.
    read_url = common.live_fetcher(settings)

    if args.stage == "validate":
        validate.stage_validate(
            settings=settings,
            date=date,
            leaderboard=args.leaderboard,
            scorer=_scorer(not args.no_faithfulness),
            fetcher=read_url,
        )
        return 0

    if args.stage == "decide":
        return decide.stage_decide(
            settings=settings,
            date=date,
            run_id=plan_stage._run_id(date, args.execution),
            commit_sha=args.commit,
            runner=args.runner,
        )

    if args.stage == "qualify":
        qualify.stage_qualify(
            settings=settings,
            date=date,
            shard=args.shard,
            shards=args.shards,
            repeats=args.repeats,
            corpus_per_shard=args.corpus_per_shard,
            candidate=_candidate_identity(settings, args),
            scorer=_scorer(not args.no_faithfulness),
            commit_sha=args.commit,
            runner=args.runner,
            fetcher=read_url,
        )
        return 0

    if args.stage == "qualify-canaries":
        return qualify_canaries.stage_qualify_canaries(settings=settings, date=date)

    if args.stage == "backfill-vectors":
        # `--date` names the day this treats as still open, and it is clamped to
        # today so a future date cannot bring the live day into scope. The live
        # day is the one the scheduled pipeline is appending to.
        return backfill_vectors.stage_backfill_vectors(
            root=common.PUBLIC_ROOT,
            index_root=assemble_stage._index_root(),
            today=min(date, _today()),
            embedder=Embedder(config.REPO_ROOT, settings.app.assist),
        )

    if args.stage == "qualify-decide":
        return qualify_decide.stage_qualify_decide(
            settings=settings,
            date=date,
            run_id=plan_stage._run_id(date, args.execution),
            job_budget_minutes=args.job_budget_minutes,
            runner=args.runner,
        )

    if args.stage == "shards":
        # stdout carries the answer and stderr carries the logs, so a caller
        # reads one number without parsing a log line.
        print(shard_count(len(common._load_plan(date).items), run=settings.app.run))
        return 0

    if args.stage in ("plan", "run"):
        plan = plan_stage.stage_plan(
            date, settings=settings, fetcher=read_url, cap=args.cap, execution=args.execution
        )
        assemble.write_atomic(common._plan_path(date), plan.to_json())
        common.LOG.info("planned date=%s items=%s feeds=%s", date, len(plan.items), plan.feeds_read)

    if args.stage in ("work", "run"):
        work_plan = common._load_plan(date)
        work.stage_work(
            work_plan,
            settings=settings,
            scorer=_scorer(
                _scores_this_run(
                    settings.app.observability,
                    run_id=work_plan.run_id,
                    flag_allows=not args.no_faithfulness,
                )
            ),
            shard=args.shard,
            shards=args.shards,
            fetcher=read_url,
        )

    if args.stage == "record":
        record.stage_record(
            common._load_plan(date), settings=settings, shard=args.shard, shards=args.shards
        )
        return 0

    if args.stage == "fingerprint":
        silicon.stage_fingerprint(
            common._load_plan(date),
            settings=settings,
            state_root=common.STATE_ROOT,
            shard=args.shard,
            job=args.job,
        )
        return 0

    if args.stage == "job-clock":
        silicon.stage_job_clock(
            common._load_plan(date),
            settings=settings,
            state_root=common.STATE_ROOT,
            shard=args.shard,
            job=args.job,
            job_started_at=int(args.job_started_at) if args.job_started_at else None,
            server_log_path=args.server_log,
            metrics_path=args.counters_file,
        )
        return 0

    if args.stage in ("assemble", "run"):
        assemble_plan = common._load_plan(date)
        assemble_stage.stage_assemble(
            assemble_plan,
            settings=settings,
            commit_sha=args.commit,
            runner=args.runner,
            # The same arithmetic the `shards` verb prints for the workflow's
            # fanout, read off the same plan file. The manifest records what was
            # planned; the machine rows record who answered. Two instruments.
            shards=shard_count(len(assemble_plan.items), run=settings.app.run),
        )

    if args.stage == "harvest":
        harvest.stage_harvest(
            date,
            settings=settings,
            corpus_dir=args.corpus_dir,
            force=args.force,
        )

    return 0
