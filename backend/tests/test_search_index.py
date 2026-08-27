"""The month search index: its contract, its writer, and the bijection they promise.

The Oracle this row is held to: every committed item carrying a vector appears
exactly once in its month index, at an offset whose bytes dequantise to the same
unit vector the day payload decodes to; every item without one appears with an
explicit null; and rebuilding the shard twice produces identical bytes. There is
only a rebuild path, so "from scratch matches incremental" is the same promise
as "twice matches once".

Contract tier for the shape, integration tier for the writer over the real
committed archive. No mocks, no network, and no fixed item counts - the
committed corpus grows several times an hour.
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

import pytest
from conftest import CONTRACT_FIXTURES_DIR, REPO_ROOT, read_text

from idhazh import assemble, cli
from idhazh.contracts.base import canonical_json
from idhazh.contracts.digest_day import DigestDay, DigestEmbeddings
from idhazh.contracts.search_index import SearchIndex, SearchIndexEntry
from idhazh.embed import DIMENSIONS, DTYPE, EMBEDDER_ID, VECTOR_SCALE, dequantise, from_base64

DIGEST_ROOT = REPO_ROOT / "frontend" / "public" / "digest"


def day() -> DigestDay:
    return DigestDay.from_json(read_text(CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json"))


def a_vector(value: float) -> str:
    """A byte pattern of the right width. The value only has to survive a round trip."""
    byte = round(max(-1.0, min(1.0, value)) * 127) & 0xFF
    return base64.b64encode(bytes([byte] * DIMENSIONS)).decode("ascii")


def block(vectors: dict[str, str], **overrides: Any) -> DigestEmbeddings:
    return DigestEmbeddings.model_validate(
        {
            "model_id": EMBEDDER_ID,
            "dimensions": DIMENSIONS,
            "dtype": DTYPE,
            "vectors": vectors,
        }
        | overrides
    )


def index(entries: list[dict[str, Any]], **overrides: Any) -> SearchIndex:
    return SearchIndex.model_validate(
        {
            "month": "2026-08",
            "model_id": EMBEDDER_ID,
            "dimensions": DIMENSIONS,
            "dtype": DTYPE,
            "scale": VECTOR_SCALE,
            "entries": entries,
        }
        | overrides
    )


def entry(**overrides: Any) -> dict[str, Any]:
    return {
        "date": "2026-08-21",
        "item_id": "ai-01",
        "title": "A headline",
        "vertical": "ai",
        "vector": None,
    } | overrides


def write_day(root: Path, payload: DigestDay) -> Path:
    path = assemble.day_dir(root, payload.date) / "digest.json"
    assemble.write_atomic(path, payload.to_json())
    return path


def committed_days() -> list[DigestDay]:
    paths = sorted(DIGEST_ROOT.glob("*/*/*/digest.json"))
    if not paths:
        pytest.skip("no committed day payloads in this checkout")
    return [DigestDay.from_json(read_text(path)) for path in paths]


# --- Contract tier ----------------------------------------------------------


class TestTheShape:
    def test_a_read_and_rewritten_index_is_byte_identical(self) -> None:
        text = index([entry(vector=0), entry(item_id="ai-02", vector=DIMENSIONS)]).to_json()
        assert SearchIndex.from_json(text).to_json() == text

    def test_the_json_is_compact_and_ends_in_one_newline(self) -> None:
        """A month is thousands of entries; the indent is bytes nobody reads."""
        built = index([entry(vector=0)])
        text = built.to_json()
        assert text.endswith("}\n")
        assert "\n" not in text[:-1]
        assert len(text) < len(canonical_json(built.model_dump(mode="json")))

    def test_an_item_with_no_vector_is_present_and_explicitly_null(self) -> None:
        """Omitting it would take it out of the browse list, not just out of search."""
        built = index([entry(), entry(item_id="ai-02", vector=0)])
        assert built.entries[0].vector is None
        assert '"vector":null' in built.to_json()

    def test_both_arms_of_the_offset_field_are_in_the_schema(self) -> None:
        """The schema itself says 'offset or null' rather than leaving it to a reader."""
        field = SearchIndex.json_schema()["$defs"]["SearchIndexEntry"]["properties"]["vector"]
        arms = field["anyOf"]
        assert {"type": "null"} in arms
        assert any(
            arm.get("type") == "integer" and arm.get("minimum") == 0 for arm in arms
        )

    def test_an_offset_that_skips_a_vector_is_rejected(self) -> None:
        """An offset one vector out decodes cleanly and ranks nonsense."""
        with pytest.raises(ValueError, match="the vectors before it end at"):
            index([entry(vector=0), entry(item_id="ai-02", vector=DIMENSIONS * 2)])

    def test_an_offset_that_is_not_a_whole_vector_in_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="the vectors before it end at"):
            index([entry(vector=1)])

    def test_a_null_between_two_vectors_does_not_move_the_next_offset(self) -> None:
        built = index(
            [
                entry(vector=0),
                entry(item_id="ai-02"),
                entry(item_id="ai-03", vector=DIMENSIONS),
            ]
        )
        assert [item.vector for item in built.entries] == [0, None, DIMENSIONS]
        assert built.vector_bytes == DIMENSIONS * 2

    def test_a_date_from_another_month_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="is not in month"):
            index([entry(date="2026-09-01")])

    def test_dates_never_go_backwards(self) -> None:
        """The index is in published order, and published order only moves forward."""
        with pytest.raises(ValueError, match="published order"):
            index([entry(date="2026-08-22"), entry(item_id="ai-02", date="2026-08-21")])

    def test_the_same_item_twice_on_one_date_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="at most once on a date"):
            index([entry(), entry()])

    def test_the_same_item_id_on_two_dates_is_allowed(self) -> None:
        """Measured 2026-08-26: 9 of the committed ids run on more than one day."""
        built = index([entry(), entry(date="2026-08-22")])
        assert [item.date for item in built.entries] == ["2026-08-21", "2026-08-22"]

    def test_an_item_id_that_is_not_addressed_by_its_vertical_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="addressed"):
            index([entry(vertical="energy")])

    def test_a_scale_of_zero_is_rejected(self) -> None:
        """Zero would decode every vector to the origin and score everything equal."""
        with pytest.raises(ValueError):
            index([entry()], scale=0.0)

    def test_the_version_is_the_newest_changelog_entry(self) -> None:
        assert SearchIndex.schema_version() == SearchIndex.__changelog__[0].version
        assert index([entry()]).version == SearchIndex.schema_version()


# --- Integration tier: the writer over real payloads -------------------------


class TestTheWriter:
    def test_the_oracle_every_committed_item_appears_once_and_decodes_the_same(
        self, tmp_path: Path
    ) -> None:
        """The bijection, over whatever the archive holds right now."""
        days = committed_days()
        months = sorted({assemble.month_of(payload.date) for payload in days})

        seen = 0
        offsets = 0
        nulls = 0
        for month in months:
            built = assemble.rebuild_search_index(
                digest_root=DIGEST_ROOT, index_root=tmp_path, month=month
            )
            raw = (tmp_path / f"{month}.bin").read_bytes()
            assert len(raw) == built.vector_bytes

            expected = [
                (payload.date, item)
                for payload in days
                if assemble.month_of(payload.date) == month
                for item in payload.items
            ]
            assert [(item.date, item.item_id) for item in built.entries] == [
                (date, item.item_id) for date, item in expected
            ]

            stored = {
                payload.date: (payload.embeddings.vectors if payload.embeddings else {})
                for payload in days
            }
            for record, (date, item) in zip(built.entries, expected, strict=True):
                assert record.title == item.title
                assert record.vertical == item.vertical
                encoded = stored[date].get(item.item_id)
                seen += 1
                if encoded is None:
                    assert record.vector is None
                    nulls += 1
                    continue
                assert record.vector is not None
                offsets += 1
                sliced = raw[record.vector : record.vector + built.dimensions]
                assert dequantise(sliced) == from_base64(encoded)

        assert seen > 0, "a probe over an empty corpus proves nothing"
        assert offsets + nulls == seen

    def test_rebuilding_twice_produces_identical_bytes(self, tmp_path: Path) -> None:
        """The whole reason there is no incremental path."""
        month = assemble.month_of(committed_days()[-1].date)
        assemble.rebuild_search_index(
            digest_root=DIGEST_ROOT, index_root=tmp_path / "once", month=month
        )
        assemble.rebuild_search_index(
            digest_root=DIGEST_ROOT, index_root=tmp_path / "twice", month=month
        )
        for suffix in (".json", ".bin"):
            first = (tmp_path / "once" / f"{month}{suffix}").read_bytes()
            assert first == (tmp_path / "twice" / f"{month}{suffix}").read_bytes()
            assert first, f"{suffix} is empty, so the comparison proved nothing"

    def test_the_index_file_is_lf(self, tmp_path: Path) -> None:
        month = assemble.month_of(committed_days()[-1].date)
        assemble.rebuild_search_index(
            digest_root=DIGEST_ROOT, index_root=tmp_path, month=month
        )
        assert b"\r\n" not in (tmp_path / f"{month}.json").read_bytes()

    def test_a_deleted_day_leaves_the_shard_correct(self, tmp_path: Path) -> None:
        """The whole retention obligation, discharged by rebuilding from what is there."""
        digest_root = tmp_path / "digest"
        first = day()
        second = first.model_copy(update={"date": "2026-08-22"})
        write_day(digest_root, first)
        path = write_day(digest_root, second)

        both = assemble.rebuild_search_index(
            digest_root=digest_root, index_root=tmp_path / "index", month="2026-08"
        )
        assert {record.date for record in both.entries} == {"2026-08-21", "2026-08-22"}

        path.unlink()
        after = assemble.rebuild_search_index(
            digest_root=digest_root, index_root=tmp_path / "index", month="2026-08"
        )
        assert {record.date for record in after.entries} == {"2026-08-21"}

    def test_a_month_with_no_days_writes_an_empty_shard(self, tmp_path: Path) -> None:
        """Degrade, do not fail: a well-formed empty index beats a 404."""
        built = assemble.rebuild_search_index(
            digest_root=tmp_path / "digest", index_root=tmp_path / "index", month="2026-01"
        )
        assert built.entries == []
        assert (tmp_path / "index" / "2026-01.bin").read_bytes() == b""
        assert built.model_id == EMBEDDER_ID

    def test_a_day_from_another_encoder_keeps_its_items_without_vectors(
        self, tmp_path: Path
    ) -> None:
        """Two encoders in one space score as scores and mean nothing."""
        digest_root = tmp_path / "digest"
        first = day()
        write_day(
            digest_root,
            first.model_copy(
                update={
                    "embeddings": block(
                        {item.item_id: a_vector(0.25) for item in first.items},
                        model_id="some-other-encoder",
                    )
                }
            ),
        )
        second = first.model_copy(update={"date": "2026-08-22"})
        write_day(
            digest_root,
            second.model_copy(
                update={"embeddings": block({second.items[0].item_id: a_vector(0.5)})}
            ),
        )

        built = assemble.rebuild_search_index(
            digest_root=digest_root, index_root=tmp_path / "index", month="2026-08"
        )

        assert built.model_id == EMBEDDER_ID
        older = [record for record in built.entries if record.date == "2026-08-21"]
        assert older and all(record.vector is None for record in older)
        assert built.vector_bytes == DIMENSIONS

    def test_a_stored_vector_of_the_wrong_width_gets_no_offset(self, tmp_path: Path) -> None:
        """A short vector would shift every offset after it, and all of them decode."""
        digest_root = tmp_path / "digest"
        payload = day()
        short = base64.b64encode(bytes(DIMENSIONS - 1)).decode("ascii")
        write_day(
            digest_root,
            payload.model_copy(
                update={
                    "embeddings": block(
                        {
                            payload.items[0].item_id: short,
                            payload.items[1].item_id: a_vector(0.25),
                        }
                    )
                }
            ),
        )

        built = assemble.rebuild_search_index(
            digest_root=digest_root, index_root=tmp_path / "index", month="2026-08"
        )

        assert built.entries[0].vector is None
        assert built.entries[1].vector == 0
        assert built.vector_bytes == DIMENSIONS

    def test_the_header_names_the_scale_the_committed_bytes_carry(self) -> None:
        """The index projects already-quantised bytes, so it states their step."""
        days = committed_days()
        month = assemble.month_of(days[-1].date)
        built, raw = assemble.build_search_index(
            month, [payload for payload in days if assemble.month_of(payload.date) == month]
        )
        if not raw:
            pytest.skip("no committed vectors in this checkout")
        assert built.scale == VECTOR_SCALE
        assert built.dtype == "int8"
        assert built.dimensions == DIMENSIONS

    def test_an_entry_carries_no_summary(self) -> None:
        """Measured 2026-08-26: carrying it is 6.35 times the entry."""
        assert "summary" not in SearchIndexEntry.model_fields
        assert set(SearchIndexEntry.model_fields) == {
            "date",
            "item_id",
            "title",
            "vertical",
            "vector",
        }


# --- Integration tier: the shard the repository actually carries -------------


class TestTheCommittedShard:
    """Where the index is written, and whether the committed one is real.

    The writer was correct from its first commit and the shard on `main` was
    not: it named one item, `ai-01`, that no published day holds. The cause was
    the path rather than the arithmetic. `stage_assemble` took the index root
    from a module constant while every pipeline test redirects only
    `PUBLIC_ROOT`, so the backend suite rebuilt the *published* shard out of
    fixture days, on any machine that ran it.
    """

    def test_a_redirected_digest_root_carries_the_index_with_it(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The test that would have caught it, and does now."""
        assert cli._index_root() == REPO_ROOT / "frontend" / "public" / "assist" / "index"

        monkeypatch.setattr(cli, "PUBLIC_ROOT", tmp_path / "public" / "digest")
        redirected = cli._index_root()

        assert redirected == tmp_path / "public" / "assist" / "index"
        assert REPO_ROOT not in redirected.parents

    def test_the_committed_shard_names_the_committed_days(self) -> None:
        """The published index is a projection of the published days, or it is wrong.

        This is the reader-facing half: the archive lists what this file holds,
        so a shard that disagrees with the tree is a page that lists the wrong
        stories. It is compared by entry rather than by bytes, because a schema
        version stamped after the last publish would move the bytes without
        moving a single story.
        """
        index_root = REPO_ROOT / "frontend" / "public" / "assist" / "index"
        if not index_root.exists():
            pytest.skip("no committed index in this checkout")

        days = committed_days()
        months = sorted({assemble.month_of(payload.date) for payload in days})
        assert months, "a probe over an empty corpus proves nothing"

        for month in months:
            path = index_root / f"{month}.json"
            assert path.exists(), f"{month} has published days and no committed shard"
            committed = SearchIndex.from_json(path.read_text(encoding="utf-8"))
            expected = [
                (payload.date, item.item_id)
                for payload in days
                if assemble.month_of(payload.date) == month
                for item in payload.items
            ]
            assert [
                (record.date, record.item_id) for record in committed.entries
            ] == expected
