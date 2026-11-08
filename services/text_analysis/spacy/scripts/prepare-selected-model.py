"""Install only configured spaCy model wheels and verify metadata without loading weights."""

import importlib.metadata
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from text_analysis.declare_service_settings import (
    EnabledLanguage,
    ModelProfile,
    ModelProfileSettings,
)
from text_analysis.load_service_settings import load_service_settings

VERIFY_ENVIRONMENT_KEY = "TEXT_ANALYSIS_VERIFY_INSTALLED_MODEL"
LANGUAGE_ENVIRONMENT_KEY = "TEXT_ANALYSIS_LANGUAGE"
PROFILE_ENVIRONMENT_KEY = "TEXT_ANALYSIS_PROFILE"
ROOT = Path(__file__).resolve().parents[4]


def _read_verification_input() -> dict[str, Any]:
    try:
        value = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, OSError):
        raise ValueError("Invalid model verification input") from None
    if not isinstance(value, dict):
        raise ValueError("Invalid model verification input")
    return value


def _verify_installed_model() -> None:
    value = _read_verification_input()
    package = value.get("package")
    version = value.get("version")
    language = value.get("language")
    spacy_version = value.get("spacy_version")
    if not all(isinstance(item, str) and item for item in (
        package,
        version,
        language,
        spacy_version,
    )):
        raise ValueError("Invalid model verification input")
    if importlib.metadata.version("spacy") != spacy_version:
        raise ValueError("Installed spaCy version does not match configuration")
    if importlib.metadata.version(package) != version:
        raise ValueError("Installed model package version does not match configuration")
    spec = importlib.util.find_spec(package)
    if spec is None or not spec.submodule_search_locations:
        raise ValueError("Installed model package metadata is unavailable")
    package_root = Path(next(iter(spec.submodule_search_locations)))
    try:
        metadata = json.loads((package_root / "meta.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raise ValueError("Installed model metadata is invalid") from None
    if (
        metadata.get("lang") != language
        or metadata.get("version") != version
        or not isinstance(metadata.get("pipeline"), list)
        or not metadata["pipeline"]
    ):
        raise ValueError("Installed model metadata does not match configuration")
    if language == "zh" and importlib.metadata.version("spacy-pkuseg") != "1.0.2":
        raise ValueError("Installed Chinese tokenizer version does not match configuration")
    print(
        json.dumps(
            {
                "language": language,
                "package": package,
                "version": version,
                "spacy_version": spacy_version,
                "pipeline": metadata["pipeline"],
            },
            separators=(",", ":"),
            sort_keys=True,
        )
    )


def _selected_models() -> tuple[
    tuple[EnabledLanguage, ModelProfile, ModelProfileSettings],
    ...,
]:
    settings = load_service_settings(ROOT)
    language_value = os.environ.get(LANGUAGE_ENVIRONMENT_KEY, "")
    profile_value = os.environ.get(PROFILE_ENVIRONMENT_KEY, "")
    if bool(language_value) != bool(profile_value):
        raise ValueError("Language and profile must be selected together")
    if language_value:
        if language_value not in ("en", "zh") or profile_value not in ("sm", "md", "lg"):
            raise ValueError("Select a configured enabled language and model profile")
        language = language_value
        profile = profile_value
        selected = settings.languages.select(language).profiles[profile]
        return ((language, profile, selected),)
    return tuple(
        (language, profile, model)
        for language in ("en", "zh")
        for profile, model in settings.languages.select(language).profiles.items()
    )


def _install_model(
    language: EnabledLanguage,
    model: ModelProfileSettings,
    spacy_version: str,
) -> None:
    subprocess.run(
        [
            "uv",
            "pip",
            "install",
            "--python",
            sys.executable,
            "--no-deps",
            model.url,
        ],
        cwd=ROOT,
        check=True,
    )
    environment = os.environ.copy()
    environment[VERIFY_ENVIRONMENT_KEY] = "1"
    subprocess.run(
        [sys.executable, str(Path(__file__).resolve())],
        cwd=ROOT,
        env=environment,
        input=json.dumps(
            {
                "language": language,
                "package": model.package,
                "version": model.version,
                "spacy_version": spacy_version,
            },
            separators=(",", ":"),
        ),
        text=True,
        check=True,
    )


def main() -> None:
    if os.environ.get(VERIFY_ENVIRONMENT_KEY) == "1":
        _verify_installed_model()
        return
    settings = load_service_settings(ROOT)
    for language, _profile, model in _selected_models():
        _install_model(language, model, settings.spacy_version)


if __name__ == "__main__":
    main()
