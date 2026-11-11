"""How can named retained Articles run fresh production calls without publishing anything?"""

from __future__ import annotations

import argparse
import logging
import os
import re
import subprocess
import sys
import tempfile
import time
from collections.abc import Mapping, Sequence
from pathlib import Path

from pydantic import TypeAdapter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from idhazh import assemble, atomic_write, config, run_context, summarize
from idhazh.classify import calls
from idhazh.command_logging import configure_command_logging
from idhazh.contracts.article import Article, ArticleStatus
from idhazh.contracts.base import ItemId, ServerJob, canonical_json
from idhazh.contracts.file_envelope import WriterIdentity
from idhazh.contracts.item_health import FailureCode, ItemOutcome, ItemStage
from idhazh.contracts.pipeline_tests import PipelineTestsConfig
from idhazh.contracts.run_plan import RunPlan
from idhazh.contracts.summary import SummaryStatus
from idhazh.contracts.visual_decision import PAYLOAD_SUFFIX, VisualState
from idhazh.fingerprint import (
    UNRECORDED_TEMPLATE,
    build_inputs,
    runner_class,
    runtime_build,
)
from idhazh.llm.server import (
    derive_turn_markers,
    props,
    request_timeout_seconds,
    resolve_endpoint,
)
from idhazh.stages.common import INPUTS_PAYLOAD
from idhazh.stages.two_calls import two_calls_one_item
from idhazh.telemetry import host
from idhazh.telemetry.record import Flags, ItemRecorder, persist
from idhazh.visual_outcomes import project_visual_outcome
from utilities.digest_recovery_download import SourceRun, download
from utilities.digest_recovery_inputs import select_plan, unpack, worker_files
from utilities.publication_git import Repository
from utilities.publication_request import IntegrityError, relative, safe_file

LOG = logging.getLogger("idhazh")
DEFAULT_ROOT = "backend/var/retained-article-verification"


def select_ids(value: str, *, limit: int) -> tuple[str, ...]:
    """Validate an explicit comma-separated selection before downloads or model work."""
    selected = TypeAdapter(list[ItemId]).validate_python(
        [part.strip() for part in value.split(",")]
    )
    if not 1 <= len(selected) <= limit:
        raise ValueError(f"select between 1 and {limit} retained item IDs")
    if len(set(selected)) != len(selected):
        raise ValueError("retained item IDs must be unique")
    return tuple(selected)


def source_execution(value: str) -> str:
    if not re.fullmatch(r"[1-9][0-9]*", value):
        raise ValueError("source run must be a positive platform run ID")
    return value


def private_file(root: Path, name: str, *, exists: bool = False) -> Path:
    """Confine named files to a supplied root, including the root's own ancestors."""
    for parent in (root, *root.parents):
        if parent.is_symlink() or parent.is_junction():
            raise IntegrityError("retained replay root crosses a symlink or junction")
    return safe_file(root, name, exists=exists)


def selected_articles(
    plan: RunPlan, files: Mapping[str, bytes], item_ids: Sequence[str]
) -> tuple[Article, ...]:
    """Keep only eligible native Articles whose identities belong to the saved plan."""
    item_ids = TypeAdapter(list[ItemId]).validate_python(item_ids)
    if not item_ids or len(set(item_ids)) != len(item_ids):
        raise ValueError("retained replay requires an explicit unique item selection")
    planned = {item.item_id: item for item in plan.items}
    selected: list[Article] = []
    for item_id in item_ids:
        name = f"{item_id}.article.json"
        if item_id not in planned or name not in files:
            raise IntegrityError("selected item has no retained planned Article", (name,))
        article = Article.model_validate_json(files[name])
        item = planned[item_id]
        if article.item_id != item_id or article.url_key != item.url_key:
            raise IntegrityError("retained Article does not match the planned identity", (name,))
        if article.status is not ArticleStatus.OK:
            raise IntegrityError("selected Article did not pass extraction", (name,))
        selected.append(article)
    return tuple(selected)


def prepare_inputs(
    root: Path,
    *,
    source: SourceRun,
    archives: Mapping[str, bytes],
    failed_shards: frozenset[int],
    item_ids: Sequence[str],
) -> tuple[RunPlan, str]:
    """Validate native artifacts, then retain only the source plan and selected Article bytes."""
    private_file(root, "unused")
    root.mkdir(parents=True, exist_ok=False)
    if "plan" not in archives:
        raise IntegrityError("source run has no retained plan artifact")
    plans = unpack(archives["plan"])
    with tempfile.TemporaryDirectory(dir=root) as scratch:
        plan, name = select_plan(
            plans,
            Path(scratch),
            execution=str(source.id),
            attempt=source.run_attempt,
            commit=source.head_sha,
        )
    files = worker_files(
        plan,
        {name: data for name, data in archives.items() if name != "plan"},
        failed_shards=failed_shards,
    )
    selected_articles(plan, files, item_ids)
    plan_file = f"source/{name}"
    atomic_write.write_atomic_bytes(private_file(root, plan_file), plans[name])
    for item_id in item_ids:
        name = f"{item_id}.article.json"
        atomic_write.write_atomic_bytes(private_file(root, f"inputs/{name}"), files[name])
    return plan, plan_file


def load_inputs(
    root: Path,
    *,
    plan_file: str,
    execution: str,
    attempt: int,
    commit: str,
    item_ids: Sequence[str],
) -> tuple[RunPlan, tuple[Article, ...]]:
    """Revalidate the selected native inputs before the first model request."""
    saved = private_file(root, plan_file, exists=True)
    with tempfile.TemporaryDirectory(dir=root) as scratch:
        plan, _ = select_plan(
            {saved.name: saved.read_bytes()},
            Path(scratch),
            execution=source_execution(execution),
            attempt=attempt,
            commit=commit,
        )
    files = {
        f"{item_id}.article.json": private_file(
            root, f"inputs/{item_id}.article.json", exists=True
        ).read_bytes()
        for item_id in item_ids
    }
    return plan, selected_articles(plan, files, item_ids)


def run_calls(
    root: Path,
    *,
    plan: RunPlan,
    articles: Sequence[Article],
    settings: config.Settings,
    identity: WriterIdentity,
) -> None:
    """Run each real call pair once and keep native products under fresh private roots."""
    flags = Flags.of(settings.app.logging)
    if not flags.capture_prompts or not flags.capture_replies:
        raise ValueError("retained replay requires configured prompt and reply capture")
    if identity.run_id == plan.run_id or not identity.run_id.startswith(f"{plan.date}-"):
        raise ValueError("retained replay requires a distinct execution on the source UTC day")
    # Validate the whole selection before contacting the model, not one item at a time.
    articles = selected_articles(
        plan,
        {f"{article.item_id}.article.json": article.to_json().encode() for article in articles},
        [article.item_id for article in articles],
    )
    output = private_file(root, "outputs/unused").parent
    output.mkdir(parents=True, exist_ok=False)
    endpoint = resolve_endpoint(settings.app.model_server.base_url)
    model = settings.models.summarizer
    timeout = request_timeout_seconds(model)
    observed = props(endpoint, timeout=timeout)
    markers = derive_turn_markers(endpoint, entry=model, timeout=timeout)
    facts = host.host_facts(job=ServerJob.WORK)
    LOG.info(identity.model_dump_json())
    failures: list[str] = []
    for index, article in enumerate(articles):
        item_root = output / article.item_id
        items = item_root / "items"
        inputs = build_inputs(
            model=model,
            model_sha256=model.sha256,
            server=model.server,
            sampling=model.sampling,
            truncation_cap_tokens=settings.app.extract.truncation_cap_tokens,
            runtime_build=runtime_build(base_url=settings.app.model_server.base_url),
            chat_template=str(observed.get("chat_template") or UNRECORDED_TEMPLATE),
            prompt=calls.prompt_inputs(
                settings.app.summarize,
                markers=markers,
                visuals=settings.app.visuals,
                prompt_files=settings.app.prompt_files,
                config_dir=settings.config_dir,
            ),
            output_schema=summarize.output_schema_text(settings.app.summarize),
            runner_class=runner_class(),
            extractor_version=article.extractor_version,
            sanitizer_version=article.sanitizer_version,
            markers=markers,
        )
        atomic_write.write_atomic(
            items / INPUTS_PAYLOAD, canonical_json(inputs.model_dump(mode="json"))
        )
        recorder = ItemRecorder(
            run_id=identity.run_id, flags=flags, now=assemble.utc_now, log=LOG
        )
        recorder.note(
            date=plan.date,
            run_id=identity.run_id,
            item_id=article.item_id,
            url_key=article.url_key,
            canonical_url=str(article.canonical_url),
            vertical=article.vertical,
            source_id=article.source_id,
            item_index=index,
            item_started_at=assemble.utc_now(),
            machine_shard=identity.shard,
            model_id=model.id,
            model_quantisation=model.quantisation,
            source_chars=len(article.text or ""),
            source_words=article.word_count,
            **facts.shard_cells(),
        )
        recorder.start()
        started = time.monotonic()
        result = two_calls_one_item(
            article,
            settings,
            date=plan.date,
            run_id=identity.run_id,
            recorder=recorder,
            capture_root=item_root / "captures",
            render_root=item_root / "assets",
        )
        summary, decision = result.summary, result.decision
        atomic_write.write_atomic(items / f"{article.item_id}.summary.json", summary.to_json())
        if decision is not None:
            atomic_write.write_atomic(
                items / f"{article.item_id}{PAYLOAD_SUFFIX}", decision.to_json()
            )
            recorder.note(**project_visual_outcome(decision))
        ok = summary.status is SummaryStatus.OK
        spent = [reply for reply in (result.label_reply, result.answer_reply) if reply is not None]
        recorder.note(
            summarize_ms=int((time.monotonic() - started) * 1000),
            stage=ItemStage.SUMMARIZE.value,
            outcome=(ItemOutcome.OK if ok else ItemOutcome.FAILED).value,
            code=None if ok else (summary.failure_code or FailureCode.UNKNOWN).value,
            detail=None if ok else summary.failure_detail,
            summary_words=len((summary.summary or "").split()),
            model_calls=len(spent) or None,
            prefill_ms=summary.prefill_ms if spent else None,
            decode_ms=summary.decode_ms if spent else None,
            input_tokens=summary.input_tokens if spent else None,
            output_tokens=summary.output_tokens if spent else None,
            cached_tokens=summary.cached_tokens if spent else None,
        )
        persist(items, recorder.done())
        if (
            not ok
            or decision is None
            or result.label_reply is None
            or result.answer_reply is None
            or decision.visual_state is VisualState.RENDER_FAILED
        ):
            failures.append(article.item_id)
        elif decision.data_path is not None:
            private_file(item_root / "assets", decision.data_path, exists=True)
    if failures:
        raise ValueError(f"retained replay failed for selected items: {', '.join(failures)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "run"))
    parser.add_argument("--root", default=DEFAULT_ROOT)
    parser.add_argument("--source-run", required=True)
    parser.add_argument(
        "--item-ids", required=True, help="Explicit comma-separated native item IDs"
    )
    parser.add_argument("--candidate-models-file", default="")
    parser.add_argument("--plan-file")
    parser.add_argument("--source-attempt", type=int)
    parser.add_argument("--source-commit")
    parser.add_argument("--execution", default=os.environ.get("GITHUB_RUN_ID"))
    args = parser.parse_args(argv)
    try:
        settings = config.load()
        configure_command_logging(settings.app.logging.level.value)
        source_execution(args.source_run)
        if args.candidate_models_file:
            raise ValueError("retained mode uses the committed production model, not a candidate")
        policy = PipelineTestsConfig.read(config.DEFAULT_CONFIG_DIR / "pipeline-tests.json")
        selected = select_ids(args.item_ids, limit=policy.articles_a_dispatch)
        relative(args.root)
        if Path(args.root).parts[:2] != ("backend", "var") or len(Path(args.root).parts) < 3:
            raise ValueError("retained replay root must be a private directory below backend/var")
        root = config.REPO_ROOT / args.root
        private_file(root, "unused")
        if args.command == "prepare":
            source, archives, failed = download(args.source_run)
            plan, plan_file = prepare_inputs(
                root, source=source, archives=archives, failed_shards=failed, item_ids=selected
            )
            LOG.info(source.model_dump_json())
            output = (
                f"date={plan.date}\nplan_file={plan_file}\n"
                f"source_attempt={source.run_attempt}\nsource_commit={source.head_sha}\n"
                f"budget_minutes={policy.budget_minutes}\n"
            )
            print(output, end="")
            if target := os.environ.get("GITHUB_OUTPUT"):
                with Path(target).open("a", encoding="utf-8", newline="\n") as handle:
                    handle.write(output)
            return 0
        if not args.plan_file or not args.source_attempt or not args.source_commit:
            raise ValueError("run requires the validated native plan and source attempt identity")
        if not args.execution:
            raise ValueError("run requires a new platform execution ID")
        source_execution(args.execution)
        plan, articles = load_inputs(
            root,
            plan_file=args.plan_file,
            execution=args.source_run,
            attempt=args.source_attempt,
            commit=args.source_commit,
            item_ids=selected,
        )
        identity = WriterIdentity(
            run_id=f"{plan.date}-{args.execution}",
            attempt=run_context.run_attempt(),
            job=ServerJob.WORK,
            shard=0,
            producer="utilities.replay_article_calls",
            git_sha=Repository(config.REPO_ROOT).git("rev-parse", "HEAD").strip(),
        )
        run_calls(root, plan=plan, articles=articles, settings=settings, identity=identity)
        return 0
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        LOG.error("retained replay failed: %s", error)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
