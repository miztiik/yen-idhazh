"""How does this judge read its own config files and name the revision it read?"""

import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Final

from pydantic import TypeAdapter, ValidationError

from idhazh import config
from idhazh.contracts.knobs.content_similarity_canaries import ContentSimilarityCanaryConfig
from idhazh.contracts.knobs.content_similarity_judge import (
    ContentSimilarityEvaluationConfig,
    ContentSimilarityJudgeConfig,
)

#: The config file a night's judge reads, as a path relative to `config/`.
JUDGE_FILE: Final = "judges/content-similarity-judge.json"

#: The known-answer pairs the judge checks itself against each run, as a path relative to
#: `config/`.
CANARY_FILE: Final = "judges/content-similarity-canaries.json"


def load_runtime(config_dir: Path | None = None) -> config.Settings:
    """Load the explicitly configured judge model and the shared non-model settings."""
    root = config.DEFAULT_CONFIG_DIR if config_dir is None else config_dir
    council = config.load_council(root)
    name = Path(JUDGE_FILE).stem
    models_file = config.judge_models_file(council, name)
    if models_file is None:
        raise ValueError(f"config/{JUDGE_FILE} must declare a model to judge pairs")
    return config.load(root, models_file=models_file)


def _refuse_a_version_that_is_not_a_past_date(version: str, *, file: str) -> None:
    """A revision date names the UTC day of an edit, so that day exists and has arrived.

    The shape was already checked, and a regular expression still accepts a day that
    does not exist and digits that are not ASCII. The clock is read here, where the file
    is, so the contract stays the same on every day it is validated.
    """
    try:
        revised = date.fromisoformat(version)
    except ValueError as error:
        raise ValueError(f"config/{file} is refused: version {version!r} is not a date") from error
    today = datetime.now(UTC).date()
    if revised > today:
        raise ValueError(
            f"config/{file} is refused: version {version} is later than today, "
            f"{today.isoformat()} UTC"
        )


def load(config_dir: Path | None = None) -> ContentSimilarityJudgeConfig:
    """Read the judge's settings, not the council's lifecycle declaration."""
    root = config.DEFAULT_CONFIG_DIR if config_dir is None else config_dir
    path = root / JUDGE_FILE
    try:
        raw = TypeAdapter(dict[str, object]).validate_python(
            json.loads(path.read_text(encoding="utf-8"))
        )
        settings = ContentSimilarityJudgeConfig.model_validate(
            {key: raw[key] for key in ContentSimilarityJudgeConfig.model_fields if key in raw}
        )
    except (ValidationError, json.JSONDecodeError) as error:
        raise ValueError(f"config/{JUDGE_FILE} is refused: {error}") from error
    _refuse_a_version_that_is_not_a_past_date(settings.version, file=JUDGE_FILE)
    return settings


def load_canaries(config_dir: Path | None = None) -> ContentSimilarityCanaryConfig:
    """Read the known-answer pairs, refusing a file whose date has not arrived."""
    root = config.DEFAULT_CONFIG_DIR if config_dir is None else config_dir
    path = root / CANARY_FILE
    try:
        canaries = ContentSimilarityCanaryConfig.model_validate_json(
            path.read_text(encoding="utf-8")
        )
    except ValidationError as error:
        raise ValueError(f"config/{CANARY_FILE} is refused: {error}") from error
    _refuse_a_version_that_is_not_a_past_date(canaries.version, file=CANARY_FILE)
    return canaries


def config_versions(config_dir: Path | None = None) -> str:
    """The revision date of each config file the judge reads, as one line of ASCII JSON.

    An object keyed by path relative to `config/`, with sorted keys and no spaces, so two
    nights that read the same revisions produce the same bytes. It exists so a night's
    records can say which tuning produced them; a new judge-owned file adds a key to this
    text rather than a column to those records. The two files are the judge's settings and
    the known-answer pairs.
    """
    versions = {
        JUDGE_FILE: load(config_dir).version,
        CANARY_FILE: load_canaries(config_dir).version,
    }
    return json.dumps(versions, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def load_evaluation(config_dir: Path | None = None) -> ContentSimilarityEvaluationConfig:
    """Read only the offline report settings; never override the selected model."""
    root = config.DEFAULT_CONFIG_DIR if config_dir is None else config_dir
    path = root / "judges" / "content-similarity-evaluation.json"
    try:
        return ContentSimilarityEvaluationConfig.model_validate_json(
            path.read_text(encoding="utf-8")
        )
    except (ValidationError, json.JSONDecodeError) as error:
        raise ValueError(
            f"config/judges/content-similarity-evaluation.json is refused: {error}"
        ) from error
