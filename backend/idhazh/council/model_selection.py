"""Which committed model preset may this Council invocation serve for a judge?"""

import hashlib
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

from idhazh import config
from idhazh.contracts.council_invocation import SelectedJudge, SelectedModel
from idhazh.contracts.knobs.council import CouncilConfig, JudgeRefusalError

_ADMITTED: ContextVar[tuple[Path, SelectedModel] | None] = ContextVar(
    "admitted_council_model", default=None,
)


def bind_model(council: CouncilConfig, judge_id: str) -> SelectedModel | None:
    models_file = config.judge_models_file(council, judge_id)
    if models_file is None:
        return None
    root = council.config_dir
    assert root is not None
    try:
        preset = (root / models_file).read_bytes()
        entry = config.parse_models(models_file, preset.decode("utf-8")).summarizer
        if entry.sha256 is None or entry.revision is None:
            raise ValueError("a judge's model requires pinned weights")
        return SelectedModel(
            models_file=models_file,
            preset_sha256=hashlib.sha256(preset).hexdigest(),
            model_id=entry.id,
            weights_sha256=entry.sha256,
        )
    except (OSError, ValueError) as error:
        raise JudgeRefusalError(judge_id, f"config/{models_file} is refused") from error


def verify_model(council: CouncilConfig, judge: SelectedJudge) -> SelectedModel | None:
    if judge.model != bind_model(council, judge.tenant):
        raise JudgeRefusalError(judge.tenant, "selected model differs from its committed preset")
    return judge.model


@contextmanager
def use_model(root: Path | None, model: SelectedModel | None) -> Iterator[None]:
    if model is not None and root is None:
        raise ValueError("a selected model requires its committed config root")
    token = _ADMITTED.set((root, model) if root is not None and model is not None else None)
    try:
        yield
    finally:
        _ADMITTED.reset(token)


def load_admitted_settings() -> config.Settings:
    admitted = _ADMITTED.get()
    if admitted is None:
        raise ValueError("this Council shard has no admitted model")
    root, model = admitted
    settings = config.load(root, models_file=model.models_file)
    if not any(
        digest.path == f"config/{model.models_file}" and digest.sha256 == model.preset_sha256
        for digest in settings.digests
    ):
        raise ValueError("the judge's loaded preset differs from the admitted model")
    return settings
