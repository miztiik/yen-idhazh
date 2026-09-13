"""Assembling one day more than once, and the vectors that have to survive it.

The oracle for Row #2: a day assembled twice with disjoint item sets carries a
vector for every item it published, not only for the last run's. Each run
encodes the items it summarized, so a block that replaced its predecessor left
the committed 2026-08-24 day with 145 vectors for 731 items.

It also holds the encoder alarm (plan 23 row #13): the committed label vectors,
what refuses a stale one, and the two assertions that say an alarm shipped
rather than a second classifier.

Integration tier (CLAUDE.md section 13). Real payloads on disk, the committed
encoder, and the assemble stage as the pipeline runs it. No mocks, no network.
"""

from __future__ import annotations

import base64
import json
import struct
from array import array
from pathlib import Path
from typing import Final

import pytest
from conftest import CONFIG_DIR, CONTRACT_FIXTURES_DIR, FIXTURES_DIR, REPO_ROOT, read_text
from pytest import MonkeyPatch

from idhazh import assemble, config, embed, publish_day_metrics
from idhazh.contracts.article import Article
from idhazh.contracts.day_metrics import DayDistribution, DayLabelSimilarity, DayMetrics
from idhazh.contracts.digest_day import DigestDay, DigestEmbeddings
from idhazh.contracts.run_manifest import RunManifest
from idhazh.contracts.run_plan import PlannedItem, RunPlan
from idhazh.contracts.summary import Summary
from idhazh.contracts.taxonomy import LifecycleStatus, Taxonomy
from idhazh.embed import DIMENSIONS, DTYPE, EMBEDDER_ID, Embedder, to_base64
from idhazh.stages import common
from idhazh.stages.assemble import stage_assemble
from idhazh.stages.common import _load_day
from utilities import build_canary_day


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
        monkeypatch.setattr(common, "VAR_ROOT", tmp_path / "run")
        monkeypatch.setattr(common, "PUBLIC_ROOT", tmp_path / "public" / "digest")
        monkeypatch.setattr(common, "STATE_ROOT", tmp_path / "state")
        items_dir = tmp_path / "run" / full_plan().date / "items"
        write_payloads(items_dir, full_plan().items[0])

        first = stage_assemble(
            plan_for(0), settings=settings, commit_sha="a" * 40, runner="fixture"
        )
        write_payloads(items_dir, full_plan().items[1])
        second = stage_assemble(
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
        monkeypatch.setattr(common, "VAR_ROOT", tmp_path / "run")
        monkeypatch.setattr(common, "PUBLIC_ROOT", tmp_path / "public" / "digest")
        monkeypatch.setattr(common, "STATE_ROOT", tmp_path / "state")
        items_dir = tmp_path / "run" / full_plan().date / "items"
        for index in (0, 1):
            write_payloads(items_dir, full_plan().items[index])
        stage_assemble(plan_for(0), settings=settings, commit_sha="a" * 40, runner="fixture")
        stage_assemble(
            plan_for(1, execution=2), settings=settings, commit_sha="a" * 40, runner="fixture"
        )

        committed = _load_day(
            assemble.day_dir(tmp_path / "public" / "digest", full_plan().date) / "digest.json"
        )

        assert committed is not None
        assert committed.embeddings is not None
        assert set(committed.embeddings.vectors) == {item.item_id for item in committed.items}

    def test_the_committed_day_carries_the_duplicate_pass(
        self, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        """The pass runs inside `build_day`, over the merged block and the whole day.

        Two different stories, so nothing groups - and `also_covered_by` reads 0
        rather than null, which is what says the pass looked. The rules it
        applies are held in `test_same_story.py`; this is the wiring.
        """
        if not Embedder(REPO_ROOT).available:
            pytest.skip("the encoder is not committed in this checkout")
        settings = config.load(CONFIG_DIR)
        monkeypatch.setattr(common, "VAR_ROOT", tmp_path / "run")
        monkeypatch.setattr(common, "PUBLIC_ROOT", tmp_path / "public" / "digest")
        monkeypatch.setattr(common, "STATE_ROOT", tmp_path / "state")
        items_dir = tmp_path / "run" / full_plan().date / "items"
        for index in (0, 1):
            write_payloads(items_dir, full_plan().items[index])
        stage_assemble(plan_for(0), settings=settings, commit_sha="a" * 40, runner="fixture")
        day = stage_assemble(
            plan_for(1, execution=2), settings=settings, commit_sha="a" * 40, runner="fixture"
        )

        assert [item.also_covered_by for item in day.items] == [0, 0]
        assert [item.same_story_as for item in day.items] == [None, None]


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


# --- the encoder alarm, plan 23 row #13 --------------------------------------

TAXONOMY: Final = Taxonomy.read(CONFIG_DIR / "taxonomy.json")
STALE_VECTORS: Final = FIXTURES_DIR / "taxonomy" / "vectors-stale-digest.bin"


class Counter:
    """Counts encoder work by calling straight through to the real encoder.

    Not a mock (Guardrail #7): the wrapped methods run, and a test that used
    them would get the same answer it gets without this. All it adds is a tally,
    which is the only way to assert that a stage made no encoder pass at all -
    a stage that does no work leaves nothing else behind to look at.
    """

    def __init__(self, monkeypatch: MonkeyPatch) -> None:
        self.loads = 0
        self.encodes = 0
        self.sequences = 0
        loaded, encoded = Embedder.load, Embedder.encode

        def load(inner: Embedder) -> None:
            self.loads += 1
            loaded(inner)

        def encode(inner: Embedder, texts: list[str]) -> list[list[float]]:
            self.encodes += 1
            self.sequences += len(texts)
            return encoded(inner, texts)

        monkeypatch.setattr(Embedder, "load", load)
        monkeypatch.setattr(Embedder, "encode", encode)


def canary_payloads(target: Path) -> tuple[str, DigestDay, RunManifest]:
    """The canary day and its manifest, built into a directory this test owns.

    Built through the canary builder's own two functions, so the day this row is
    measured over is the day the browser suite draws rather than a second
    fixture that drifts from it. Fixed in size whatever the archive grows to
    (CLAUDE.md section 13), and it can carry a case the archive never produced.
    """
    settings = config.load(CONFIG_DIR)
    day = build_canary_day.build(target, settings.app.evaluation, settings.app.visuals)
    return build_canary_day.DATE, day, build_canary_day.manifest(target, len(day.items))


def committed_vectors() -> assemble.TaxonomyVectors:
    vectors = assemble.read_taxonomy_vectors(REPO_ROOT, TAXONOMY)
    assert vectors is not None, "config/taxonomy-vectors.bin is committed"
    return vectors


def built_vectors(*sources: list[float]) -> assemble.TaxonomyVectors:
    """Label vectors this test made up, laid out by the real packer.

    Built rather than sampled, so a case the vocabulary has never produced -
    an item sitting exactly on a label - can still be asked for.
    """
    digest = assemble.taxonomy_digest(assemble.label_vector_texts(TAXONOMY))
    packed = assemble.pack_taxonomy_vectors(list(sources), digest=digest)
    body = packed[len(packed) - DIMENSIONS * len(sources) :]
    stored = tuple(
        array("b", body[index * DIMENSIONS : (index + 1) * DIMENSIONS])
        for index in range(len(sources))
    )
    return assemble.TaxonomyVectors(
        dimensions=DIMENSIONS,
        taxonomy_digest=digest,
        encoder_ref=embed.ENCODER_REF,
        vectors=stored,
        norms=tuple(assemble._norm(one) for one in stored),
    )


def rooted(target: Path, payload: bytes) -> Path:
    """A repository root holding one vectors file, for the reader to be pointed at."""
    (target / "config").mkdir(parents=True, exist_ok=True)
    (target / assemble.TAXONOMY_VECTORS_RELPATH).write_bytes(payload)
    return target


class TestTheCommittedLabelVectors:
    def test_the_file_holds_one_vector_for_every_label_the_vocabulary_offers(self) -> None:
        """Eleven today: five active verticals and six active lenses.

        A retired entry is offered to no prompt and is not encoded here either,
        which is why the retired lens does not make it twelve.
        """
        vectors = committed_vectors()
        offered = [
            entry
            for group in (TAXONOMY.verticals, TAXONOMY.lenses)
            for entry in group
            if entry.status is LifecycleStatus.ACTIVE
        ]

        assert len(vectors.vectors) == len(offered)
        assert vectors.dimensions == DIMENSIONS
        assert vectors.encoder_ref == embed.ENCODER_REF
        assert all(len(one) == DIMENSIONS for one in vectors.vectors)

    def test_the_vectors_are_the_committed_file_minus_its_header(self) -> None:
        """One int8 vector a label, no padding, and a header that names both rulers."""
        raw = (REPO_ROOT / assemble.TAXONOMY_VECTORS_RELPATH).read_bytes()
        vectors = committed_vectors()
        body = len(vectors.vectors) * DIMENSIONS

        assert body == 4224, "eleven labels at 384 int8 dimensions"
        assert len(raw) - body == assemble._VECTORS_HEADER_BYTES + len(embed.ENCODER_REF)

    def test_the_encoder_reference_the_contract_accepts_is_the_one_the_encoder_declares(
        self,
    ) -> None:
        """A contract may not import `embed` (section 4), so the pattern is pinned here."""
        block = DayLabelSimilarity(
            taxonomy_digest="a" * 64,
            encoder_ref=embed.ENCODER_REF,
            nearest=DayDistribution(
                count=1, total=0.3, p25=0.3, p50=0.3, p75=0.3, minimum=0.3, maximum=0.3
            ),
        )

        assert block.encoder_ref == embed.ENCODER_REF

    def test_the_file_carries_no_label_id_a_reader_could_pick_from(self) -> None:
        """The nearest-label pick this row refuses is unbuildable from the committed bytes.

        Not a style point. A file carrying the ids is one short edit away from
        being a classifier, and this assertion is what makes that edit visible.
        """
        raw = (REPO_ROOT / assemble.TAXONOMY_VECTORS_RELPATH).read_bytes()
        ids = [
            entry.id
            for group in (TAXONOMY.verticals, TAXONOMY.lenses)
            for entry in group
            if entry.status is LifecycleStatus.ACTIVE
        ]

        assert not any(one.encode("ascii") in raw for one in ids)

    def test_a_round_trip_through_the_file_format_keeps_every_byte(self, tmp_path: Path) -> None:
        """Packed and read back, the vectors are the ones that went in."""
        sources = [[0.5] * DIMENSIONS, [-0.25] * DIMENSIONS]
        digest = assemble.taxonomy_digest(assemble.label_vector_texts(TAXONOMY))
        root = rooted(tmp_path, assemble.pack_taxonomy_vectors(sources, digest=digest))

        read = assemble.read_taxonomy_vectors(root, TAXONOMY)

        assert read is not None
        assert [bytes(one) for one in read.vectors] == [embed.quantise(one) for one in sources]
        assert read.taxonomy_digest == digest

    def test_a_checkout_without_the_file_records_nothing_rather_than_failing(
        self, tmp_path: Path
    ) -> None:
        """Absent is not stale. The day publishes with no label vectors at all."""
        assert assemble.read_taxonomy_vectors(tmp_path, TAXONOMY) is None


class TestTheStaleFileRefusal:
    """The one way this row is allowed to fail, and it has to be loud.

    A stale vectors file compares today's items against last month's lenses and
    produces a number that looks exactly like a real one, so nothing may read
    one quietly.
    """

    def test_the_oracle_a_file_built_from_another_vocabulary_is_refused_by_name(
        self, tmp_path: Path
    ) -> None:
        """Driven from the committed fixture, whose header names a vocabulary we do not have."""
        root = rooted(tmp_path, STALE_VECTORS.read_bytes())

        with pytest.raises(ValueError) as raised:
            assemble.read_taxonomy_vectors(root, TAXONOMY)

        assert "taxonomy-vectors.bin" in str(raised.value)
        assert "build_taxonomy_vectors.py" in str(raised.value)

    def test_the_fixture_is_stale_rather_than_corrupt(self) -> None:
        """A well-formed file whose header digest is another vocabulary's.

        A fixture that failed for being malformed would pass the test above
        while proving nothing about the check this row exists for.
        """
        raw = STALE_VECTORS.read_bytes()
        head = assemble._VECTORS_HEADER_BYTES
        magic, dimensions, count, digest, length = struct.unpack(
            assemble._VECTORS_HEADER, raw[:head]
        )

        assert magic == assemble._VECTORS_MAGIC
        assert dimensions == DIMENSIONS
        assert len(raw) - head - length == count * dimensions
        assert raw[head : head + length].decode("ascii") == embed.ENCODER_REF
        assert digest.hex() != assemble.taxonomy_digest(assemble.label_vector_texts(TAXONOMY))

    def test_a_file_built_by_other_weights_is_refused_by_name(self, tmp_path: Path) -> None:
        """The vocabulary is not the only ruler. Move the weights and the cosine collapses."""
        digest = assemble.taxonomy_digest(assemble.label_vector_texts(TAXONOMY))
        packed = assemble.pack_taxonomy_vectors([[0.5] * DIMENSIONS], digest=digest)
        head = assemble._VECTORS_HEADER_BYTES
        older = embed.ENCODER_REF.replace(embed.ENCODER_DIRECTORY, "2026-01-01")
        root = rooted(
            tmp_path,
            packed[:head] + older.encode("ascii") + packed[head + len(embed.ENCODER_REF) :],
        )

        with pytest.raises(ValueError) as raised:
            assemble.read_taxonomy_vectors(root, TAXONOMY)

        assert "taxonomy-vectors.bin" in str(raised.value)
        assert "2026-01-01" in str(raised.value)

    def test_retiring_a_lens_moves_the_digest(self) -> None:
        """The digest has to see a vocabulary change, or the refusal never fires."""
        payload = TAXONOMY.model_dump(mode="json")
        payload["lenses"] = [
            lens | {"status": "retired", "retired_on": "2026-09-13"}
            if lens["id"] == "chips"
            else lens
            for lens in payload["lenses"]
        ]
        narrowed = Taxonomy.model_validate(payload)

        assert assemble.taxonomy_digest(
            assemble.label_vector_texts(narrowed)
        ) != assemble.taxonomy_digest(assemble.label_vector_texts(TAXONOMY))

    def test_editing_a_retired_entry_leaves_the_digest_alone(self) -> None:
        """A change that cannot move a vector must not fail a build."""
        payload = TAXONOMY.model_dump(mode="json")
        payload["lenses"] = [
            lens | {"display_name": "Something else"} if lens["status"] == "retired" else lens
            for lens in payload["lenses"]
        ]
        edited = Taxonomy.model_validate(payload)

        assert assemble.taxonomy_digest(
            assemble.label_vector_texts(edited)
        ) == assemble.taxonomy_digest(assemble.label_vector_texts(TAXONOMY))


class TestTheAlarmCostsTheRunNothing:
    def test_the_oracle_the_day_record_is_written_with_no_encoder_pass_at_all(
        self, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        """Zero passes over the canary day, and the day payload does not grow by a byte.

        An alarm that costs a pass an item is not an alarm, it is a second
        classifier, and this is the assertion that says which one shipped. The
        label vectors are committed once and the item vectors are already on the
        payload, so the whole reading is eleven dot products an item over bytes
        that were going to be written anyway.
        """
        if not Embedder(REPO_ROOT).available:
            pytest.skip("the encoder is not committed in this checkout")
        date, day, manifest = canary_payloads(tmp_path / "digest")
        assert day.embeddings is not None, "the canary day encodes its items"
        before = len(day.to_json().encode("utf-8"))
        vectors = committed_vectors()
        counter = Counter(monkeypatch)

        written = publish_day_metrics.publish(
            state_root=tmp_path / "state",
            date=date,
            day=day,
            manifest=manifest,
            taxonomy_vectors=vectors,
        )
        record = json.loads(written.read_text(encoding="utf-8"))

        assert (counter.loads, counter.encodes, counter.sequences) == (0, 0, 0)
        assert len(day.to_json().encode("utf-8")) == before
        assert record["label_similarity"]["nearest"]["count"] == len(day.embeddings.vectors)

    def test_the_reading_lands_on_the_day_record_and_on_no_item(self, tmp_path: Path) -> None:
        """No field on an item, no vector added, and no per-item cosine anywhere.

        The last one is the line that keeps this out of `CLAUDE.md` section 0a:
        a record naming what one summary scored is a per-item verdict whatever
        it is called. Asserted by looking for the item ids in the block's text.
        """
        if not Embedder(REPO_ROOT).available:
            pytest.skip("the encoder is not committed in this checkout")
        date, day, manifest = canary_payloads(tmp_path / "digest")

        written = publish_day_metrics.publish(
            state_root=tmp_path / "state",
            date=date,
            day=day,
            manifest=manifest,
            taxonomy_vectors=committed_vectors(),
        )
        record = json.loads(written.read_text(encoding="utf-8"))
        drawn = json.dumps(record["label_similarity"])
        published = json.loads(day.to_json())

        assert not any(item.item_id in drawn for item in day.items)
        assert set(record["label_similarity"]) == {"taxonomy_digest", "encoder_ref", "nearest"}
        assert all("label_similarity" not in item for item in published["items"])

    def test_the_two_rulers_travel_with_the_reading(self, tmp_path: Path) -> None:
        """A level only compares against one taken under the same vocabulary and weights."""
        if not Embedder(REPO_ROOT).available:
            pytest.skip("the encoder is not committed in this checkout")
        date, day, manifest = canary_payloads(tmp_path / "digest")

        written = publish_day_metrics.publish(
            state_root=tmp_path / "state",
            date=date,
            day=day,
            manifest=manifest,
            taxonomy_vectors=committed_vectors(),
        )
        block = json.loads(written.read_text(encoding="utf-8"))["label_similarity"]

        assert block["taxonomy_digest"] == assemble.taxonomy_digest(
            assemble.label_vector_texts(TAXONOMY)
        )
        assert block["encoder_ref"] == embed.ENCODER_REF

    def test_a_day_with_no_vectors_records_no_reading_rather_than_a_zero(
        self, tmp_path: Path
    ) -> None:
        """Empty is not zero. Nothing measured and an encoder that matched nothing differ."""
        if not Embedder(REPO_ROOT).available:
            pytest.skip("the encoder is not committed in this checkout")
        date, day, manifest = canary_payloads(tmp_path / "digest")

        written = publish_day_metrics.publish(
            state_root=tmp_path / "state",
            date=date,
            day=day.model_copy(update={"embeddings": None}),
            manifest=manifest,
            taxonomy_vectors=committed_vectors(),
        )

        assert json.loads(written.read_text(encoding="utf-8"))["label_similarity"] is None

    def test_a_checkout_with_no_label_vectors_records_no_reading(self, tmp_path: Path) -> None:
        """The alarm is removable. A day without it publishes exactly as it did before."""
        if not Embedder(REPO_ROOT).available:
            pytest.skip("the encoder is not committed in this checkout")
        date, day, manifest = canary_payloads(tmp_path / "digest")

        written = publish_day_metrics.publish(
            state_root=tmp_path / "state", date=date, day=day, manifest=manifest
        )

        assert json.loads(written.read_text(encoding="utf-8"))["label_similarity"] is None

    def test_a_record_written_before_this_field_existed_still_reads(
        self, tmp_path: Path
    ) -> None:
        """The read-side half of an additive field, proved by taking the key away.

        `Contract` sets `extra="forbid"`, so a field that is not optional rejects
        every record already on disk. Driven by removing the key from a record
        the producer really wrote, which is a case that cannot age out of the
        archive the way a count of unmigrated payloads would.
        """
        if not Embedder(REPO_ROOT).available:
            pytest.skip("the encoder is not committed in this checkout")
        date, day, manifest = canary_payloads(tmp_path / "digest")
        written = publish_day_metrics.publish(
            state_root=tmp_path / "state",
            date=date,
            day=day,
            manifest=manifest,
            taxonomy_vectors=committed_vectors(),
        )
        record = json.loads(written.read_text(encoding="utf-8"))
        assert record.pop("label_similarity") is not None
        record["version"] = "2026-09-08T21:00"

        older = DayMetrics.model_validate(record)

        assert older.label_similarity is None
        assert older.version == "2026-09-08T21:00"


class TestTheArithmetic:
    def test_an_item_sitting_on_a_label_reads_one(self) -> None:
        """The cosine is real arithmetic and not a constant. A vector against itself is 1.0."""
        source = [1.0] + [0.0] * (DIMENSIONS - 1)

        found = assemble.nearest_label_cosines(
            block({"ai-01": to_base64(source)}), built_vectors(source)
        )

        assert found == pytest.approx([1.0])

    def test_the_reading_is_the_closest_label_and_not_the_average_of_them(self) -> None:
        """Two labels, one of them the item's own vector. An average would not read 1.0."""
        near = [1.0] + [0.0] * (DIMENSIONS - 1)
        far = [0.0, 1.0] + [0.0] * (DIMENSIONS - 2)

        found = assemble.nearest_label_cosines(
            block({"ai-01": to_base64(near)}), built_vectors(far, near)
        )

        assert found == pytest.approx([1.0])

    def test_a_day_with_no_label_vectors_reads_nothing(self) -> None:
        assert assemble.nearest_label_cosines(block({"ai-01": vector(0.5)}), None) == []

    def test_an_item_vector_of_another_width_is_left_out_rather_than_compared(self) -> None:
        """A short vector against a full label vector is arithmetic over two different things."""
        narrow = block({"ai-01": base64.b64encode(bytes(256)).decode("ascii")}, dimensions=256)

        assert assemble.nearest_label_cosines(narrow, built_vectors([0.5] * DIMENSIONS)) == []

    def test_one_unreadable_item_is_dropped_and_the_rest_of_the_day_still_reads(self) -> None:
        """Degrade, do not fail. A short stored vector loses its own reading and no other."""
        source = [1.0] + [0.0] * (DIMENSIONS - 1)
        day = block(
            {
                "ai-01": to_base64(source),
                "ai-02": base64.b64encode(bytes(DIMENSIONS - 1)).decode("ascii"),
            }
        )

        assert assemble.nearest_label_cosines(day, built_vectors(source)) == pytest.approx([1.0])
