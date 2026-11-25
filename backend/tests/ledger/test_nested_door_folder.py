"""A door ledger's folder comes from the registry prefix, at any depth."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

import pytest
from pydantic import ValidationError
from support.paths import FIXTURES_DIR, REPO_ROOT, read_text

from idhazh import ledger
from idhazh.contracts.base import Contract, ServerJob
from idhazh.contracts.file_envelope import Format, Period, WriterIdentity
from idhazh.contracts.ledger_index import CompactEntry, CompactIndex
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.ledgers import Grain, LedgerEntry, LedgersConfig
from idhazh.contracts.story_similarity_pair_verdict import StorySimilarityPairVerdict
from idhazh.contracts.story_similarity_threshold_history_row import (
    StorySimilarityThresholdHistoryRow,
)
from idhazh.ledger.persist import StoredRow

pytestmark = pytest.mark.contract

A_SHA = "0735031c2a9e4b8f1d6c3a5e7b9d0f2a4c6e8b1d"
REGISTRY = REPO_ROOT / "config" / "ledgers.json"
PREFIXES = FIXTURES_DIR / "ledger-door" / "nested-prefixes.json"
KEYS: Mapping[LedgerName, tuple[str, ...]] = {
    which: ledger.door_key(which)
    for which in (
        LedgerName.CONTENT_SIMILARITY_JUDGE_PAIR_VERDICTS,
        LedgerName.CONTENT_SIMILARITY_JUDGE_THRESHOLD_HISTORY,
    )
}


def _identity() -> WriterIdentity:
    return WriterIdentity(
        run_id="2026-10-05-1",
        attempt=1,
        job=ServerJob.MIGRATE,
        shard=0,
        producer="tests.ledger.nested_door_folder",
        git_sha=A_SHA,
    )


def _registry_payload(prefixes: Mapping[str, str]) -> dict[str, object]:
    """The committed registry, with only the fixture's two door prefixes moved."""
    payload: dict[str, object] = json.loads(REGISTRY.read_text(encoding="utf-8"))
    families = payload["families"]
    assert isinstance(families, list)
    for family in families:
        assert isinstance(family, dict)
        if family["name"] != "content-similarity-judge":
            continue
        ledgers = family["ledgers"]
        assert isinstance(ledgers, list)
        for held in ledgers:
            assert isinstance(held, dict)
            prefix = prefixes.get(str(held["name"]))
            if prefix is None:
                continue
            held["grain"] = Grain.RAW_AND_COMPACT.value
            held["prefix"] = prefix.split("/")
            held["suffix"] = None
    return payload


def _fixture_registry() -> tuple[LedgersConfig, dict[LedgerName, LedgerEntry]]:
    prefixes: dict[str, str] = json.loads(PREFIXES.read_text(encoding="utf-8"))
    config = LedgersConfig.model_validate(_registry_payload(prefixes))
    return config, ledger.registry_entries(config)


def _rows(model: type[Contract]) -> list[Contract]:
    paths = {
        StorySimilarityPairVerdict: (
            "story-similarity-pair-verdict/a-judged-pair-with-its-slice-and-chance.json"
        ),
        StorySimilarityThresholdHistoryRow: (
            "story-similarity-threshold-history-row/a-night-that-held-both-thresholds.json"
        ),
    }
    return [model.from_json(read_text(FIXTURES_DIR / "contracts" / paths[model]))]


def _row_day(row: Contract) -> str:
    """The fixture row's UTC day, refused if a future fixture no longer has one."""
    if isinstance(row, StorySimilarityPairVerdict | StorySimilarityThresholdHistoryRow):
        return row.date
    raise TypeError(f"{type(row).__name__} has no string date")


def _compact_one_day[C: Contract](
    state_dir: Path,
    which: LedgerName,
    *,
    model: type[C],
    registry: Mapping[LedgerName, LedgerEntry],
) -> Path:
    day = _row_day(_rows(model)[0])
    raw = ledger.read_day_files(state_dir, which, day, registry=registry)
    stored = [ledger.load_stored([held.path], model=model) for held in raw]
    settled: list[StoredRow[C]] = ledger.settle_rows(stored, KEYS[which])
    compact = ledger.persist_period(
        state_dir,
        settled,
        model=model,
        ledger=which,
        period=Period.DAILY,
        covers=day,
        identity=_identity(),
        built_from=len(raw),
        fmt=Format.JSON,
        registry=registry,
    )
    index = CompactIndex.from_period_entries(
        ledger=which,
        period=Period.DAILY,
        entries=[CompactEntry(covers=day, rows=len(settled), bytes=compact.stat().st_size)],
    )
    index_path = ledger.compact_index_path(state_dir, which, Period.DAILY, registry=registry)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(index.to_json(), encoding="ascii", newline="\n")
    return compact


@pytest.mark.parametrize(
    ("which", "model", "folder"),
    [
        (
            LedgerName.CONTENT_SIMILARITY_JUDGE_PAIR_VERDICTS,
            StorySimilarityPairVerdict,
            "content-similarity-judge/pair-verdicts",
        ),
        (
            LedgerName.CONTENT_SIMILARITY_JUDGE_THRESHOLD_HISTORY,
            StorySimilarityThresholdHistoryRow,
            "content-similarity-judge/deep/threshold-history",
        ),
    ],
    ids=["pair-verdicts", "threshold-history"],
)
def test_a_door_ledger_files_under_its_declared_folder_only(
    tmp_path: Path, which: LedgerName, model: type[Contract], folder: str
) -> None:
    """Persist, compact and load through the door using the fixture registry."""
    _, registry = _fixture_registry()
    rows = _rows(model)

    written = ledger.persist(
        tmp_path,
        rows,
        ledger=which,
        covers=_row_day(rows[0]),
        identity=_identity(),
        fmt=Format.JSON,
        registry=registry,
    )
    compact = _compact_one_day(tmp_path, which, model=model, registry=registry)
    loaded = ledger.load_days(
        tmp_path,
        which,
        [_row_day(rows[0])],
        model=model,
        registry=registry,
        key=KEYS[which],
    )

    assert [row.to_json() for row in loaded] == [row.to_json() for row in rows]
    assert all(
        path.relative_to(tmp_path).as_posix().startswith(f"raw/{folder}/") for path in written
    )
    assert compact.relative_to(tmp_path).as_posix().startswith(f"compact/{folder}/")
    assert not (tmp_path / "raw" / which.value).exists()
    assert not (tmp_path / "compact" / which.value).exists()


def test_a_door_prefix_must_end_with_the_ledger_value() -> None:
    prefixes: dict[str, str] = json.loads(PREFIXES.read_text(encoding="utf-8"))
    prefixes["pair-verdicts"] = "content-similarity-judge/deep"

    with pytest.raises(ValidationError, match="not pair-verdicts"):
        LedgersConfig.model_validate(_registry_payload(prefixes))


def test_a_door_prefix_must_not_sit_inside_another_door_prefix() -> None:
    prefixes: dict[str, str] = json.loads(PREFIXES.read_text(encoding="utf-8"))
    prefixes["threshold-history"] = "content-similarity-judge/pair-verdicts/threshold-history"

    with pytest.raises(ValidationError, match="threshold-history sits inside pair-verdicts"):
        LedgersConfig.model_validate(_registry_payload(prefixes))
