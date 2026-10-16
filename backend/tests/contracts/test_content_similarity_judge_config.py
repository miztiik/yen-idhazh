"""Does the judge read its own required execution settings without changing its model?"""

import dataclasses
import json
from pathlib import Path

import pytest
from conftest import CONFIG_DIR

from idhazh import config
from idhazh.content_similarity_judge import settings as judge_settings
from idhazh.similarity import judge, stamps

pytestmark = pytest.mark.contract


def declaration(root: Path, **changes: object) -> Path:
    """Write the named file with a lifecycle declaration and real execution knobs."""
    path = root / "judges" / "content-similarity-judge.json"
    path.parent.mkdir(parents=True)
    raw = json.loads(
        (CONFIG_DIR / "judges" / "content-similarity-judge.json").read_text(encoding="utf-8")
    )
    raw.update(changes)
    path.write_text(json.dumps(raw), encoding="utf-8", newline="\n")
    return path


def test_the_judge_owns_the_three_execution_knobs_and_shared_stages_keep_the_rest() -> None:
    settings = config.load(CONFIG_DIR)
    execution = judge_settings.load(CONFIG_DIR)
    assert execution.model_dump() == {
        "pair_budget": 200,
        "flush_every_pairs": 1,
        "judge_temperature": 0.0,
    }
    shared = settings.app.assemble.same_story.judging_knobs().model_dump()
    assert not set(type(execution).model_fields) & set(shared)
    assert {"enabled", "band_low", "bin_width", "discard_share", "applied_lookback_days"} <= set(
        shared
    )
    digest = next(
        digest
        for digest in settings.digests
        if digest.path == "config/judges/content-similarity-judge.json"
    )
    assert len(digest.sha256) == 64


def test_a_written_judge_file_changes_the_sampler_and_the_stamp_together(tmp_path: Path) -> None:
    declaration(tmp_path, pair_budget=7, flush_every_pairs=2, judge_temperature=0.4)
    settings = dataclasses.replace(config.load(CONFIG_DIR), config_dir=tmp_path)
    execution = judge_settings.load(tmp_path)
    assert execution.pair_budget == 7 and execution.flush_every_pairs == 2
    sampling = judge.decode_settings(settings)
    assert sampling["temperature"] == 0.4
    assert stamps.judge_inputs(settings).judge_temperature == 0.4
    assert sampling["seed"] == judge.entry_of(settings).sampling["seed"]
    assert sampling["top_p"] == judge.entry_of(settings).sampling["top_p"]


@pytest.mark.parametrize("key", ["pair_budget", "flush_every_pairs", "judge_temperature"])
def test_a_missing_owned_knob_is_refused_at_the_judge_reader(tmp_path: Path, key: str) -> None:
    path = declaration(tmp_path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    del raw[key]
    path.write_text(json.dumps(raw), encoding="utf-8", newline="\n")
    with pytest.raises(ValueError, match=key):
        judge_settings.load(tmp_path)
