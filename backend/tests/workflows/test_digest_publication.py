"""Does digest publication preserve immutable inputs and stop invalid work?"""

import dataclasses
import json
from datetime import date, timedelta
from pathlib import Path

import pytest
from gardener._garden import an_origin, git, quiet_git, write
from retention._trees import health_row
from support.paths import CONFIG_DIR

from idhazh import assemble, completed_writes, config, ledger, publication, rank
from idhazh.contracts.article import Article, ArticleStatus
from idhazh.contracts.base import ServerJob, derive_output_digest, derive_url_key
from idhazh.contracts.digest_day import DigestDay
from idhazh.contracts.digest_run_fragment import DigestRunFragment
from idhazh.contracts.file_envelope import Period, WriterIdentity
from idhazh.contracts.item_health import ItemStage
from idhazh.contracts.ledger_index import CompactEntry, CompactIndex
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.publication_inventory import PublicationInventory
from idhazh.contracts.run_plan import PlannedItem, RunPlan
from idhazh.contracts.summary import Summary, SummaryStatus
from idhazh.contracts.visual import EncodingRole
from idhazh.contracts.visual_data import RENDERER_VERSION, VisualData
from idhazh.contracts.visual_decision import PAYLOAD_SUFFIX, VisualDecision, VisualKind, VisualState
from idhazh.ledger import paths
from idhazh.render.write import asset_relpath
from idhazh.stages import common
from idhazh.stages.assemble import stage_assemble
from utilities import digest_assemble, digest_publish, publication_evidence
from utilities.publication_git import Repository
from utilities.publication_request import IntegrityError, PublicationRequest, Write
from utilities.publish_to_repo import Status, _verify_preparation


def a_repository(root: Path, files: dict[str, str]) -> tuple[Path, str]:
    repo = root / "checkout"
    repo.mkdir()
    git(repo, "init", "--quiet", "-b", "main")
    for name, text in files.items():
        write(repo / name, text)
    git(repo, "add", "--all")
    git(repo, "commit", "--quiet", "-m", "seed")
    return repo, git(repo, "rev-parse", "HEAD").strip()


def test_preparation_cannot_change_immutable_counts_inside_its_scope() -> None:
    source, fresh = "a" * 40, "b" * 40
    scope = digest_assemble.count_scope("2026-08-21")
    path = f"{scope}/completed.parquet"
    identity = WriterIdentity(
        run_id="2026-08-21-1", attempt=1, job=ServerJob.ASSEMBLE, shard=0,
        producer="tests.publisher", git_sha=source,
    )
    original = PublicationRequest(
        identity, "assembled", source, (scope,), (),
        {path: Write("c" * 64, None, immutable=True)},
        preparation_scopes=(scope,),
    )
    changed = dataclasses.replace(
        original, source_tip=fresh, writes={path: Write("d" * 64, None, immutable=True)}
    )
    with pytest.raises(IntegrityError, match="changed completed artifact"):
        _verify_preparation(original, changed, fresh)


def test_native_band_inputs_include_both_spans_without_retired_projection_roots() -> None:
    settings = config.load(CONFIG_DIR)
    through = "2026-10-09"
    widest = max(settings.appearance.console.window_presets)
    first = (date.fromisoformat(through) - timedelta(days=2 * widest - 1)).isoformat()
    inputs = digest_assemble.input_paths(date=through, settings=settings)
    day = first.replace("-", "/")
    assert f"frontend/public/digest/{day}/run.json" in inputs
    assert f"state/day-metrics/{day}.json" in inputs
    assert f"frontend/public/digest/{day}/digest.json" not in inputs
    assert not any(
        path.startswith(f"frontend/public/{root}/")
        for path in inputs for root in ("machine", "run-days", "day-metrics")
    )


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
    gardener = json.loads((CONFIG_DIR / "gardener/config/idhazh_gardener.json").read_text(encoding="utf-8"))
    gardener["first_ledger_year"] = "2023"
    seed = {
        "config/gardener/config/idhazh_gardener.json": json.dumps(gardener),
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
            index = CompactIndex.from_period_entries(
                ledger=which,
                period=period,
                entries=[CompactEntry(covers=covers, rows=1, bytes=5)],
            )
            seed[paths.compact_index_path(Path("state"), which, period).as_posix()] = index.to_json()
    repo, tip = a_repository(tmp_path, seed)
    settings = config.load(CONFIG_DIR)
    settings.app.collect.published_window_days = -1

    inputs = digest_assemble.resolved_inputs(
        Repository(repo), tip, date="2026-10-09", settings=settings
    )

    assert "state/raw/published/2023/01/01" in inputs
    assert not any(path.startswith("state/raw/published/2022") for path in inputs)
    assert heads <= set(inputs)
    assert "state/raw/published" not in inputs


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
    remote = Repository(origin, git_dir=origin)
    assert remote.entry("main", "state/foreign-staged.json") is None
    for target in evidence:
        entry = remote.entry("main", target.relative_to(repo).as_posix())
        assert entry is not None and entry.mode == "100644"
        assert remote.blob(entry.oid) == target.read_bytes()


def save_chart_worker_output(
    plan: RunPlan, items: Path, title: str
) -> tuple[PlannedItem, VisualDecision]:
    url = f"https://example.test/{title.lower().replace(' ', '-')}"
    url_key = derive_url_key(url)
    vertical = "energy"
    item_id = rank.item_id(vertical, url_key)
    identity = {
        "item_id": item_id, "url_key": url_key, "source_url": url, "canonical_url": url,
        "source_id": "example", "tier": 1, "vertical": vertical, "rank_score": 1.0,
    }
    article = Article.model_validate(
        identity | {
            "version": Article.schema_version(), "text": "The plant generated 10 MW.",
            "status": ArticleStatus.OK, "fetched_at": plan.generated_at,
            "extractor_version": "test", "sanitizer_version": "test",
        }
    )
    summary = Summary(
        version=Summary.schema_version(), item_id=item_id, url_key=url_key, title=title,
        summary=article.text, output_digest=derive_output_digest(article.text, title=title),
        model_id="test-model", generated_at=plan.generated_at, status=SummaryStatus.OK,
    )
    mark = {"unit": None, "source_text": None, "derived": None}
    chart = VisualData.model_validate({
        "version": VisualData.schema_version(), "item_id": item_id, "type": "bar",
        "renderer_version": RENDERER_VERSION, "declared_whole": None,
        "declared_whole_element_id": None, "title": title, "caption": None,
        "emphasized_mark_id": "m2",
        "marks": [
            mark | {"mark_id": "m1", "text": "Plant", "value": None, "element_id": "entity-4-9"},
            mark | {"mark_id": "m2", "text": None, "value": "10", "element_id": "quantity-20-25"},
        ],
        "encoding": {role.value: [] for role in EncodingRole}
        | {"category": ["m1"], "quantity": ["m2"]},
    })
    decision = VisualDecision(
        version=VisualDecision.schema_version(), item_id=item_id, url_key=url_key,
        kind=VisualKind.CHART, visual_state=VisualState.RENDERED, spec=chart.to_json(),
        data_path=asset_relpath(plan.date, item_id), model_id=summary.model_id,
        decided_at=plan.generated_at,
    )
    write(items / f"{item_id}.article.json", article.to_json())
    write(items / f"{item_id}.summary.json", summary.to_json())
    write(items / f"{item_id}{PAYLOAD_SUFFIX}", decision.to_json())
    return PlannedItem.model_validate(identity), decision


def test_fresh_main_rebuild_publishes_only_charts_the_day_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    quiet_git(tmp_path, monkeypatch)
    origin, repo = an_origin(tmp_path, {
        "config/push-retry.json": (CONFIG_DIR / "push-retry.json").read_text(encoding="utf-8"),
        "frontend/public/publication.json": PublicationInventory(
            version=PublicationInventory.schema_version(), dates=[]
        ).to_json(),
    })
    settings = config.load(CONFIG_DIR)
    monkeypatch.setattr(config, "REPO_ROOT", repo)
    monkeypatch.setattr(common, "STATE_ROOT", repo / "state")
    monkeypatch.setattr(common, "PUBLIC_ROOT", repo / "frontend" / "public" / "digest")
    monkeypatch.setattr(common, "VAR_ROOT", repo / "backend" / "var" / "run")
    covers = "2026-10-09"
    run = RunPlan(
        version=RunPlan.schema_version(), date=covers, run_id=f"{covers}-2",
        generated_at=f"{covers}T03:00:00Z", shards=1,
    )
    items = common.VAR_ROOT / covers / "items"
    duplicate, unused = save_chart_worker_output(run, items, "Earlier chartless story")
    retained, drawn = save_chart_worker_output(run, items, "Earlier charted story")
    added, incoming = save_chart_worker_output(run, items, "New story")
    run.items = [duplicate, retained, added]
    identity = WriterIdentity(
        run_id=run.run_id, attempt=1, job=ServerJob.ASSEMBLE, shard=0,
        producer="idhazh.stages.assemble", git_sha=git(repo, "rev-parse", "HEAD").strip(),
    )
    with completed_writes.collect() as evidence:
        initial = stage_assemble(run, settings=settings, commit_sha=identity.git_sha, writer_identity=identity)
    publication_evidence.save(repo, identity, "assemble", evidence)
    assert unused.data_path is not None and drawn.data_path is not None and incoming.data_path is not None
    assert drawn.spec is not None and incoming.spec is not None
    assert (common.PUBLIC_ROOT.parent / unused.data_path) in evidence

    rival = tmp_path / "rival"
    git(tmp_path, "clone", "--quiet", str(origin), str(rival))
    by_id = {item.item_id: item for item in initial.items}
    earlier = DigestRunFragment(
        version=DigestRunFragment.schema_version(), date=covers, run_id=f"{covers}-1",
        completed_at=f"{covers}T02:00:00Z", items_planned=2, verticals=[],
        items=[by_id[duplicate.item_id].model_copy(update={"visual": None}), by_id[retained.item_id]],
    )
    public = rival / "frontend" / "public"
    prior_day = assemble.assemble_day(
        [earlier], taxonomy=settings.taxonomy, retention_window_months=settings.app.retention.image_months
    )
    digest_path = f"digest/{covers.replace('-', '/')}/digest.json"
    write(public / digest_path, prior_day.to_json())
    write(assemble.fragment_path(rival / "state", date=covers, run_id=earlier.run_id), earlier.to_json())
    saved_chart = VisualData.from_json(drawn.spec).model_copy(update={"title": "Published chart"}).to_json()
    write(public / drawn.data_path, saved_chart)
    publication.record_day(public, prior_day)
    git(rival, "add", "frontend", "state")
    git(rival, "commit", "--quiet", "-m", "publish earlier run")
    git(rival, "push", "--quiet", "origin", "main")

    result = digest_publish.land(repo=repo, identity=identity, date=covers, source_plan=run)
    assert result.status is Status.LANDED and result.prepared, result
    remote = Repository(origin, git_dir=origin)

    def committed(path: str) -> bytes:
        entry = remote.entry("main", f"frontend/public/{path}")
        assert entry is not None, path
        return remote.blob(entry.oid)

    digest = DigestDay.model_validate_json(committed(digest_path))
    assert next(item for item in digest.items if item.item_id == duplicate.item_id).visual is None
    assert remote.entry("main", f"frontend/public/{unused.data_path}") is None
    inventory = PublicationInventory.model_validate_json(committed("publication.json"))
    names = {entry.path for entry in inventory.entries}
    assert unused.data_path not in names
    assert {drawn.data_path, incoming.data_path} <= names
    assert committed(drawn.data_path) == saved_chart.encode()
    assert committed(incoming.data_path) == incoming.spec.encode()
