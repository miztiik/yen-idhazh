"""Does a chart a work shard drew reach the published day when its file stays on the shard's runner?"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest
from gardener._garden import an_origin, git, quiet_git
from pytest import MonkeyPatch
from support.paths import CONFIG_DIR, read_text
from support.server import RecordedEndpoint
from test_classify import a_reply, named, reading

from idhazh import assemble, completed_writes, config, ledger, run_context
from idhazh.contracts.article import Article
from idhazh.contracts.base import ServerJob
from idhazh.contracts.derived import DerivedFunction
from idhazh.contracts.digest_day import DigestDay
from idhazh.contracts.feed_health import FetchOutcome
from idhazh.contracts.file_envelope import WriterIdentity
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.run_manifest import RunManifest
from idhazh.contracts.visual import VisualType
from idhazh.contracts.visual_data import VisualData
from idhazh.contracts.visual_decision import PAYLOAD_SUFFIX, VisualDecision, VisualKind
from idhazh.contracts.visual_telemetry import VisualAttemptRow
from idhazh.fetch import FetchResult
from idhazh.ledger import staging
from idhazh.publication import read_inventory
from idhazh.render.write import asset_relpath
from idhazh.stages import common
from idhazh.stages.work import stage_work
from utilities import digest_publish, publication_evidence
from utilities.publication_git import Repository
from utilities.publish_to_repo import Status

from ._builders import (
    DRAWS_SUMMARIZE_AND_PLAN,
    _work_stage,
    assert_planning_readings,
    assert_reader_accepts,
    drawable_article_fetch,
    finding_the_wind_countries,
    plan,
    publish_worker_items,
)

pytestmark = pytest.mark.visual


def test_assemble_publishes_a_chart_from_its_decision_alone(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """Work lands the recorded save; only the item handoff reaches fresh assembly."""
    quiet_git(tmp_path, monkeypatch)
    origin, worker = an_origin(
        tmp_path, {"config/push-retry.json": read_text(CONFIG_DIR / "push-retry.json")}
    )
    run_plan = plan(item_count=1)
    identity = WriterIdentity(
        run_id=run_plan.run_id,
        attempt=run_context.run_attempt(),
        job=ServerJob.WORK,
        shard=0,
        producer=digest_publish.__name__,
        git_sha=git(worker, "rev-parse", "HEAD").strip(),
    )
    worker_public = worker / "frontend" / "public"
    worker_var = worker / "backend" / "var" / "run"
    monkeypatch.setattr(common, "PUBLIC_ROOT", worker_public / "digest")
    monkeypatch.setattr(common, "VAR_ROOT", worker_var)
    monkeypatch.setattr(common, "STATE_ROOT", worker / "state")

    response = json.loads(DRAWS_SUMMARIZE_AND_PLAN.read_bytes())
    message = response["choices"][0]["message"]
    content = json.loads(message["content"])
    content["visual"]["axis_titles"] = {"x": "Capacity approved", "y": "Award recipients"}
    for row in content["visual"]["rows"]:
        row["series"] = "Offshore awards"
    message["content"] = json.dumps(content)
    with (
        completed_writes.collect() as writes,
        finding_the_wind_countries(config.load(CONFIG_DIR)) as settings,
        RecordedEndpoint(200, json.dumps(response).encode("utf-8")) as server,
    ):
        stage_work(
            run_plan,
            settings=settings,
            scorer=None,
            fetcher=drawable_article_fetch,
            model_endpoint=server.endpoint,
            commit_sha=identity.git_sha,
        )
    publication_evidence.save(worker, identity, "work", writes)
    result = digest_publish.land(repo=worker, identity=identity, date=run_plan.date)
    assert result.status is Status.LANDED, result

    items = worker_var / run_plan.date / "items"
    item_id = run_plan.items[0].item_id
    decision = VisualDecision.read(items / f"{item_id}{PAYLOAD_SUFFIX}")
    relpath = asset_relpath(run_plan.date, item_id)
    assert decision.kind is VisualKind.CHART
    assert decision.data_path == relpath
    assert decision.spec is not None
    chart_bytes = decision.spec.encode("utf-8")
    assert (items.parent / "chart-scratch" / relpath).read_bytes() == chart_bytes
    assert not (items / relpath).exists()
    assert not (worker_public / relpath).exists()

    receipt = publication_evidence.read(worker, identity, ("work",))
    chart_path = f"frontend/public/{relpath}"
    assert chart_path not in receipt
    remote = Repository(origin, git_dir=origin)
    assert remote.entry("main", chart_path) is None
    attempt_root = staging.staged_path(LedgerName.VISUAL_DESIGN_ATTEMPTS)
    (attempt_path,) = [path for path in receipt if path.startswith(f"{attempt_root}/")]
    attempt_entry = remote.entry("main", attempt_path)
    assert attempt_entry is not None
    attempt_file = worker / attempt_path
    assert remote.blob(attempt_entry.oid) == attempt_file.read_bytes()
    (attempt,) = ledger.load([attempt_file], model=VisualAttemptRow)
    assert (attempt.run_id, attempt.item_id, attempt.visual_id) == (
        run_plan.run_id, item_id, decision.visual_id,
    )
    assert attempt.planned_type is attempt.rendered_type is VisualType.BAR

    compiled = VisualData.from_json(decision.spec)
    assert_planning_readings(
        server,
        ["1200 MW", "900 MW", "640 MW", "410 MW"],
    )
    marks = {mark.mark_id: mark for mark in compiled.marks}
    assert compiled.axis_titles and compiled.axis_titles.x == "Capacity approved"
    assert compiled.axis_titles.y == "Award recipients"
    assert {marks[name].text for name in compiled.encoding.series} == {"Offshore awards"}
    assert all(
        marks[name].label_source == "model" and marks[name].element_id is None
        for name in [*compiled.encoding.category, *compiled.encoding.series]
    )
    assert [marks[name].text for name in compiled.encoding.category] == [
        "Denmark", "Germany", "Poland", "Ireland"
    ]
    assert [Decimal(str(marks[name].value)) for name in compiled.encoding.quantity] == [
        Decimal(1200), Decimal(900), Decimal(640), Decimal(410)
    ]
    assert compiled.emphasized_mark_id is None

    publisher = tmp_path / "publisher"
    publish_worker_items(run_plan, items, publisher, monkeypatch)

    public = publisher / "public"
    day = DigestDay.from_json(
        read_text(assemble.day_dir(public / "digest", run_plan.date) / "digest.json")
    )
    named = {item.visual.data_path for item in day.items if item.visual is not None}
    inventoried = {entry.path for entry in read_inventory(public).entries}
    assert relpath in named, f"the published day does not name {relpath}"
    assert (public / relpath).read_bytes() == chart_bytes
    assert VisualData.read(public / relpath) == compiled
    assert relpath in inventoried, f"the inventory does not count {relpath}"
    manifest = RunManifest.read(assemble.day_dir(public / "digest", run_plan.date) / "run.json")
    assert [(run.run_id, run.items_decided) for run in manifest.runs] == [(attempt.run_id, 1)]
    assert_reader_accepts(public / relpath, item_id=item_id)


def test_later_duplicate_selected_as_negative_survives_fresh_publisher_handoff(
    tmp_path: Path, monkeypatch: MonkeyPatch,
) -> None:
    """Only serialized work outputs carry the exact selected occurrence into publication."""
    text = (
        "Alder gained 20 MW of generating capacity during the reporting period. "
        "Birch lost 20 MW of generating capacity during the same reporting period. "
        "Cedar gained 30 MW of generating capacity over that reporting period. "
        "The regional authority said the figures measure net changes in installed capacity, "
        "rather than electricity supplied to customers or the cost of each project. "
        "The authority published its comparison after reviewing the operating records from "
        "all participating sites. Operators said that the changes reflect the closure of "
        "older units and the commissioning of new equipment. The report did not compare "
        "auction prices or forecast future construction."
    )
    page = (
        "<html><head><title>Regional generating capacity changes</title></head>"
        f"<body><article><h1>Regional generating capacity changes</h1><p>{text}</p>"
        "</article></body></html>"
    ).encode()

    def fetched(_url: str) -> FetchResult:
        return FetchResult(FetchOutcome.OK, status=200, body=page)

    content = a_reply(
        title="Net capacity change",
        comparison_basis="Net installed generating capacity change over the reporting period",
        rows=[
            {"label": "Birch", "reading": reading("q2", "negative_magnitude")},
            named("Cedar", "q3"),
        ],
    )
    response = json.dumps({"content": content, "stop": True}).encode()
    run_plan, items, server = _work_stage(
        tmp_path / "worker", monkeypatch, run_plan=plan(item_count=1),
        fetcher=fetched, replies=(response,),
    )
    item_id = run_plan.items[0].item_id
    article = Article.read(items / f"{item_id}.article.json")
    source = article.text or ""
    first = source.index("20 MW")
    later = source.index("20 MW", first + 1)
    selected_id = f"quantity-{later}-{later + len('20 MW')}"
    excluded_id = f"quantity-{first}-{first + len('20 MW')}"
    decision = VisualDecision.read(items / f"{item_id}{PAYLOAD_SUFFIX}")
    assert decision.kind is VisualKind.CHART, decision
    assert decision.spec is not None
    assert decision.data_path is not None
    compiled = VisualData.from_json(decision.spec)
    by_id = {mark.mark_id: mark for mark in compiled.marks}
    signed, positive = [by_id[mark] for mark in compiled.encoding.quantity]
    assert signed.value == "-20"
    assert signed.source_text == source[later:later + len("20 MW")] == "20 MW"
    assert signed.element_id is None and signed.derived is not None
    assert signed.derived.function is DerivedFunction.NEGATIVE_MAGNITUDE
    assert signed.derived.inputs == [selected_id]
    assert excluded_id not in signed.derived.inputs
    assert signed.derived.source_unit is None and signed.derived.unit_table_version is None
    assert positive.value == "30"
    assert server.served == 1
    assert "q2" in server.sent[0]["json_schema"]["$defs"]["QuantityEvidenceId"]["enum"]

    publisher = tmp_path / "publisher"
    day = publish_worker_items(run_plan, items, publisher, monkeypatch)
    published_item = next(item for item in day.items if item.visual is not None)
    assert published_item.visual is not None
    assert published_item.visual.data_path is not None
    published = publisher / "public" / published_item.visual.data_path
    assert published.read_text(encoding="utf-8") == decision.spec
    assert VisualData.read(published) == compiled
    published_marks = {mark.mark_id: mark for mark in VisualData.read(published).marks}
    persisted = published_marks[compiled.encoding.quantity[0]]
    assert persisted.source_text == "20 MW"
    assert persisted.derived is not None
    assert persisted.derived.function is DerivedFunction.NEGATIVE_MAGNITUDE
    assert persisted.derived.inputs == [selected_id]
    assert_reader_accepts(published, item_id=item_id)
