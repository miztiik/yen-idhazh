"""How does one source become two native text-analysis responses?"""

import json
from dataclasses import dataclass
from pathlib import Path

import httpx
from collect_operations import Outcome
from gliner_api.declare_analysis_contracts import AnalyzeTextRequest as GlinerRequest
from gliner_api.declare_analysis_contracts import AnalyzeTextResult as GlinerResult
from gliner_api.declare_api_contracts import ANALYZE_TEXT_PATH as GLINER_ANALYZE_TEXT_PATH
from gliner_api.declare_api_contracts import ErrorResult as GlinerError
from gliner_api.load_settings import SETTINGS_PATH as GLINER_SETTINGS_PATH
from gliner_api.load_settings import GlinerSettings
from gliner_api.validate_analysis_results import validate_analysis_results
from load_caller_settings import CallerAnalysisSettings
from pydantic import ValidationError
from text_analysis.declare_api_contracts import (
    ANALYZE_TEXT_PATH,
    AnalysisResult,
    AnalyzeTextRequest,
    TextAnalysisHealth,
)
from text_analysis.declare_api_contracts import ErrorResult as SpacyError
from text_analysis.declare_service_settings import ServiceSettings
from text_analysis.load_service_settings import SETTINGS_PATH as SPACY_SETTINGS_PATH
from write_reports import write_atomic


@dataclass(frozen=True)
class Inputs:
    text: str
    profile: str
    feature_mode: str
    classification_tasks: str


def read_inputs(event: object, environment: dict[str, str]) -> Inputs:
    """Read dispatch text as data and validate the selected controls."""
    if not isinstance(event, dict) or not isinstance(event.get("inputs"), dict):
        raise ValueError("The dispatch inputs are invalid.")
    text = event["inputs"].get("text")
    profile = environment.get("TEXT_ANALYSIS_PROFILE", "")
    mode = environment.get("TEXT_ANALYSIS_FEATURE_MODE", "")
    tasks = event["inputs"].get("classification_tasks", "")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("The source text must not be empty.")
    if profile not in ("sm", "md", "lg") or mode not in ("default", "all"):
        raise ValueError("The selected profile or feature mode is invalid.")
    if not isinstance(tasks, str):
        raise ValueError("Classification tasks must be native tasks JSON text.")
    return Inputs(
        text=text,
        profile=profile,
        feature_mode=mode,
        classification_tasks=tasks,
    )


def save_settings(root: Path, directory: Path) -> ServiceSettings:
    """Save exactly the native bytes validated for this run, before API startup."""
    spacy = (root / SPACY_SETTINGS_PATH).read_bytes()
    settings: ServiceSettings = ServiceSettings.model_validate_json(spacy)
    write_atomic(directory / "spacy" / "settings.json", spacy)
    gliner = (root / GLINER_SETTINGS_PATH).read_bytes()
    GlinerSettings.model_validate_json(gliner)
    write_atomic(directory / "gliner" / "settings.json", gliner)
    return settings


def gliner_labels(settings: ServiceSettings) -> list[str]:
    """Use the configured presentation types as caller-selected entity labels."""
    labels = list(dict.fromkeys(settings.named_entities.label_map.values()))
    if not labels:
        raise ValueError("No configured entity labels are available for GLiNER.")
    return labels


def spacy_request(inputs: Inputs, health: TextAnalysisHealth) -> AnalyzeTextRequest:
    """Build the selected request without replacing native default selection."""
    capability = next(item for item in health.languages if item.language == "en" and item.enabled)
    payload: dict[str, object] = {
        "text": inputs.text,
        "language": "en",
        "model_profile": inputs.profile,
    }
    if inputs.feature_mode == "all":
        payload["features"] = list(capability.supported_features)
    request: AnalyzeTextRequest = AnalyzeTextRequest.model_validate_json(json.dumps(payload))
    if request.features is not None and not set(request.features).issubset(
        capability.supported_features
    ):
        raise ValueError("The selected spaCy features are not supported.")
    return request


async def send_request(
    client: httpx.AsyncClient,
    path: str,
    request: bytes,
    directory: Path,
) -> httpx.Response:
    write_atomic(directory / "request.json", request)
    response = await client.post(
        path, content=request, headers={"content-type": "application/json"}
    )
    write_atomic(directory / "response.json", response.content)
    return response


async def collect_spacy(
    client: httpx.AsyncClient, inputs: Inputs, health: TextAnalysisHealth, directory: Path
) -> Outcome:
    """Collect and validate exactly one spaCy analysis response."""
    try:
        request = spacy_request(inputs, health)
        response = await send_request(
            client,
            ANALYZE_TEXT_PATH,
            request.model_dump_json(exclude_none=True).encode("utf-8"),
            directory / "spacy",
        )
        if response.status_code in (200, 422):
            try:
                result = AnalysisResult.model_validate_json(response.content)
            except ValidationError:
                if response.status_code != 422:
                    raise
            else:
                capability = next(
                    item for item in health.languages if item.language == "en" and item.enabled
                )
                expected_features = (
                    request.features
                    if request.features is not None
                    else capability.default_features
                )
                if (
                    result.language != request.language
                    or result.model.profile != request.model_profile
                    or tuple(feature.feature for feature in result.features) != expected_features
                ):
                    raise ValueError("The spaCy response does not match the request.")
                return Outcome(
                    result=result.model_dump(mode="json"),
                    incomplete=result.status != "complete",
                )
        error = SpacyError.model_validate_json(response.content)
        return Outcome(error=f"{error.error.code}: {error.error.message}")
    except (httpx.HTTPError, OSError, ValidationError, ValueError, StopIteration):
        return Outcome(error="The spaCy request failed or returned an invalid response.")


async def collect_gliner(
    client: httpx.AsyncClient, inputs: Inputs, settings: CallerAnalysisSettings, directory: Path
) -> Outcome:
    """Collect entities and linked candidates in exactly one native extraction response."""
    try:
        request = GlinerRequest.model_validate_json(
            json.dumps(
                {
                    "text": inputs.text,
                    "schema": settings.analysis_schema.model_dump(exclude_none=True),
                    "include_confidence": settings.include_confidence,
                    "include_spans": settings.include_spans,
                }
            ),
            strict=True,
        )
        response = await send_request(
            client,
            GLINER_ANALYZE_TEXT_PATH,
            request.model_dump_json(by_alias=True, exclude_unset=True).encode("utf-8"),
            directory / "gliner",
        )
        if response.status_code == 200:
            wire = GlinerResult.model_validate_json(response.content)
            result = validate_analysis_results(wire.result, request)
            return Outcome(result=result.model_dump(mode="json"))
        error = GlinerError.model_validate_json(response.content)
        return Outcome(error=f"{error.error.code}: {error.error.message}")
    except (httpx.HTTPError, OSError, ValidationError, ValueError):
        return Outcome(error="The GLiNER NER request failed or returned an invalid response.")
