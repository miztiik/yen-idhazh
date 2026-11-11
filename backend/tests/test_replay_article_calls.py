"""Do retained native Articles produce fresh, isolated products through the real call pair?"""

from __future__ import annotations

import io
import json
import logging
import zipfile
from collections import Counter
from dataclasses import replace
from pathlib import Path

import pytest
from pipeline._builders import (
    DRAWS_LABEL,
    DRAWS_SUMMARIZE_AND_PLAN,
    declining_replies,
    drawable_article_fetch,
    plan,
    summary,
    whowhat_replies,
)
from support.paths import CONFIG_DIR
from support.server import RecordedEndpoint

from idhazh import config, extract, ledger
from idhazh.contracts.article import Article
from idhazh.contracts.base import ServerJob
from idhazh.contracts.file_envelope import WriterIdentity
from idhazh.contracts.fingerprint import PipelineInputs
from idhazh.contracts.item_health import FailureCode, ItemHealthRow
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.run_plan import RunPlan
from idhazh.contracts.summary import Summary, SummaryStatus
from idhazh.contracts.visual_decision import (
    PAYLOAD_SUFFIX,
    NoneReason,
    VisualDecision,
    VisualKind,
)
from idhazh.ledger.persist import read_registered_envelope
from idhazh.llm.server import window
from idhazh.stages import common
from idhazh.telemetry.record import HEALTH_SUFFIX
from utilities import replay_article_calls as replay
from utilities.digest_recovery_download import SourceRun
from utilities.publication_request import IntegrityError

pytestmark = [pytest.mark.workflow, pytest.mark.visual]


def zipped(files: dict[str, bytes]) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        for name, payload in files.items():
            archive.writestr(name, payload)
    return stream.getvalue()


def retained(
    root: Path,
) -> tuple[RunPlan, SourceRun, dict[str, bytes], tuple[Article, ...]]:
    saved = plan(item_count=2)
    counts = Counter(item.vertical for item in saved.items)
    saved = RunPlan.model_validate(saved.model_dump() | {
        "shards": 1,
        "verticals": [
            vertical.model_dump() | {"planned": counts[vertical.id]}
            for vertical in saved.verticals
        ],
    })
    knobs = config.load(CONFIG_DIR)
    articles = tuple(
        extract.to_article(
            item,
            drawable_article_fetch(str(item.canonical_url)),
            config=knobs.app.extract,
            fetched_at=saved.generated_at,
        )
        for item in saved.items
    )
    second_text = f"{articles[1].text} This update carries no additional figures."
    articles = (
        articles[0],
        Article.model_validate(articles[1].model_dump() | {
            "text": second_text,
            "word_count": len(second_text.split()),
            "source_word_count": len(second_text.split()),
        }),
    )
    writer = WriterIdentity(
        run_id=saved.run_id, attempt=1, job=ServerJob.PLAN, shard=0,
        producer="stages.plan", git_sha="a" * 40,
    )
    paths = ledger.persist(
        root / "source-state", [saved], ledger=LedgerName.RUN_PLAN,
        covers=saved.date, identity=writer,
    )
    archives = {
        "plan": zipped({path.name: path.read_bytes() for path in paths}),
        "items-0": zipped({
            **{f"{article.item_id}.article.json": article.to_json().encode()
               for article in articles},
            f"{saved.items[0].item_id}.summary.json": summary().to_json().encode(),
        }),
    }
    source = SourceRun(
        id=1, run_attempt=1, head_sha=writer.git_sha,
        path=".github/workflows/digest.yml", status="completed", conclusion="success",
        run_started_at=saved.generated_at,
    )
    return saved, source, archives, articles


def prepared(
    root: Path, source: SourceRun, archives: dict[str, bytes], item_ids: tuple[str, ...],
) -> tuple[RunPlan, tuple[Article, ...], str]:
    _, plan_file = replay.prepare_inputs(
        root, source=source, archives=archives, failed_shards=frozenset(), item_ids=item_ids,
    )
    saved, articles = replay.load_inputs(
        root, plan_file=plan_file, execution=str(source.id), attempt=source.run_attempt,
        commit=source.head_sha, item_ids=item_ids,
    )
    return saved, articles, plan_file


def settings_at(server: RecordedEndpoint) -> config.Settings:
    knobs = config.load(CONFIG_DIR)
    app = type(knobs.app).model_validate(knobs.app.model_dump() | {
        "model_server": {"base_url": server.base_url},
    })
    return replace(knobs, app=app)


def replay_identity(saved: RunPlan) -> WriterIdentity:
    return WriterIdentity(
        run_id=f"{saved.date}-2", attempt=1, job=ServerJob.WORK, shard=0,
        producer="utilities.replay_article_calls", git_sha="b" * 40,
    )


@pytest.mark.parametrize("selection", [
    "", "ai-01,ai-01", "../ai-01", "ai-01,", "ai-01,ai-02,ai-03,ai-04",
])
def test_invalid_or_overlarge_selection_is_not_an_inference_request(selection: str) -> None:
    with pytest.raises(ValueError):
        replay.select_ids(selection, limit=3)
    assert replay.select_ids(" ai-02, ai-01 ", limit=3) == ("ai-02", "ai-01")


@pytest.mark.parametrize("kind", [VisualKind.CHART, VisualKind.WHOWHAT])
def test_real_item_major_calls_keep_native_assets_captures_and_provenance_private(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
    kind: VisualKind,
) -> None:
    saved, source, archives, original = retained(tmp_path)
    root = tmp_path / "replay"
    ids = tuple(article.item_id for article in original)
    saved, articles, plan_file = prepared(root, source, archives, ids)
    monkeypatch.setattr(common, "PUBLIC_ROOT", tmp_path / "forbidden-public" / "digest")
    monkeypatch.setattr(common, "VAR_ROOT", tmp_path / "forbidden-run")
    positive = (
        (DRAWS_LABEL.read_bytes(), DRAWS_SUMMARIZE_AND_PLAN.read_bytes())
        if kind is VisualKind.CHART else whowhat_replies()
    )
    caplog.set_level(logging.INFO, logger="idhazh")
    identity = replay_identity(saved)
    with RecordedEndpoint(200, *positive, *declining_replies()) as server:
        replay.run_calls(
            root, plan=saved, articles=articles, settings=settings_at(server), identity=identity,
        )
        assert server.served == 4
        requests = server.sent

    envelope = read_registered_envelope(root / plan_file, ledger=LedgerName.RUN_PLAN)
    assert envelope.identity.git_sha == source.head_sha != identity.git_sha
    assert identity.model_dump_json() in caplog.messages
    for index, article in enumerate(articles):
        assert (root / "inputs" / f"{article.item_id}.article.json").read_bytes() == (
            original[index].to_json().encode()
        )
        assert not (root / "inputs" / f"{article.item_id}.summary.json").exists()
        produced = root / "outputs" / article.item_id
        items = produced / "items"
        fresh = Summary.read(items / f"{article.item_id}.summary.json")
        assert fresh.status is SummaryStatus.OK
        assert fresh.title != summary().title
        decision = VisualDecision.read(items / f"{article.item_id}{PAYLOAD_SUFFIX}")
        health = ItemHealthRow.read(items / f"{article.item_id}{HEALTH_SUFFIX}")
        assert health.run_id == identity.run_id
        assert health.model_calls == 2
        provenance = PipelineInputs.model_validate_json((items / common.INPUTS_PAYLOAD).read_bytes())
        assert provenance.model_sha256 == config.load(CONFIG_DIR).models.summarizer.sha256
        assert provenance.extractor_version == article.extractor_version
        assert provenance.sanitizer_version == article.sanitizer_version
        for turn, name in enumerate(("label", "summary")):
            captured = json.loads(
                (produced / "captures" / f"{article.item_id}.{name}.json").read_bytes()
            )
            assert captured["prompt"] == requests[index * 2 + turn]["prompt"]
            assert captured["reply"] and captured["item_id"] == article.item_id
        if index == 0:
            assert decision.kind is kind and decision.data_path
            assert (produced / "assets" / decision.data_path).is_file()
        else:
            assert decision.kind is VisualKind.NONE
            assert decision.none_reason is NoneReason.MODEL_DECLINED
            assert decision.data_path is None
            assert not (produced / "assets" / "digest" / "2026" / "08" / "21" / f"{article.item_id}.json").exists()
        assert not (tmp_path / "forbidden-public" / "digest" / "2026" / "08" / "21" / f"{article.item_id}.json").exists()
        assert not (tmp_path / "forbidden-run" / saved.date / common.CAPTURES_DIRNAME / f"{article.item_id}.label.json").exists()
    assert "This update carries no additional figures." not in requests[0]["prompt"]
    assert "This update carries no additional figures." in requests[2]["prompt"]


@pytest.mark.parametrize("defect", ["missing", "failed", "identity", "escaping"])
def test_invalid_selected_inputs_fail_before_model_work(tmp_path: Path, defect: str) -> None:
    saved, source, archives, original = retained(tmp_path)
    root = tmp_path / "replay"
    ids = tuple(article.item_id for article in original)
    _, _, plan_file = prepared(root, source, archives, ids)
    selected = root / "inputs" / f"{ids[1]}.article.json"
    if defect == "missing":
        selected.unlink()
    elif defect == "failed":
        selected.write_text(Article.model_validate(original[1].model_dump() | {
            "status": "extract_failed", "failure_code": "too_short",
            "failure_detail": "The retained extraction failed.", "title_source": None,
        }).to_json(), encoding="utf-8")
    elif defect == "identity":
        selected.write_text(original[0].to_json(), encoding="utf-8")
    else:
        plan_file = "../foreign.parquet"
    with RecordedEndpoint(200, DRAWS_LABEL.read_bytes()) as server:
        with pytest.raises(ValueError):
            loaded, articles = replay.load_inputs(
                root, plan_file=plan_file, execution=str(source.id), attempt=source.run_attempt,
                commit=source.head_sha, item_ids=ids,
            )
            replay.run_calls(
                root, plan=loaded, articles=articles, settings=settings_at(server),
                identity=replay_identity(saved),
            )
        assert server.served == 0
    assert not (root / "outputs").exists()


def test_source_attempt_must_match_and_existing_output_cannot_be_fresh_proof(
    tmp_path: Path,
) -> None:
    saved, source, archives, original = retained(tmp_path)
    root = tmp_path / "replay"
    ids = tuple(article.item_id for article in original)
    _, articles, plan_file = prepared(root, source, archives, ids)
    with pytest.raises(IntegrityError, match="exactly one compatible"):
        replay.load_inputs(
            root, plan_file=plan_file, execution=str(source.id), attempt=2,
            commit=source.head_sha, item_ids=ids,
        )
    (root / "outputs").mkdir()
    with RecordedEndpoint(200, DRAWS_LABEL.read_bytes()) as server:
        with pytest.raises(FileExistsError):
            replay.run_calls(
                root, plan=saved, articles=articles, settings=settings_at(server),
                identity=replay_identity(saved),
            )
        assert server.served == 0


def test_linked_private_root_cannot_redirect_replay_files(tmp_path: Path) -> None:
    destination = tmp_path / "outside"
    destination.mkdir()
    alias = tmp_path / "alias"
    try:
        alias.symlink_to(destination, target_is_directory=True)
    except OSError as error:
        if getattr(error, "winerror", None) == 1314:
            pytest.skip("This host does not grant filesystem symlink creation.")
        raise
    with pytest.raises(IntegrityError, match="symlink or junction"):
        replay.private_file(alias / "nested", "article.json")
    assert not (destination / "nested" / "article.json").exists()


@pytest.mark.parametrize("failure", ["bad_shape", "context_exceeded"])
def test_failed_summary_is_retained_and_never_reported_as_legitimate_none(
    tmp_path: Path, failure: str,
) -> None:
    saved, source, archives, original = retained(tmp_path)
    root = tmp_path / "replay"
    ids = (original[0].item_id,)
    _, articles, _ = prepared(root, source, archives, ids)
    malformed = b'{"choices":[{"message":{"content":"{}"},"finish_reason":"stop"}]}'
    with RecordedEndpoint(200, malformed) as server:
        knobs = settings_at(server)
        if failure == "context_exceeded":
            articles = (Article.model_validate(articles[0].model_dump() | {
                "token_count": window(knobs.models.summarizer.server),
            }),)
        with pytest.raises(ValueError, match="retained replay failed for selected items"):
            replay.run_calls(
                root, plan=saved, articles=articles, settings=knobs,
                identity=replay_identity(saved),
            )
        assert server.served == (1 if failure == "bad_shape" else 0)
    items = root / "outputs" / ids[0] / "items"
    failed = Summary.read(items / f"{ids[0]}.summary.json")
    assert failed.status is SummaryStatus.FAILED
    assert failed.failure_code is FailureCode(failure)
    assert not (items / f"{ids[0]}{PAYLOAD_SUFFIX}").exists()
    recorded = ItemHealthRow.read(items / f"{ids[0]}{HEALTH_SUFFIX}")
    assert recorded.code is failed.failure_code
