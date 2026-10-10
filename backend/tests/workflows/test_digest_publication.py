"""Does ASSEMBLE really rebuild against fresh main without replacing completed raw bytes?"""

import dataclasses
import json
from datetime import date, timedelta
from pathlib import Path

import pytest
from conftest import CONFIG_DIR, CONTRACT_FIXTURES_DIR, REFILL_PUBLISHED
from gardener._garden import an_origin, git, on_origin, quiet_git, write
from pipeline._builders import FULL_TEXT, plan, score_one_item
from pipeline.test_publish_window import stage_visual_payloads
from retention._trees import health_row
from test_corpus_harvest import row_at

from idhazh import completed_writes, config, corpus, ledger
from idhazh.contracts.article import Article
from idhazh.contracts.base import ServerJob, derive_output_digest
from idhazh.contracts.eval_row import EvalRow
from idhazh.contracts.file_envelope import Period, WriterIdentity
from idhazh.contracts.item_health import ItemStage
from idhazh.contracts.ledger_index import CompactEntry, CompactIndex
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.publication_inventory import PublicationInventory
from idhazh.contracts.summary import Summary
from idhazh.contracts.visual_data import VisualData
from idhazh.contracts.visual_decision import PAYLOAD_SUFFIX, VisualDecision
from idhazh.ledger import paths
from idhazh.publication import record_files
from idhazh.render import asset_relpath
from idhazh.stages import common
from idhazh.stages.assemble import stage_assemble
from utilities import digest_assemble, digest_publish, publication_evidence
from utilities.publication_git import Repository
from utilities.publication_request import IntegrityError, PublicationRequest
from utilities.publish_to_repo import Status, publish
from utilities.push_retry import PushRetry


@pytest.mark.parametrize("empty_harvest", [False, True])
def test_fresh_base_regeneration_preserves_completed_raw_and_newer_inventory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    empty_harvest: bool,
) -> None:
    quiet_git(tmp_path, monkeypatch)
    seed = PublicationInventory(version=PublicationInventory.schema_version(), dates=[])
    origin, repo = an_origin(
        tmp_path,
        {
            "seed": "seed\n",
            digest_publish.INVENTORY: seed.to_json(),
        },
    )
    run_plan = plan()
    monkeypatch.setattr(common, "VAR_ROOT", repo / "backend" / "var" / "run")
    monkeypatch.setattr(common, "STATE_ROOT", repo / "state")
    monkeypatch.setattr(common, "PUBLIC_ROOT", repo / "frontend" / "public" / "digest")
    source = git(repo, "rev-parse", "HEAD").strip()
    identity = WriterIdentity(
        run_id=run_plan.run_id,
        attempt=1,
        job=ServerJob.PLAN,
        shard=0,
        producer="idhazh.stages.plan",
        git_sha=source,
    )
    ledger.persist(
        repo / "state",
        [run_plan],
        ledger=LedgerName.RUN_PLAN,
        covers=run_plan.date,
        identity=identity,
    )
    git(repo, "add", "state")
    git(repo, "commit", "--quiet", "-m", "completed plan")
    git(repo, "push", "--quiet", "origin", "HEAD:main")
    source = git(repo, "rev-parse", "HEAD").strip()
    items = common.VAR_ROOT / run_plan.date / "items"
    stage_visual_payloads(run_plan, items, text=FULL_TEXT)
    score_one_item(items, run_plan)
    first = run_plan.items[0]
    for model, stem, name, suffix in (
        (Article, "article", "ok", ".article.json"),
        (Summary, "summary", "titled", ".summary.json"),
        (EvalRow, "eval-row", "high", ".eval.json"),
    ):
        payload = model.read(CONTRACT_FIXTURES_DIR / stem / f"{name}.json").model_copy(
            update={"item_id": first.item_id, "url_key": first.url_key}
        )
        write(items / f"{first.item_id}{suffix}", payload.to_json())
    visual = VisualData.read(
        CONTRACT_FIXTURES_DIR / "visual-data/bars-from-the-committed-plan.json"
    ).model_copy(update={"item_id": first.item_id})
    decision = VisualDecision.read(
        CONTRACT_FIXTURES_DIR / "visual-decision/chart-rendered.json"
    ).model_copy(
        update={
            "item_id": first.item_id,
            "url_key": first.url_key,
            "data_path": asset_relpath(run_plan.date, first.item_id),
            "spec": visual.to_json(),
        }
    )
    write(items / f"{first.item_id}{PAYLOAD_SUFFIX}", decision.to_json())
    settings = config.load(CONFIG_DIR)
    summary_path = items / f"{first.item_id}.summary.json"
    summary = Summary.read(summary_path).model_copy(
        update={
            "title": REFILL_PUBLISHED.title,
            "summary": REFILL_PUBLISHED.summary,
            "output_digest": derive_output_digest(
                REFILL_PUBLISHED.summary, title=REFILL_PUBLISHED.title
            ),
        }
    )
    write(summary_path, summary.to_json())
    settings = dataclasses.replace(
        settings,
        app=settings.app.model_copy(
            update={
                "finetune": settings.app.finetune.model_copy(update={"corpus_rows": 2}),
            }
        ),
    )
    if empty_harvest:
        (items / f"{first.item_id}.eval.json").unlink()
    incoming = corpus.harvest_rows(
        corpus.scored_from_items(items),
        date=run_plan.date,
        prompt_config=settings.app.summarize,
        evaluation=settings.app.evaluation,
    )
    assert bool(incoming) is not empty_harvest
    older = [row_at("2026-01-01", "a"), row_at("2026-01-02", "b")]
    local_rows = corpus.roll(older, incoming, window=2)
    original_meta = corpus.census(
        local_rows,
        previous=corpus.read_meta(repo / "corpus"),
        prompt_digest="a" * 64,
    ).model_copy(update={"harvested_date": run_plan.date})
    with completed_writes.collect() as written:
        stage_assemble(run_plan, settings=settings, commit_sha=source, runner="fixture")
        corpus.write(repo / "corpus", local_rows, original_meta)
    hashes = {
        path.relative_to(repo).as_posix(): digest
        for path, digest in written.items()
        if path.is_relative_to(repo) and not path.is_relative_to(repo / "backend")
    }
    authority = digest_publish.permissions("assemble", date=run_plan.date)
    day = "frontend/public/digest/" + run_plan.date.replace("-", "/")
    mutable = (
        *(
            path
            for path in authority
            if path.startswith("frontend/") or path == "state/day-metrics"
        ),
        day,
        "corpus/corpus.jsonl",
        "corpus/corpus.meta.json",
    )
    request = PublicationRequest(
        identity.model_copy(update={"job": ServerJob.ASSEMBLE}),
        "assembled",
        source,
        authority,
        (),
        publication_evidence.confirmed(
            Repository(repo),
            hashes,
            source=source,
            permissions=authority,
            mutable=mutable,
        ),
        preparation_scopes=mutable,
    )
    request = dataclasses.replace(
        request,
        prepare=digest_assemble.preparation(
            repo,
            request,
            date=run_plan.date,
            settings=settings,
        ),
    )
    raw = {
        path: (repo / path).read_bytes()
        for path in request.writes
        if path.startswith("state/raw/") or path.startswith("state/digest-fragments/")
    }
    assert raw, "the producer wrote no completed immutable evidence"
    mover = tmp_path / "mover"
    git(tmp_path, "clone", "--quiet", str(origin), str(mover))
    write(mover / "frontend/public/other.json", '{"newer":true}\n')
    record_files(mover / "frontend" / "public", paths=("other.json",))
    asset = "frontend/public/" + asset_relpath(run_plan.date, first.item_id)
    raced = (json.dumps(json.loads((repo / asset).read_bytes()), indent=1) + "\n").encode()
    assert raced != (repo / asset).read_bytes()
    (mover / asset).parent.mkdir(parents=True, exist_ok=True)
    (mover / asset).write_bytes(raced)
    record_files(mover / "frontend/public", paths=(asset.removeprefix("frontend/public/"),))
    remote_rows = [older[0], row_at("2026-01-03", "c")]
    corpus.write(
        mover / "corpus",
        remote_rows,
        corpus.census(
            remote_rows, previous=corpus.read_meta(mover / "corpus"), prompt_digest="b" * 64
        ),
    )
    git(mover, "add", "frontend", "corpus")
    git(mover, "commit", "--quiet", "-m", "newer inventory")
    git(mover, "push", "--quiet", "origin", "HEAD:main")
    original_bytes = {path: (repo / path).read_bytes() for path in request.writes}
    observed = git(mover, "rev-parse", "HEAD").strip()
    completed_summary = summary_path.read_bytes()
    summary_path.write_bytes(b"{}\n")
    try:
        refusal = publish(request, repo=repo, retry=PushRetry({"default": 300}, 0.001, 0.001, 1))
        assert refusal.status is Status.PREPARATION_FAILURE
        assert refusal.push_count == 0
        assert git(origin, "rev-parse", "main").strip() == observed
        assert {path: (repo / path).read_bytes() for path in request.writes} == original_bytes
    finally:
        summary_path.write_bytes(completed_summary)
    # This fixture has no model weights: retries must use its completed fragment.
    monkeypatch.setattr(config, "REPO_ROOT", repo)
    result = publish(request, repo=repo, retry=PushRetry({"default": 300}, 0.001, 0.001, 1))
    assert result.status is Status.LANDED, result
    assert result.prepared
    manifest_text = on_origin(origin, f"{day}/run.json")
    assert manifest_text is not None
    from idhazh.cli import shard_count

    assert json.loads(manifest_text)["runs"][-1]["shards"] == shard_count(
        len(run_plan.items), run=settings.app.run
    )
    assert on_origin(origin, "frontend/public/other.json") == '{"newer":true}\n'
    for path, data in raw.items():
        entry = Repository(origin).entry("main", path)
        assert entry is not None
        assert Repository(origin).blob(entry.oid) == data
    entry = Repository(origin).entry("main", asset)
    assert entry is not None
    assert Repository(origin).blob(entry.oid) == raced
    expected = corpus.roll(remote_rows, incoming, window=2)
    assert corpus.read_rows(repo / "corpus") == expected
    corpus.refuse_a_miscounted_census(expected, corpus.read_meta(repo / "corpus"))
    for path in ("corpus/corpus.jsonl", "corpus/corpus.meta.json"):
        entry = Repository(origin).entry("main", path)
        assert entry is not None
        assert Repository(origin).blob(entry.oid) == (repo / path).read_bytes()


@pytest.mark.parametrize("staged", [False, True])
def test_published_build_inputs_refuse_foreign_bytes_before_import(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, staged: bool
) -> None:
    quiet_git(tmp_path, monkeypatch)
    inventory = PublicationInventory(version=PublicationInventory.schema_version(), dates=[])
    origin, repo = an_origin(tmp_path, {digest_publish.INVENTORY: inventory.to_json()})
    source = git(repo, "rev-parse", "HEAD").strip()
    write(repo / "frontend/public/other.json", '{"published":true}\n')
    record_files(repo / "frontend/public", paths=("other.json",))
    git(repo, "add", "frontend/public")
    git(repo, "commit", "--quiet", "-m", "inventory input")
    git(repo, "push", "--quiet", "origin", "HEAD:main")
    tip = git(repo, "rev-parse", "HEAD").strip()
    reader = tmp_path / "reader"
    git(tmp_path, "clone", "--quiet", str(origin), str(reader))
    git(reader, "checkout", "--quiet", source)
    write(reader / "frontend/public/other.json", "foreign local bytes\n")
    if staged:
        git(reader, "add", "frontend/public/other.json")
    index = (reader / ".git/index").read_bytes()
    previous_inventory = (reader / digest_publish.INVENTORY).read_bytes()
    with pytest.raises(IntegrityError, match="foreign"):
        digest_publish.published_inputs(reader, tip)
    assert (reader / "frontend/public/other.json").read_bytes() == b"foreign local bytes\n"
    assert (reader / digest_publish.INVENTORY).read_bytes() == previous_inventory
    assert (reader / ".git/index").read_bytes() == index


@pytest.mark.parametrize("missing_head", [False, True])
def test_named_indexes_import_old_permanent_heads_without_scanning_raw_archive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, missing_head: bool
) -> None:
    quiet_git(tmp_path, monkeypatch)
    which = LedgerName.FEED_RETIREMENTS
    index_path = paths.compact_index_path(Path("state"), which, Period.YEARLY).as_posix()
    compact_path = paths.compact_path(Path("state"), which, Period.YEARLY, "2023").as_posix()
    index = CompactIndex(
        version=CompactIndex.schema_version(),
        ledger=which,
        period=Period.YEARLY,
        entries=[CompactEntry(covers="2023", rows=1, bytes=5)],
    )
    seed = {index_path: index.to_json(), "state/raw/feed-retirements/1990/01/01/old.json": "{}\n"}
    for period in (Period.DAILY, Period.MONTHLY):
        seed[paths.compact_index_path(Path("state"), which, period).as_posix()] = CompactIndex(
            version=CompactIndex.schema_version(), ledger=which, period=period, entries=[]
        ).to_json()
    if not missing_head:
        seed[compact_path] = "head\n"
    _, repo = an_origin(tmp_path, seed)
    tip = git(repo, "rev-parse", "HEAD").strip()
    if missing_head:
        with pytest.raises(IntegrityError, match="packed input is absent"):
            digest_assemble.resolved_inputs(
                Repository(repo), tip, date="2026-10-09", settings=config.load(CONFIG_DIR)
            )
        return
    inputs = digest_assemble.resolved_inputs(
        Repository(repo), tip, date="2026-10-09", settings=config.load(CONFIG_DIR)
    )
    assert compact_path in inputs
    assert not any(path.startswith("state/raw/feed-retirements/1990") for path in inputs)
    assert "state/raw/feed-retirements" not in inputs


def test_inputs_include_the_full_seen_and_published_consumer_windows() -> None:
    settings = config.load(CONFIG_DIR)
    settings.app.collect.seen_window_days = 900
    settings.app.collect.published_window_days = 1000
    through = "2026-10-09"
    inputs = digest_assemble.input_paths(date=through, settings=settings)

    for which, window in ((LedgerName.SEEN, 900), (LedgerName.PUBLISHED, 1000)):
        first = (date.fromisoformat(through) - timedelta(days=window)).isoformat()
        expected = (ledger.raw_root(Path("state"), which) / first.replace("-", "/")).as_posix()
        assert expected in inputs, "the reader includes the boundary day"
        excluded = (date.fromisoformat(first) - timedelta(days=1)).isoformat()
        outside = (ledger.raw_root(Path("state"), which) / excluded.replace("-", "/")).as_posix()
        assert outside not in inputs


@pytest.mark.parametrize("raw_only", [False, True], ids=["packed-and-raw", "raw-only"])
def test_unbounded_published_inputs_use_the_declared_start_and_all_index_heads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, raw_only: bool
) -> None:
    quiet_git(tmp_path, monkeypatch)
    which = LedgerName.PUBLISHED
    gardener = json.loads((CONFIG_DIR / "idhazh_gardener.json").read_text(encoding="utf-8"))
    gardener["first_ledger_year"] = "2023"
    seed = {
        "config/idhazh_gardener.json": json.dumps(gardener),
        "state/raw/published/2023/01/01/older-than-the-index.json": "old raw\n",
        "state/raw/published/2022/01/01/foreign-archive.json": "outside the declared start\n",
    }
    heads: set[str] = set()
    if not raw_only:
        for period, covers in (
            (Period.DAILY, "2024-02-01"),
            (Period.MONTHLY, "2024-03"),
            (Period.YEARLY, "2024"),
        ):
            head = paths.compact_path(Path("state"), which, period, covers).as_posix()
            heads.add(head)
            seed[head] = "head\n"
            seed[paths.compact_index_path(Path("state"), which, period).as_posix()] = CompactIndex(
                version=CompactIndex.schema_version(),
                ledger=which,
                period=period,
                entries=[CompactEntry(covers=covers, rows=1, bytes=5)],
            ).to_json()
    _, repo = an_origin(tmp_path, seed)
    settings = config.load(CONFIG_DIR)
    settings.app.collect.published_window_days = -1
    tip = git(repo, "rev-parse", "HEAD").strip()

    inputs = digest_assemble.resolved_inputs(
        Repository(repo), tip, date="2026-10-09", settings=settings
    )

    assert "state/raw/published/2023/01/01" in inputs
    assert not any(path.startswith("state/raw/published/2022") for path in inputs)
    assert heads <= set(inputs)
    assert "state/raw/published" not in inputs


@pytest.mark.parametrize("foreign", [False, True], ids=["one-published-snapshot", "foreign-state"])
def test_published_build_imports_raw_state_and_compact_heads_without_foreign_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, foreign: bool
) -> None:
    quiet_git(tmp_path, monkeypatch)
    which = LedgerName.HOST_FINGERPRINT
    day = "2026-10-09"
    head = paths.compact_path(Path("state"), which, Period.DAILY, day).as_posix()
    raw_folder = ledger.raw_root(Path("state"), which) / day.replace("-", "/")
    old_raw, new_raw = ((raw_folder / name).as_posix() for name in ("old.json", "new.json"))
    seed = {
        digest_publish.INVENTORY: PublicationInventory(
            version=PublicationInventory.schema_version(), dates=[]
        ).to_json(),
        head: "old head\n",
        old_raw: "old raw\n",
    }
    for period in Period:
        seed[paths.compact_index_path(Path("state"), which, period).as_posix()] = CompactIndex(
            version=CompactIndex.schema_version(),
            ledger=which,
            period=period,
            entries=[CompactEntry(covers=day, rows=1, bytes=9)] if period is Period.DAILY else [],
        ).to_json()
    origin, repo = an_origin(tmp_path, seed)
    mover = tmp_path / "mover"
    git(tmp_path, "clone", "--quiet", str(origin), str(mover))
    write(mover / head, "new head\n")
    (mover / old_raw).unlink()
    write(mover / new_raw, "new raw\n")
    write(mover / "frontend/public/other.json", '{"sameTip":true}\n')
    record_files(mover / "frontend/public", paths=("other.json",))
    git(mover, "add", "--", "state", "frontend")
    git(mover, "commit", "--quiet", "-m", "published state and public projections")
    git(mover, "push", "--quiet", "origin", "HEAD:main")
    tip = git(mover, "rev-parse", "HEAD").strip()
    git(repo, "fetch", "--quiet", "origin", "main")
    before = git(repo, "rev-parse", "HEAD"), (repo / ".git/index").read_bytes()
    if foreign:
        write(repo / head, "foreign state\n")
        with pytest.raises(IntegrityError, match="foreign"):
            digest_publish.published_inputs(repo, tip, date=day, settings=config.load(CONFIG_DIR))
        assert (repo / head).read_text() == "foreign state\n"
        assert not (repo / "frontend/public/other.json").exists()
    else:
        digest_publish.published_inputs(repo, tip, date=day, settings=config.load(CONFIG_DIR))
        assert (repo / head).read_text() == "new head\n"
        assert (repo / new_raw).read_text() == "new raw\n"
        assert not (repo / old_raw).exists()
        assert (repo / "frontend/public/other.json").read_text() == '{"sameTip":true}\n'
    assert before == (git(repo, "rev-parse", "HEAD"), (repo / ".git/index").read_bytes())


def test_work_adapter_lands_exact_completed_raw_not_pre_staged_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    quiet_git(tmp_path, monkeypatch)
    retry = {
        "deadline_seconds": {"default": 300},
        "base_step_seconds": 0.001,
        "ceiling_seconds": 0.001,
        "ceiling_after": 1,
    }
    origin, repo = an_origin(
        tmp_path, {"seed": "seed\n", "config/push-retry.json": json.dumps(retry) + "\n"}
    )
    source = git(repo, "rev-parse", "HEAD").strip()
    identity = WriterIdentity(
        run_id="2026-10-09-123",
        attempt=1,
        job=ServerJob.WORK,
        shard=0,
        producer="utilities.digest_publish",
        git_sha=source,
    )
    with completed_writes.collect() as evidence:
        ledger.persist(
            repo / "state",
            [health_row(day="2026-10-09", run=123, number=1, stage=ItemStage.PUBLISH)],
            ledger=LedgerName.ITEM_HEALTH,
            covers="2026-10-09",
            identity=identity,
        )
    publication_evidence.save(repo, identity, "record", evidence)
    write(repo / "state/foreign-staged.json", "foreign staged bytes\n")
    git(repo, "add", "state/foreign-staged.json")
    index = (repo / ".git/index").read_bytes()
    result = digest_publish.land(repo=repo, identity=identity, date="2026-10-09")
    assert result.status is Status.LANDED, result
    assert git(repo, "rev-parse", "HEAD").strip() == source
    assert (repo / ".git/index").read_bytes() == index
    assert Repository(origin).entry("main", "state/foreign-staged.json") is None
    for target in evidence:
        entry = Repository(origin).entry("main", target.relative_to(repo).as_posix())
        assert entry is not None and entry.mode == "100644"
        assert Repository(origin).blob(entry.oid) == target.read_bytes()


def test_plan_workflow_call_parses_and_bad_retry_config_stops_before_git_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from ._harness import _commit_call, _substitute

    quiet_git(tmp_path, monkeypatch)
    origin, repo = an_origin(tmp_path, {"seed": "seed\n", "config/push-retry.json": "{}\n"})
    monkeypatch.chdir(repo)
    source = git(repo, "rev-parse", "HEAD").strip()
    index = (repo / ".git/index").read_bytes()
    args, _ = _commit_call("plan")
    argv = [_substitute(value) for value in args]
    assert digest_publish.main(argv) == 2
    assert "deadline_seconds" in capsys.readouterr().err
    assert git(repo, "rev-parse", "HEAD").strip() == source
    assert git(origin, "rev-parse", "main").strip() == source
    assert (repo / ".git/index").read_bytes() == index
    write(repo / "config/push-retry.json", (CONFIG_DIR / "push-retry.json").read_text())
    assert digest_publish.main(argv) == 0
