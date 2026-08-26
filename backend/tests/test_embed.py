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
    session_options,
    text_for,
    to_base64,
)

# The browser's half of the same contract. POSIX and relative, per CLAUDE.md
# section 2.
ENCODER_TS_RELPATH = "frontend/src/lib/assist/encoder.ts"

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
