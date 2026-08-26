"""Backfilling the vectors a closed day never got.

Row #11's oracle: for every closed committed day, the vector count equals the
count of items that earned a vector. Coverage was 439 of the 1,614 eligible
items over the five closed days when this was written - the ranking worked and
the corpus was part empty, because `build_day` used to replace a day's
embeddings block instead of merging it and nothing revisits a closed day.

Unit tier for the detectors (which day is in scope, which day is wrong),
integration tier for the stage itself: a real payload on disk, the committed
encoder, no mocks and no network.
"""

from __future__ import annotations

import base64
from pathlib import Path

import pytest
from conftest import CONTRACT_FIXTURES_DIR, REPO_ROOT, read_text

from idhazh import assemble, cli
from idhazh.contracts.app_config import AssistConfig
from idhazh.contracts.digest_day import DigestDay, DigestEmbeddings
from idhazh.embed import DIMENSIONS, DTYPE, EMBEDDER_ID, Embedder, to_base64

# A headline written in Devanagari. `readable_share` counts no Latin letter in
# it, so no configured share above zero lets it earn a vector.
UNREADABLE = "\u0938\u092e\u093e\u091a\u093e\u0930 \u0914\u0930 \u0935\u093f\u0936\u094d\u0932"


def embedder(root: Path = REPO_ROOT) -> Embedder:
    return Embedder(root, AssistConfig())


def day() -> DigestDay:
    return DigestDay.from_json(read_text(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json"))


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


def with_block(embeddings: DigestEmbeddings | None) -> DigestDay:
    return day().model_copy(update={"embeddings": embeddings})


def with_one_unreadable_item(embeddings: DigestEmbeddings | None) -> DigestDay:
    """The same day, with `ai-02` written in a script the encoder cannot read."""
    base = with_block(embeddings)
    items = [
        item.model_copy(update={"title": UNREADABLE, "summary": UNREADABLE})
        if item.item_id == "ai-02"
        else item
        for item in base.items
    ]
    return base.model_copy(update={"items": items})


def vector(value: float) -> str:
    return to_base64([value] * DIMENSIONS)


def write_day(root: Path, payload: DigestDay) -> Path:
    path = assemble.day_dir(root, payload.date) / "digest.json"
    assemble.write_atomic(path, payload.to_json())
    return path


def needs_encoder() -> None:
    if not embedder().available:
        pytest.skip("the encoder is not committed in this checkout")



class TestWhichDaysAreInScope:
    def test_a_finished_day_is_closed(self) -> None:
        assert cli.is_closed("2026-08-25", today="2026-08-26")

    def test_the_live_day_is_not(self) -> None:
        """The pipeline appends to it several times an hour and the payload is one file."""
        assert not cli.is_closed("2026-08-26", today="2026-08-26")

    def test_a_day_stamped_ahead_of_today_is_not(self) -> None:
        """A clock skew must not open the live day's neighbour either."""
        assert not cli.is_closed("2026-08-27", today="2026-08-26")


class TestWhichItemsEarnAVector:
    def test_readable_items_all_earn_one(self) -> None:
        assert cli.earns_a_vector(day(), embedder()) == {"ai-01", "energy-01", "ai-02"}

    def test_an_item_the_encoder_cannot_read_earns_nothing(self) -> None:
        """A vector about characters rather than a story is one no query retrieves."""
        assert cli.earns_a_vector(with_one_unreadable_item(None), embedder()) == {
            "ai-01",
            "energy-01",
        }


class TestWhichDaysAreWrong:
    def test_a_day_with_no_block_is_wrong(self) -> None:
        assert cli.needs_backfill(with_block(None), embedder())

    def test_a_day_short_of_a_vector_is_wrong(self) -> None:
        assert cli.needs_backfill(with_block(block({"ai-01": vector(0.25)})), embedder())

    def test_a_day_that_matches_is_not(self) -> None:
        """This is what makes the command safe to dispatch twice."""
        covered = block({item.item_id: vector(0.25) for item in day().items})
        assert not cli.needs_backfill(with_block(covered), embedder())

    def test_a_surplus_vector_is_wrong_too(self) -> None:
        """Short and surplus are one question: is the block what this encoder would write?"""
        every = block({item.item_id: vector(0.25) for item in day().items})
        assert cli.needs_backfill(with_one_unreadable_item(every), embedder())

    def test_another_width_is_wrong(self) -> None:
        """One map holding two widths is nonsense no reader-side decoder can read."""
        narrow = block(
            {"ai-01": base64.b64encode(bytes(256)).decode("ascii")},
            dimensions=256,
        )
        assert cli.needs_backfill(with_block(narrow), embedder())

    def test_another_model_is_wrong(self) -> None:
        other = block({"ai-01": vector(0.25)}, model_id="some-other-encoder")
        assert cli.needs_backfill(with_block(other), embedder())


class TestTheBackfill:
    def test_the_oracle_a_repaired_day_carries_a_vector_for_every_earned_item(
        self, tmp_path: Path
    ) -> None:
        needs_encoder()
        path = write_day(tmp_path, with_block(block({})))

        assert (
            cli.stage_backfill_vectors(root=tmp_path, today="2026-08-22", embedder=embedder()) == 0
        )

        repaired = DigestDay.from_json(path.read_text(encoding="utf-8"))
        assert repaired.embeddings is not None
        assert set(repaired.embeddings.vectors) == {item.item_id for item in repaired.items}
        assert repaired.version == DigestDay.schema_version()

    def test_an_item_that_earns_nothing_gets_nothing(self, tmp_path: Path) -> None:
        needs_encoder()
        path = write_day(tmp_path, with_one_unreadable_item(block({})))

        cli.stage_backfill_vectors(root=tmp_path, today="2026-08-22", embedder=embedder())

        repaired = DigestDay.from_json(path.read_text(encoding="utf-8"))
        assert repaired.embeddings is not None
        assert set(repaired.embeddings.vectors) == {"ai-01", "energy-01"}

    def test_a_surplus_vector_is_dropped(self, tmp_path: Path) -> None:
        """A day that embedded everything loses the vector no query could retrieve."""
        needs_encoder()
        every = block({item.item_id: vector(0.25) for item in day().items})
        path = write_day(tmp_path, with_one_unreadable_item(every))

        cli.stage_backfill_vectors(root=tmp_path, today="2026-08-22", embedder=embedder())

        repaired = DigestDay.from_json(path.read_text(encoding="utf-8"))
        assert repaired.embeddings is not None
        assert "ai-02" not in repaired.embeddings.vectors

    def test_a_wrong_day_is_re_encoded_whole(self, tmp_path: Path) -> None:
        """One block, one arithmetic.

        Measured 2026-08-26: every closed day's committed vectors predate the
        commit that stopped `encode` padding and batching, and a re-encode moves
        them by a median cosine of 0.9936. Topping such a day up would leave one
        block holding two arithmetics for a single query to rank against.
        """
        needs_encoder()
        stale = vector(0.25)
        path = write_day(tmp_path, with_block(block({"ai-01": stale})))

        cli.stage_backfill_vectors(root=tmp_path, today="2026-08-22", embedder=embedder())

        repaired = DigestDay.from_json(path.read_text(encoding="utf-8"))
        assert repaired.embeddings is not None
        assert repaired.embeddings.vectors["ai-01"] != stale
        assert len(repaired.embeddings.vectors) == 3

    def test_running_it_again_changes_nothing(self, tmp_path: Path) -> None:
        needs_encoder()
        path = write_day(tmp_path, with_block(block({})))
        cli.stage_backfill_vectors(root=tmp_path, today="2026-08-22", embedder=embedder())
        once = path.read_bytes()

        cli.stage_backfill_vectors(root=tmp_path, today="2026-08-22", embedder=embedder())

        assert path.read_bytes() == once

    def test_the_live_day_is_left_alone(self, tmp_path: Path) -> None:
        """It is being written by the run that owns it, and a payload has no union merge."""
        needs_encoder()
        path = write_day(tmp_path, with_block(block({})))
        before = path.read_bytes()

        assert (
            cli.stage_backfill_vectors(root=tmp_path, today="2026-08-21", embedder=embedder()) == 0
        )

        assert path.read_bytes() == before

    def test_no_encoder_fails_instead_of_reporting_success(self, tmp_path: Path) -> None:
        """Unlike a run, this command has nothing else to publish. A no-op is a lie."""
        path = write_day(tmp_path, with_block(block({})))
        before = path.read_bytes()

        assert (
            cli.stage_backfill_vectors(
                root=tmp_path, today="2026-08-22", embedder=embedder(tmp_path / "empty")
            )
            == 1
        )

        assert path.read_bytes() == before
