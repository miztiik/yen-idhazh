"""Does the judge read its own required settings and revision date without changing its model?"""

import dataclasses
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from support.config import canary_config
from support.paths import CONFIG_DIR

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


def known_answer_pairs(root: Path, **changes: object) -> Path:
    """Write the known-answer pairs file beside the judge's, with some keys changed."""
    path = root / "judges" / "content-similarity-canaries.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = canary_config().model_dump(mode="json", exclude_none=True)
    raw.update(changes)
    path.write_text(json.dumps(raw), encoding="utf-8", newline="\n")
    return path


def committed(block: str) -> dict[str, object]:
    """One nested block of the committed judge file, for a test to change one key of."""
    raw = json.loads(
        (CONFIG_DIR / "judges" / "content-similarity-judge.json").read_text(encoding="utf-8")
    )
    return dict(raw[block])


def test_the_judge_reads_its_draw_and_thresholds_from_its_own_file() -> None:
    settings = config.load(CONFIG_DIR)
    execution = judge_settings.load(CONFIG_DIR)
    raw = json.loads(
        (CONFIG_DIR / "judges" / "content-similarity-judge.json").read_text(encoding="utf-8")
    )
    assert execution.model_dump() == {
        name: raw[name] for name in type(execution).model_fields
    }
    digest = next(
        digest
        for digest in settings.digests
        if digest.path == "config/judges/content-similarity-judge.json"
    )
    assert len(digest.sha256) == 64


def test_a_written_judge_file_changes_the_sampler_and_the_stamp_together(tmp_path: Path) -> None:
    declaration(
        tmp_path,
        draw=committed("draw") | {"pair_budget": 7},
        flush_every_pairs=2,
        judge_temperature=0.4,
    )
    settings = dataclasses.replace(config.load(CONFIG_DIR), config_dir=tmp_path)
    prompt_file = settings.app.prompt_files.compare_articles
    prompt_path = tmp_path / prompt_file
    prompt_path.parent.mkdir(parents=True)
    prompt_path.write_bytes((CONFIG_DIR / prompt_file).read_bytes())
    execution = judge_settings.load(tmp_path)
    assert execution.draw.pair_budget == 7 and execution.flush_every_pairs == 2
    sampling = judge.decode_settings(settings)
    assert sampling["temperature"] == 0.4
    assert stamps.judge_inputs(settings).judge_temperature == 0.4
    assert sampling["seed"] == judge.entry_of(settings).sampling["seed"]
    assert sampling["top_p"] == judge.entry_of(settings).sampling["top_p"]


def test_the_legacy_judge_file_acquires_diagnostic_defaults_without_a_new_stamp(
    tmp_path: Path,
) -> None:
    path = declaration(tmp_path, version="2026-11-19")
    raw = json.loads(path.read_text(encoding="utf-8"))
    del raw["diagnostics"]
    path.write_text(json.dumps(raw), encoding="utf-8", newline="\n")

    legacy = judge_settings.load(tmp_path)

    assert legacy.version == "2026-11-19"
    assert legacy.diagnostics.model_dump() == committed("diagnostics")
    assert legacy.draw.model_dump() == raw["draw"]
    assert legacy.thresholds.model_dump() == raw["thresholds"]


@pytest.mark.parametrize(
    "key", ["draw", "thresholds", "flush_every_pairs", "judge_temperature", "version"]
)
def test_a_missing_owned_knob_is_refused_at_the_judge_reader(tmp_path: Path, key: str) -> None:
    path = declaration(tmp_path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    del raw[key]
    path.write_text(json.dumps(raw), encoding="utf-8", newline="\n")
    with pytest.raises(ValueError, match=key):
        judge_settings.load(tmp_path)


@pytest.mark.parametrize(
    ("block", "changes", "refused"),
    [
        ("draw", {"slice_width": 0.03}, "does not divide 1"),
        ("draw", {"coarse_slice_width": 0.035}, "whole number of"),
        ("draw", {"fully_similar": {"weight": 6, "minimum": 7, "maximum": 6}}, "above the maximum"),
        ("draw", {"pair_budget": 0}, "pair_budget"),
        ("draw", {"unknown_knob": 1}, "unknown_knob"),
        ("thresholds", {"upper_start": 0.8}, "need 0.1200"),
        ("thresholds", {"lower_start": 0.95}, "apart"),
        ("thresholds", {"upper_start": 1.0}, "fully similar end"),
        ("thresholds", {"lower_start": -1.0}, "fully dissimilar end"),
        ("thresholds", {"upper_start": 0.9900000005}, "fully similar end"),
        ("thresholds", {"lower_start": -0.9900000005}, "fully dissimilar end"),
        ("thresholds", {"lower_share_level": 0.95}, "lower_share_level 0.95 is not below"),
        ("thresholds", {"pull_minimum_nights": 29}, "pull_minimum_nights 29 is above"),
        ("thresholds", {"far_gap": 0.01}, "far_gap 0.01 is not above"),
        ("thresholds", {"far_gap_step": 0.01}, "far_gap_step 0.01 is under"),
        ("thresholds", {"lowest_lower_threshold": -1.0}, "lowest_lower_threshold -1.0 leaves"),
        ("thresholds", {"highest_upper_threshold": 1.0}, "highest_upper_threshold 1.0 leaves"),
        ("thresholds", {"smallest_gap": 0.1}, "smallest_gap 0.1 is under"),
        ("thresholds", {"lowest_lower_threshold": 0.75}, "is below lowest_lower_threshold"),
        ("thresholds", {"highest_upper_threshold": 0.9}, "is above highest_upper_threshold"),
        ("thresholds", {"smallest_gap": 0.25}, "closer than smallest_gap"),
        ("diagnostics", {"cutoff": 1.01}, "cutoff"),
        ("diagnostics", {"score_bins": 2.0}, "score_bins"),
        ("diagnostics", {"score_baseline_days": 29}, "cannot exceed"),
        ("diagnostics", {"score_baseline_lookback_days": 91}, "score_baseline_lookback_days"),
        ("diagnostics", {"score_psi_share_floor": 0.025}, "uniform share"),
        ("diagnostics", {"probability_bins": True}, "probability_bins"),
        ("diagnostics", {"fit_pair_limit": 1051}, "fit_pair_limit"),
        ("diagnostics", {"publication_floor": 0.85}, "publication_floor"),
    ],
)
def test_settings_the_night_could_not_run_on_are_refused_at_the_judge_reader(
    tmp_path: Path, block: str, changes: dict[str, object], refused: str
) -> None:
    declaration(tmp_path, **{block: committed(block) | changes})
    with pytest.raises(ValueError, match=refused):
        judge_settings.load(tmp_path)


@pytest.mark.parametrize(
    "version",
    [
        20261118,
        "2026-11-18T00:00",
        "2026-02-30",
        "\u0662\u0660\u0662\u0666-\u0661\u0661-\u0661\u0668",
        "9999-12-31",
    ],
    ids=["an integer", "a time", "a day that does not exist", "non-ascii digits", "a day to come"],
)
def test_a_version_that_is_not_a_past_date_is_refused_at_the_judge_reader(
    tmp_path: Path, version: object
) -> None:
    declaration(tmp_path, version=version)
    with pytest.raises(ValueError, match="version"):
        judge_settings.load(tmp_path)


def test_a_version_of_today_is_read(tmp_path: Path) -> None:
    today = datetime.now(UTC).date().isoformat()
    declaration(tmp_path, version=today)
    assert judge_settings.load(tmp_path).version == today


def test_the_versions_a_night_read_are_one_line_of_ascii_json_keyed_by_file(
    tmp_path: Path,
) -> None:
    declaration(tmp_path, version="2026-11-17")
    known_answer_pairs(tmp_path, version="2026-11-18")
    assert judge_settings.config_versions(tmp_path) == (
        '{"judges/content-similarity-canaries.json":"2026-11-18",'
        '"judges/content-similarity-judge.json":"2026-11-17"}'
    )


def test_offline_settings_use_their_own_named_file_and_defaults(tmp_path: Path) -> None:
    from idhazh.contracts.knobs.content_similarity_judge import ContentSimilarityEvaluationConfig

    committed = judge_settings.load_evaluation(CONFIG_DIR)
    assert committed == ContentSimilarityEvaluationConfig()
    path = tmp_path / "judges" / "content-similarity-evaluation.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps({"max_cases": 3, "confidence_level": 0.8, "resamples": 17, "resample_seed": -4}),
        encoding="utf-8",
    )
    assert judge_settings.load_evaluation(tmp_path).model_dump() == {
        "max_cases": 3, "confidence_level": 0.8, "resamples": 17, "resample_seed": -4,
    }


@pytest.mark.parametrize(
    "changes",
    [
        {"max_cases": True}, {"max_cases": 0}, {"resamples": 0}, {"resamples": 1.5},
        {"resample_seed": False}, {"confidence_level": 0}, {"confidence_level": 1},
        {"confidence_level": float("nan")}, {"base_url": "https://invalid.test:443"},
    ],
)
def test_offline_settings_refuse_invalid_bounds_and_destination_fields(
    changes: dict[str, object],
) -> None:
    from idhazh.contracts.knobs.content_similarity_judge import ContentSimilarityEvaluationConfig

    with pytest.raises(ValueError):
        ContentSimilarityEvaluationConfig.model_validate(changes)
