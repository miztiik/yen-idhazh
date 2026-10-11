"""How does this judge read its own execution settings?"""

import json
from pathlib import Path

from pydantic import TypeAdapter, ValidationError

from idhazh import config
from idhazh.contracts.knobs.content_similarity_judge import ContentSimilarityJudgeConfig


def load(config_dir: Path | None = None) -> ContentSimilarityJudgeConfig:
    """Read the judge's settings, not the council's lifecycle declaration."""
    root = config.DEFAULT_CONFIG_DIR if config_dir is None else config_dir
    path = root / "judges" / "content-similarity-judge.json"
    try:
        raw = TypeAdapter(dict[str, object]).validate_python(
            json.loads(path.read_text(encoding="utf-8"))
        )
        return ContentSimilarityJudgeConfig.model_validate(
            {key: raw[key] for key in ContentSimilarityJudgeConfig.model_fields if key in raw}
        )
    except (ValidationError, json.JSONDecodeError) as error:
        raise ValueError(
            f"config/judges/content-similarity-judge.json is refused: {error}"
        ) from error
