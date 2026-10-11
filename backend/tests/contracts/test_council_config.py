"""Does the council read its own file with the same clocks and judge list?"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from conftest import CONFIG_DIR
from pydantic import ValidationError

from idhazh import config
from idhazh.contracts.knobs.council import CouncilConfig

pytestmark = pytest.mark.contract


def test_the_committed_file_names_every_knob_and_both_loaders_read_it() -> None:
    text = (CONFIG_DIR / "llm_council.json").read_text(encoding="utf-8")
    expected = json.loads(text)
    assert set(expected) == set(CouncilConfig.model_fields)
    assert config.load_council(CONFIG_DIR).model_dump(mode="json") == expected
    settings = config.load(CONFIG_DIR)
    assert settings.council == config.load_council(CONFIG_DIR)
    digest = next(d for d in settings.digests if d.path == "config/llm_council.json")
    assert digest.sha256 == hashlib.sha256(text.encode("utf-8")).hexdigest()
    assert "council" not in type(settings.app).model_fields


def test_the_loader_reads_the_named_file_without_other_config(tmp_path: Path) -> None:
    written = CouncilConfig(shards=2, judge_names=("second-judge", "first-judge"))
    (tmp_path / "llm_council.json").write_text(
        written.model_dump_json(), encoding="utf-8", newline="\n"
    )
    assert config.load_council(tmp_path) == written


def test_a_missing_file_does_not_silently_use_defaults(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match=r"llm_council\.json"):
        config.load_council(tmp_path)


@pytest.mark.parametrize("raw", [{"tenants": []}, {"judge_names": ["Not a slug"]}, {"shards": 0}])
def test_the_loader_validates_the_councils_own_model(
    tmp_path: Path, raw: dict[str, object]
) -> None:
    (tmp_path / "llm_council.json").write_text(json.dumps(raw), encoding="utf-8", newline="\n")
    with pytest.raises(ValidationError):
        config.load_council(tmp_path)


def test_an_empty_judge_list_keeps_the_clocks() -> None:
    council = CouncilConfig(judge_names=())
    assert council.judge_names == ()
    assert council.shards >= 1
    assert council.shard_timeout_minutes >= 1


def test_the_whole_range_of_the_repair_cap_loads() -> None:
    field = CouncilConfig.model_fields["repair_dates_a_night"]
    lowest = next(bound.ge for bound in field.metadata if hasattr(bound, "ge"))
    highest = next(bound.le for bound in field.metadata if hasattr(bound, "le"))
    for value in range(lowest, highest + 1):
        assert CouncilConfig(repair_dates_a_night=value).repair_dates_a_night == value


def test_the_council_carries_its_own_window_its_floor_and_its_cap() -> None:
    committed = config.load_council(CONFIG_DIR)
    fresh = CouncilConfig()
    assert committed.repair_window_nights == fresh.repair_window_nights
    assert committed.first_night == fresh.first_night
    assert committed.repair_dates_a_night == fresh.repair_dates_a_night
