"""Assembling one day more than once, and the vectors that have to survive it.

The oracle for Row #2: a day assembled twice with disjoint item sets carries a
vector for every item it published, not only for the last run's. Each run
encodes the items it summarized, so a block that replaced its predecessor left
the committed 2026-08-24 day with 145 vectors for 731 items.

Integration tier (CLAUDE.md section 13). Real payloads on disk, the committed
encoder, and the assemble stage as the pipeline runs it. No mocks, no network.
"""

from __future__ import annotations

import base64
from pathlib import Path

import pytest
from conftest import CONFIG_DIR, CONTRACT_FIXTURES_DIR, REPO_ROOT, read_text
from pytest import MonkeyPatch

from idhazh import assemble, cli, config
from idhazh.contracts.article import Article
from idhazh.contracts.digest_day import DigestEmbeddings
from idhazh.contracts.run_plan import PlannedItem, RunPlan
from idhazh.contracts.summary import Summary
from idhazh.embed import DIMENSIONS, DTYPE, EMBEDDER_ID, Embedder, to_base64


def full_plan() -> RunPlan:
    return RunPlan.from_json(read_text(CONTRACT_FIXTURES_DIR / "run-plan" / "one-day.json"))


def plan_for(*indexes: int, execution: int = 1) -> RunPlan:
    """The fixture plan narrowed to the items one run worked, revalidated not copied.

    Each narrowed plan carries its own `execution`, because two runs of a day are
    two executions and the manifest refuses a day whose records share a run id.
    Sharing one here made the second run's items count against the first run's
    plan, which is the arithmetic the collision broke in production.
    """
    full = full_plan()
    items = [full.items[index] for index in indexes]
    return RunPlan.model_validate(
        full.model_dump(mode="json")
        | {
            "run_id": f"{full.date}-{execution}",
            "items": [item.model_dump(mode="json") for item in items],
            "verticals": [
                vertical.model_dump(mode="json")
                | {"planned": sum(1 for item in items if item.vertical == vertical.id)}
                for vertical in full.verticals
            ],
        }
    )


def write_payloads(items_dir: Path, item: PlannedItem) -> None:
    """A real article and a real summary for one planned item, where assemble looks for them.

    The title comes from the planned item, so the two runs embed different text
    and a carried vector cannot be confused with a re-encoded one.
    """
    article = Article.model_validate(
        Article.from_json(read_text(CONTRACT_FIXTURES_DIR / "article" / "ok.json")).model_dump(
            mode="json"
        )
        | {
            "item_id": item.item_id,
            "url_key": item.url_key,
            "source_url": item.source_url,
            "canonical_url": item.canonical_url,
            "title": item.title,
        }
    )
    summary = Summary.model_validate(
        Summary.from_json(read_text(CONTRACT_FIXTURES_DIR / "summary" / "ok.json")).model_dump(
            mode="json"
        )
        | {"item_id": item.item_id, "url_key": item.url_key}
    )
    items_dir.mkdir(parents=True, exist_ok=True)
    (items_dir / f"{item.item_id}.article.json").write_text(article.to_json(), encoding="utf-8")
    (items_dir / f"{item.item_id}.summary.json").write_text(summary.to_json(), encoding="utf-8")


def block(vectors: dict[str, str], **overrides: object) -> DigestEmbeddings:
    return DigestEmbeddings.model_validate(
        {
            "model_id": EMBEDDER_ID,
            "dimensions": DIMENSIONS,
            "dtype": DTYPE,
            "vectors": vectors,
        }
        | overrides
    )


def vector(value: float) -> str:
    """A real quantised vector, through the encoder's own wire format."""
    return to_base64([value] * DIMENSIONS)


class TestTheStageAssembledTwice:
    def test_the_oracle_a_second_run_keeps_the_first_runs_vectors(
        self, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        """Two runs, disjoint items. The vector keys equal the day's item ids."""
        if not Embedder(REPO_ROOT).available:
            pytest.skip("the encoder is not committed in this checkout")
        settings = config.load(CONFIG_DIR)
        monkeypatch.setattr(cli, "VAR_ROOT", tmp_path / "run")
        monkeypatch.setattr(cli, "PUBLIC_ROOT", tmp_path / "public" / "digest")
        monkeypatch.setattr(cli, "STATE_ROOT", tmp_path / "state")
        items_dir = tmp_path / "run" / full_plan().date / "items"
        write_payloads(items_dir, full_plan().items[0])

        first = cli.stage_assemble(
            plan_for(0), settings=settings, commit_sha="a" * 40, runner="fixture"
        )
        write_payloads(items_dir, full_plan().items[1])
        second = cli.stage_assemble(
            plan_for(1, execution=2), settings=settings, commit_sha="a" * 40, runner="fixture"
        )

        assert first.embeddings is not None
        assert second.embeddings is not None
        assert [item.item_id for item in second.items] == ["ai-01", "ai-02"]
        assert set(second.embeddings.vectors) == {item.item_id for item in second.items}
        assert second.embeddings.vectors["ai-01"] == first.embeddings.vectors["ai-01"], (
            "the first run's vector is carried, not re-encoded"
        )
        assert second.embeddings.vectors["ai-02"] != second.embeddings.vectors["ai-01"]

    def test_the_carried_vectors_survive_the_committed_json(
        self, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        """The next run reads the day off disk, so the merge is only as good as the file."""
        if not Embedder(REPO_ROOT).available:
            pytest.skip("the encoder is not committed in this checkout")
        settings = config.load(CONFIG_DIR)
        monkeypatch.setattr(cli, "VAR_ROOT", tmp_path / "run")
        monkeypatch.setattr(cli, "PUBLIC_ROOT", tmp_path / "public" / "digest")
        monkeypatch.setattr(cli, "STATE_ROOT", tmp_path / "state")
        items_dir = tmp_path / "run" / full_plan().date / "items"
        for index in (0, 1):
            write_payloads(items_dir, full_plan().items[index])
        cli.stage_assemble(plan_for(0), settings=settings, commit_sha="a" * 40, runner="fixture")
        cli.stage_assemble(
            plan_for(1, execution=2), settings=settings, commit_sha="a" * 40, runner="fixture"
        )

        committed = cli._load_day(
            assemble.day_dir(tmp_path / "public" / "digest", full_plan().date) / "digest.json"
        )

        assert committed is not None
        assert committed.embeddings is not None
        assert set(committed.embeddings.vectors) == {item.item_id for item in committed.items}


class TestTheMerge:
    def test_the_first_run_of_a_day_carries_its_own_block(self) -> None:
        current = block({"ai-01": vector(0.25)})
        assert assemble.merge_embeddings(None, current) == current

    def test_a_run_whose_encoder_failed_keeps_the_vectors_the_day_had(self) -> None:
        """The encoder is secondary by construction. Losing it must not lose the day's search."""
        previous = block({"ai-01": vector(0.25)})
        assert assemble.merge_embeddings(previous, None) == previous

    def test_the_newer_vector_wins_a_collision(self) -> None:
        """A re-summarized item was encoded again from the newer text."""
        merged = assemble.merge_embeddings(
            block({"ai-01": vector(0.25)}), block({"ai-01": vector(0.75)})
        )
        assert merged is not None
        assert merged.vectors == {"ai-01": vector(0.75)}

    def test_another_width_replaces_rather_than_mixes(self) -> None:
        """One map holding two widths is what the self-describing block exists to prevent."""
        narrow = block(
            {"ai-01": base64.b64encode(bytes(256)).decode("ascii")},
            dimensions=256,
        )
        merged = assemble.merge_embeddings(narrow, block({"ai-02": vector(0.5)}))
        assert merged is not None
        assert merged.dimensions == DIMENSIONS
        assert merged.vectors == {"ai-02": vector(0.5)}

    def test_another_model_replaces_rather_than_mixes(self) -> None:
        """Two encoders' vectors are not comparable, so a merged map would rank nonsense."""
        merged = assemble.merge_embeddings(
            block({"ai-01": vector(0.25)}, model_id="some-other-encoder"),
            block({"ai-02": vector(0.5)}),
        )
        assert merged is not None
        assert merged.model_id == EMBEDDER_ID
        assert merged.vectors == {"ai-02": vector(0.5)}
