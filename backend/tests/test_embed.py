"""The build-time embeddings, and the round trip a browser has to agree with.

The oracle for Row #19 is the round trip: encode on the runner, commit, decode
on the other side, and get the same vector back to within the quantiser's own
tolerance. A silent dtype or endianness mistake fails here rather than showing
up months later as bad search results nobody can explain.

The second oracle is determinism: a vector may depend on its own text and on
nothing else. `TestPinnedArithmetic` holds the pins that make that true.
"""

from __future__ import annotations

import base64
import math
import re
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT

from idhazh.contracts.app_config import AssistConfig
from idhazh.contracts.base import SLUG_PATTERN
from idhazh.contracts.digest_day import DigestDay, DigestEmbeddings
from idhazh.embed import (
    DIMENSIONS,
    DTYPE,
    EMBEDDER_ID,
    ENCODER_VERSION,
    MAX_TOKENS,
    MODEL_RELDIR,
    ONNX_RELPATH,
    TOKENIZER_RELPATH,
    Embedder,
    build_tokenizer,
    cosine,
    dequantise,
    from_base64,
    quantise,
    readable_share,
    session_options,
    text_for,
    to_base64,
)
from utilities.token_budget import digest_paths, measure_day, percentile, raw_tokenizer

# The browser's half of the same contract. POSIX and relative, per CLAUDE.md
# section 2.
ENCODER_TS_RELPATH = "frontend/src/lib/assist/encoder.ts"
LOADER_TS_RELPATH = "frontend/src/lib/assist/loader.ts"

CORPUS = [
    "India added 15,400 megawatts of solar capacity, its biggest year yet.",
    "The central bank held interest rates steady for a fourth meeting.",
    "A new open-weights language model was released under a permissive licence.",
]

# Fifteen sentences of deliberately mixed length, so a batch of sixteen is the
# worst case for anything that reads a scale off the whole tensor.
NEIGHBOURS = [
    " ".join(["neighbour"] * (3 + 9 * index)) + f". filler item {index}." for index in range(15)
]


def unit(values: list[float]) -> list[float]:
    length = math.sqrt(sum(value * value for value in values)) or 1.0
    return [value / length for value in values]


@pytest.fixture(scope="module")
def embedder() -> Embedder:
    model = Embedder(REPO_ROOT)
    if not model.available:
        pytest.skip("the encoder is not committed in this checkout")
    model.load()
    return model


@pytest.fixture(scope="module")
def tokenizer() -> Any:
    if not (REPO_ROOT / TOKENIZER_RELPATH).exists():
        pytest.skip("the tokenizer is not committed in this checkout")
    return build_tokenizer(REPO_ROOT)


class TestQuantisation:
    def test_a_vector_becomes_one_byte_per_dimension(self) -> None:
        raw = quantise(unit([1.0] * DIMENSIONS))
        assert len(raw) == DIMENSIONS

    def test_the_wrong_width_is_refused_rather_than_padded(self) -> None:
        with pytest.raises(ValueError):
            quantise([0.1] * 128)

    def test_the_round_trip_returns_a_unit_vector(self) -> None:
        restored = dequantise(quantise(unit([0.3, -0.7] * (DIMENSIONS // 2))))
        assert math.isclose(math.sqrt(sum(v * v for v in restored)), 1.0, rel_tol=1e-6)

    def test_a_negative_component_survives_the_round_trip(self) -> None:
        """The sign bit is the classic dtype mistake, so it gets its own assertion."""
        source = unit([-1.0 if index % 2 else 1.0 for index in range(DIMENSIONS)])
        restored = dequantise(quantise(source))
        assert all((a < 0) == (b < 0) for a, b in zip(source, restored, strict=True))

    def test_base64_is_ascii_and_reversible(self) -> None:
        """A hand-made vector of four repeating values is the worst case for int8.

        Normalising it leaves components near 0.01, which land on a handful of
        the 255 levels, so the relative error is far larger than a real
        embedding's. The tight tolerance belongs on the real-encoder test.
        """
        source = unit([0.5, -0.25, 0.125, -0.0625] * (DIMENSIONS // 4))
        encoded = to_base64(source)
        assert encoded.isascii()
        assert cosine(source, from_base64(encoded)) > 0.99

    def test_base64_decodes_to_exactly_one_byte_per_dimension(self) -> None:
        encoded = to_base64(unit([0.1] * DIMENSIONS))
        assert len(base64.b64decode(encoded)) == DIMENSIONS


class TestOneEncoderTwoRuntimes:
    """The browser's copy of the encoder constants, checked against this one.

    A drift gate, not an import. `backend/` never imports frontend code; it
    reads that file as text, the same way the schema gate compares generated
    artifacts across the boundary.

    The gate is needed because `search.ts` now refuses a payload whose
    `model_id` is not the browser's copy of `EMBEDDER_ID`. Let the two strings
    separate and the failure is total and silent: either every committed day
    stops being searchable, or a foreign payload is accepted and ranked. Neither
    shows up in a type check, a lint, or a build.
    """

    def constant(self, name: str) -> str:
        source = (REPO_ROOT / ENCODER_TS_RELPATH).read_text(encoding="utf-8")
        found = re.search(rf"^export const {name} = '([^']*)';$", source, re.MULTILINE)
        assert found is not None, f"{ENCODER_TS_RELPATH} no longer declares {name}"
        return found.group(1)

    def test_the_browser_names_the_identifier_the_runner_stamps(self) -> None:
        assert self.constant("ENCODER_ID") == EMBEDDER_ID

    def test_the_identifier_is_writable_into_a_payload(self) -> None:
        """`model_id` is a slug, so the upstream mixed-case name cannot win.

        This is the whole reason the runner's string is the reconciled one. A
        reconciliation that picked the other name would fail here rather than
        at the moment a day is published.
        """
        assert re.fullmatch(SLUG_PATTERN, EMBEDDER_ID) is not None

    def test_the_browser_loads_the_directory_the_runner_reads(self) -> None:
        """A version in the path is a cache boundary only if both sides use it."""
        assert self.constant("ENCODER_VERSION") == ENCODER_VERSION
        assert MODEL_RELDIR.endswith(f"{EMBEDDER_ID}/{ENCODER_VERSION}")

    def test_the_versioned_directory_is_the_one_on_disk(self) -> None:
        """A rename that missed the weights is a 404 nothing else would catch."""
        assert (REPO_ROOT / MODEL_RELDIR).is_dir()

    def test_the_browser_guards_against_the_width_the_runner_writes(self) -> None:
        """The browser refuses a day before downloading, so it needs the width."""
        source = (REPO_ROOT / ENCODER_TS_RELPATH).read_text(encoding="utf-8")
        found = re.search(r"^export const ENCODER_DIMENSIONS = (\d+);$", source, re.MULTILINE)
        assert found is not None, f"{ENCODER_TS_RELPATH} no longer declares ENCODER_DIMENSIONS"
        assert int(found.group(1)) == DIMENSIONS

    def test_the_browser_reads_a_query_exactly_as_far_as_the_runner_read_the_items(
        self,
    ) -> None:
        """The cap moved into `config/`, and the browser's copy is still a literal.

        A query read further than the items it is matched against is a different
        question, and nothing about that failure is visible: no error, no 404,
        just worse results. The browser cannot import `config/idhazh.json` -
        that reader is server-only - so until it can, this gate is what stops
        the two numbers separating. It fails the moment `assist.max_tokens`
        moves without `loader.ts` following.
        """
        source = (REPO_ROOT / LOADER_TS_RELPATH).read_text(encoding="utf-8")
        found = re.search(r"^export const MAX_TOKENS = (\d+);$", source, re.MULTILINE)
        assert found is not None, f"{LOADER_TS_RELPATH} no longer declares MAX_TOKENS"
        assert int(found.group(1)) == MAX_TOKENS


class TestEncoder:
    def test_the_committed_model_is_the_one_the_browser_fetches(self) -> None:
        """One artifact, two runtimes. Two copies would drift the day one is updated.

        It has to be under `static/`, because that is the only directory copied
        into the served bundle. Under `public/` the runner still finds it and
        every browser gets a 404 - which is exactly what happened.
        """
        assert (
            (REPO_ROOT / ONNX_RELPATH)
            .as_posix()
            .startswith((REPO_ROOT / "frontend/static").as_posix())
        )

    def test_it_returns_one_unit_vector_per_input(self, embedder: Embedder) -> None:
        vectors = embedder.encode(CORPUS)
        assert len(vectors) == len(CORPUS)
        for vector in vectors:
            assert len(vector) == DIMENSIONS
            assert math.isclose(math.sqrt(sum(v * v for v in vector)), 1.0, rel_tol=1e-4)

    def test_encoding_nothing_is_not_an_error(self, embedder: Embedder) -> None:
        assert embedder.encode([]) == []

    def test_the_same_text_encodes_identically_twice(self, embedder: Embedder) -> None:
        """Exactly, not nearly. A near miss here is a vector that moves between runs."""
        assert embedder.encode([CORPUS[0]])[0] == embedder.encode([CORPUS[0]])[0]

    def test_the_oracle_a_vector_ignores_the_items_it_travelled_with(
        self, embedder: Embedder
    ) -> None:
        """Alone, and inside two different batches of sixteen: the same committed bytes.

        This is the reproducibility failure that started the row, and it needed
        no second machine. The encoder is dynamically quantised, so it reads its
        activation scales off whatever tensor it is handed - which made the
        other fifteen items an input to this one's vector. Measured before the
        fix on 2026-08-25 (Windows 11, 8 vCPU, onnxruntime 1.29.0): two batches
        of sixteen disagreed about a shared sentence by up to 1.5e-2 per
        component, far above anything int8 quantisation would hide.
        """
        alone = embedder.encode([CORPUS[0]])[0]
        one_crowd = embedder.encode([CORPUS[0], *NEIGHBOURS])[0]
        another_crowd = embedder.encode([CORPUS[0], *reversed(CORPUS), *NEIGHBOURS[:12]])[0]

        assert to_base64(alone) == to_base64(one_crowd) == to_base64(another_crowd)
        assert alone == one_crowd == another_crowd

    def test_a_query_retrieves_the_item_it_is_about(self, embedder: Embedder) -> None:
        """The whole point. Without this the row runs but does not work."""
        vectors = embedder.encode(CORPUS)
        query = embedder.encode(["renewable energy growth"])[0]
        scores = [cosine(query, vector) for vector in vectors]
        assert scores.index(max(scores)) == 0

    def test_an_unrelated_query_scores_lower_than_a_related_one(self, embedder: Embedder) -> None:
        vectors = embedder.encode(CORPUS)
        rates = embedder.encode(["central bank interest rate decision"])[0]
        assert cosine(rates, vectors[1]) > cosine(rates, vectors[0])

    def test_the_oracle_a_committed_vector_survives_the_wire(self, embedder: Embedder) -> None:
        """Encode, base64, decode - the exact path a browser walks.

        Measured 2026-08-22 on real summaries: 0.9990. The bar is set just below
        that, which still leaves a dtype or endianness mistake nowhere to hide -
        those score near zero, not near one.
        """
        source = embedder.encode([CORPUS[0]])[0]
        assert cosine(source, from_base64(to_base64(source))) > 0.998

    def test_ranking_survives_quantisation(self, embedder: Embedder) -> None:
        """A round trip that preserved cosine but reordered results would be useless."""
        vectors = embedder.encode(CORPUS)
        query = embedder.encode(["renewable energy growth"])[0]
        exact = sorted(range(len(CORPUS)), key=lambda i: -cosine(query, vectors[i]))
        restored = [from_base64(to_base64(vector)) for vector in vectors]
        after = sorted(range(len(CORPUS)), key=lambda i: -cosine(query, restored[i]))
        assert exact == after

    def test_a_long_summary_is_truncated_rather_than_refused(self, embedder: Embedder) -> None:
        assert len(embedder.encode([" ".join(["word"] * 5000)])[0]) == DIMENSIONS


class TestPinnedArithmetic:
    """The pins behind the oracle above, asserted where they are set.

    The oracle proves the property on this machine. These prove the reason it
    holds on any machine, and they fail the moment somebody removes one.
    """

    def test_the_session_runs_on_one_thread_in_order(self) -> None:
        """Float addition is not associative, so the thread count picks the answer."""
        import onnxruntime

        options = session_options()
        assert options.intra_op_num_threads == 1
        assert options.inter_op_num_threads == 1
        assert options.execution_mode == onnxruntime.ExecutionMode.ORT_SEQUENTIAL

    def test_the_tokenizer_truncates_at_the_cap(self, tokenizer: Any) -> None:
        assert len(tokenizer.encode(" ".join(["word"] * 5000)).ids) == MAX_TOKENS

    def test_the_tokenizer_pads_nothing(self, tokenizer: Any) -> None:
        """A pad token is an activation too, and it widens the quantiser's range."""
        short = tokenizer.encode("Solar capacity rose.")
        assert len(short.ids) < MAX_TOKENS
        assert set(short.attention_mask) == {1}

    def test_the_cap_is_the_configured_one_and_not_a_literal(self) -> None:
        """The knob has to reach the tokenizer, or it is decoration (Rule #6)."""
        if not (REPO_ROOT / TOKENIZER_RELPATH).exists():
            pytest.skip("the tokenizer is not committed in this checkout")
        narrow = build_tokenizer(REPO_ROOT, max_tokens=64)
        assert len(narrow.encode(" ".join(["word"] * 5000)).ids) == 64


class TestTokenBudget:
    """The cap against the text it has to read. See `backend/utilities/token_budget.py`.

    The distribution itself is an operator sweep, not a test - there is no
    assertion a tier can defend about a p50. What is assertable is the relation
    the cap has to hold to the corpus, so that is all this asserts.
    """

    def test_the_oracle_the_cap_sits_at_or_above_the_p95_of_what_it_reads(self) -> None:
        """The cap may truncate a tail. It may not truncate the ordinary case.

        Measured 2026-08-26 (Windows 11, 8 vCPU, Python 3.12.12) over the 1886
        embedded items of the six committed days: p95 217 tokens, p99 243, max
        280. The 18 percent over-cap figure this row started from came from a
        character-count proxy; the encoder's own count says 0.58 percent.

        This is also the gate that says when to revisit the cap. If a day
        arrives whose items are half again as long, it fails here rather than
        in a reader's search results.
        """
        if not (REPO_ROOT / TOKENIZER_RELPATH).exists():
            pytest.skip("the tokenizer is not committed in this checkout")
        paths = digest_paths(REPO_ROOT)
        if not paths:
            pytest.skip("no day is committed in this checkout")

        tokenizer = raw_tokenizer(REPO_ROOT)
        floor = AssistConfig().min_readable_letter_share
        lengths = [
            int(row["tokens"])
            for path in paths
            for row in measure_day(path, tokenizer)
            if float(row["readable_share"]) >= floor
        ]
        assert lengths, "the committed days hold no embeddable item"
        assert MAX_TOKENS >= percentile(lengths, 0.95)


class TestWhatTheEncoderCannotRead:
    """An item in another alphabet gets no vector, rather than an unretrievable one."""

    def test_english_is_fully_readable(self) -> None:
        assert readable_share("India added 15,400 megawatts of solar capacity.") == 1.0

    def test_a_headline_of_numbers_alone_is_readable(self) -> None:
        """No alphabet, nothing to be illiterate in. The tokenizer reads digits."""
        assert readable_share("15,400 (2026) - 99.9%") == 1.0

    def test_another_script_is_not_readable(self) -> None:
        assert readable_share("\u0b87\u0ba8\u0bcd\u0ba4\u0bbf\u0baf \u0bae\u0bbf\u0ba9\u0bcd") == 0.0

    def test_a_mostly_english_item_stays_readable(self) -> None:
        """One foreign name in an English summary must not cost it its vector."""
        share = readable_share(
            "The plant is live, said Reliance chair \u0bae\u0bc1\u0b95\u0bc7\u0bb7\u0bcd, on Monday."
        )
        assert share > 0.8

    def test_the_gate_reads_the_configured_share(self) -> None:
        tamil = "\u0b87\u0ba8\u0bcd\u0ba4\u0bbf\u0baf. \u0bae\u0bbf\u0b95\u0baa\u0bcd\u0baa\u0bc6\u0bb0\u0bbf\u0baf \u0b86\u0ba3\u0bcd\u0b9f\u0bc1."
        assert Embedder(REPO_ROOT, AssistConfig()).readable(tamil) is False
        assert Embedder(REPO_ROOT, AssistConfig(min_readable_letter_share=0.0)).readable(tamil)

    def test_the_oracle_an_unreadable_item_carries_no_vector(
        self, embedder: Embedder, digest_day_ok: DigestDay
    ) -> None:
        """The encoder answers anything, confidently. That is the whole problem.

        Left alone it returns a well-formed unit vector for text whose letters
        it never learned - one that says where `[UNK]` and a run of single
        characters sit in the embedding space, not what the story was. No query
        a reader types retrieves it, and nothing about the payload says so.
        """
        from idhazh.assemble import build_embeddings

        readable, unreadable = digest_day_ok.items[0], digest_day_ok.items[1]
        unreadable = unreadable.model_copy(
            update={
                "title": "\u0b9a\u0bc2\u0bb0\u0bbf\u0baf \u0bae\u0bbf\u0ba9\u0bcd \u0ba4\u0bbf\u0bb1\u0ba9\u0bcd",
                "summary": (
                    "\u0b87\u0ba8\u0bcd\u0ba4\u0bbf\u0baf\u0bbe \u0b87\u0ba8\u0bcd\u0ba4 "
                    "\u0b86\u0ba3\u0bcd\u0b9f\u0bbf\u0bb2\u0bcd \u0bae\u0bbf\u0b95\u0baa\u0bcd\u0baa\u0bc6\u0bb0\u0bbf\u0baf "
                    "\u0b85\u0bb3\u0bb5\u0bbf\u0bb2\u0bcd \u0b9a\u0bc2\u0bb0\u0bbf\u0baf \u0bae\u0bbf\u0ba9\u0bcd "
                    "\u0ba4\u0bbf\u0bb1\u0ba9\u0bc8\u0b9a\u0bcd \u0b9a\u0bc7\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4\u0ba4\u0bc1."
                ),
            }
        )

        block = build_embeddings([readable, unreadable], embedder)

        assert block is not None
        assert readable.item_id in block.vectors
        assert unreadable.item_id not in block.vectors

    def test_an_unreadable_day_publishes_with_an_empty_block(
        self, embedder: Embedder, digest_day_ok: DigestDay
    ) -> None:
        """Degrade, do not fail. A day nobody can search still reaches a reader."""
        from idhazh.assemble import build_embeddings

        only = digest_day_ok.items[0].model_copy(
            update={
                "title": "\u0b9a\u0bc2\u0bb0\u0bbf\u0baf \u0bae\u0bbf\u0ba9\u0bcd",
                "summary": "\u0b87\u0ba8\u0bcd\u0ba4\u0bbf\u0baf\u0bbe \u0b9a\u0bc7\u0bb0\u0bcd\u0ba4\u0bcd\u0ba4\u0ba4\u0bc1.",
            }
        )

        block = build_embeddings([only], embedder)

        assert block is not None
        assert block.vectors == {}
        assert block.model_id == EMBEDDER_ID


class TestDayPayload:
    def test_the_block_describes_itself(self) -> None:
        block = DigestEmbeddings(model_id=EMBEDDER_ID, dimensions=DIMENSIONS, dtype=DTYPE)
        assert block.dimensions == DIMENSIONS
        assert block.dtype == "int8"

    def test_a_day_with_no_block_is_valid(self, digest_day_ok: DigestDay) -> None:
        assert digest_day_ok.embeddings is None

    def test_text_for_carries_the_title_and_the_summary(self, digest_day_ok: DigestDay) -> None:
        item = digest_day_ok.items[0]
        rendered = text_for(item)
        assert item.title in rendered
        assert item.summary in rendered

    def test_an_absent_encoder_yields_no_block_rather_than_an_error(
        self, tmp_path: Path, digest_day_ok: DigestDay
    ) -> None:
        """A day that cannot be searched still publishes."""
        from idhazh.assemble import build_embeddings

        assert build_embeddings(digest_day_ok.items, Embedder(tmp_path)) is None
