"""How far back the same-story window reads, and what it does when a day is missing.

Unit tier (CLAUDE.md section 13). Every day here is built in the test on a
temporary tree: nothing reads `frontend/public/digest`, whose cost follows what
the pipeline has piled up.

The question this file answers is Guardrail #12's: the read is bounded by the
window and never by how much archive exists, so it opens the same number of
files on the thousandth day as on the third.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from conftest import CONTRACT_FIXTURES_DIR, read_text

from idhazh.embed import DIMENSIONS, DTYPE, EMBEDDER_ID, to_base64
from idhazh.stages import common
from idhazh.stages.assemble import _earlier_days

A_COMMITTED_DAY = CONTRACT_FIXTURES_DIR / "digest-day" / "two-runs.json"


def a_day_on(public_root: Path, date: str, *, vectors: dict[str, str] | None = None) -> None:
    """One published day at a chosen date, from the committed contract fixture."""
    payload = json.loads(read_text(A_COMMITTED_DAY))
    payload["date"] = date
    if vectors is not None:
        payload["embeddings"] = {
            "model_id": EMBEDDER_ID,
            "dimensions": DIMENSIONS,
            "dtype": DTYPE,
            "vectors": vectors,
        }
    year, month, dom = date.split("-")
    where = public_root / "digest" / year / month / dom
    where.mkdir(parents=True, exist_ok=True)
    (where / "digest.json").write_text(json.dumps(payload), encoding="utf-8")


@pytest.fixture
def published(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "public"
    monkeypatch.setattr(common, "PUBLIC_ROOT", root / "digest")
    return root


def test_a_thirty_six_hour_window_opens_one_day(published: Path) -> None:
    """`ceil(36 / 24)` is 2 - one earlier day, because today is the other."""
    for date in ("2026-08-28", "2026-08-29", "2026-08-30"):
        a_day_on(published, date)

    found = _earlier_days("2026-08-31", window_hours=36.0)

    assert [day.date for day in found] == ["2026-08-30", "2026-08-29"]


def test_the_archive_behind_the_window_is_never_opened(published: Path) -> None:
    """The bound is the window, not the tree. Ten days on disk, two reached."""
    for dom in range(20, 31):
        a_day_on(published, f"2026-08-{dom}")

    assert len(_earlier_days("2026-08-31", window_hours=36.0)) == 2
    assert len(_earlier_days("2026-08-31", window_hours=12.0)) == 1


def test_a_window_of_zero_reads_nothing_at_all(published: Path) -> None:
    """The revert path does not even open a file."""
    a_day_on(published, "2026-08-30")

    assert _earlier_days("2026-08-31", window_hours=0.0) == []


def test_a_day_the_archive_does_not_hold_is_a_quiet_miss(published: Path) -> None:
    """The archive starts somewhere, and a run near that start is not a failure."""
    a_day_on(published, "2026-08-29")

    found = _earlier_days("2026-08-31", window_hours=36.0)

    assert [day.date for day in found] == ["2026-08-29"]


def test_an_earlier_day_arrives_with_its_vectors(published: Path) -> None:
    """Without them the pass can compare nothing, so this is what the read is for."""
    payload = json.loads(read_text(A_COMMITTED_DAY))
    first = str(payload["items"][0]["item_id"])
    a_day_on(
        published,
        "2026-08-30",
        vectors={first: to_base64([1.0] + [0.0] * (DIMENSIONS - 1))},
    )

    found = _earlier_days("2026-08-31", window_hours=36.0)

    assert found[0].items, "the day's stories"
    assert found[0].embeddings is not None
    assert first in found[0].embeddings.vectors, "and the vector to place one against"