"""The build-time embeddings, and the round trip a browser has to agree with.

The oracle for Row #19 is the round trip: encode on the runner, commit, decode
on the other side, and get the same vector back to within the quantiser's own
tolerance. A silent dtype or endianness mistake fails here rather than showing
up months later as bad search results nobody can explain.
"""

from __future__ import annotations

import base64
import math
from pathlib import Path

import pytest
from conftest import REPO_ROOT

from idhazh.contracts.digest_day import DigestDay, DigestEmbeddings
from idhazh.embed import (
    DIMENSIONS,
    DTYPE,
    EMBEDDER_ID,
    ONNX_RELPATH,
    Embedder,
    cosine,
    dequantise,
    from_base64,
    quantise,
    text_for,
    to_base64,
)

CORPUS = [
    "India added 15,400 megawatts of solar capacity, its biggest year yet.",
    "The central bank held interest rates steady for a fourth meeting.",
    "A new open-weights language model was released under a permissive licence.",
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
        first = embedder.encode([CORPUS[0]])[0]
        second = embedder.encode([CORPUS[0]])[0]
        assert cosine(first, second) > 0.9999

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
