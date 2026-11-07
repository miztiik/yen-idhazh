"""Replay real UniEval predictions only at the model-call boundary in an owned process."""

import hashlib
import io
import multiprocessing
import os
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from multiprocessing.process import BaseProcess
from pathlib import Path

import httpx
from summary_evaluator_cases.contract_examples import REPOSITORY

from scripts.recording_json import canonical_bytes
from summary_evaluator.serve_http.api_settings import load_scorer_api_settings
from summary_evaluator.serve_http.contracts.api_settings import ApiSettings
from summary_evaluator.serve_http.emit_events import EventWriter
from summary_evaluator.serve_http.load_scorer_settings import load_unieval_settings
from summary_evaluator.serve_http.serve_api import create_app
from summary_evaluator.shared.exchange_packets import ByteChannel
from summary_evaluator.unieval.contracts.unieval_recording import (
    UnievalRecordingInputs,
    UnievalRecordingPredictions,
)
from summary_evaluator.unieval.contracts.unieval_result import UnievalModelIdentity
from summary_evaluator.unieval.contracts.unieval_settings import UnievalSettings
from summary_evaluator.unieval.load_unieval_resources import (
    UnievalResources,
    load_unieval_resources,
)
from summary_evaluator.unieval.maintain_unieval_worker import UnievalSupervisor
from summary_evaluator.unieval.unieval_worker import run_unieval_worker


def read_unieval_inputs() -> UnievalRecordingInputs:
    return UnievalRecordingInputs.model_validate_json(
        (REPOSITORY / "tests" / "fixtures" / "unieval-evaluator" / "model-inputs.json").read_bytes()
    )


def read_unieval_recordings() -> tuple[
    UnievalRecordingInputs, UnievalRecordingPredictions, UnievalModelIdentity
]:
    directory = REPOSITORY / "tests" / "fixtures" / "unieval-evaluator"
    try:
        inputs = read_unieval_inputs()
        predictions = UnievalRecordingPredictions.model_validate_json(
            (directory / "model-predictions.json").read_bytes()
        )
        identity = UnievalModelIdentity.model_validate_json(
            (directory / "model-identity.json").read_bytes()
        )
    except FileNotFoundError:
        raise AssertionError(
            "Capture actual UniEval fixtures with scripts/capture-unieval-recordings.py "
            "in the frozen model environment; predictions cannot be invented."
        ) from None
    assert (
        predictions.model_identity_sha256
        == hashlib.sha256(canonical_bytes(identity.model_dump(mode="json"))).hexdigest()
    ), "The recorded predictions and model identity do not belong together."
    assert len(inputs.cases) == len(predictions.cases)
    assert len({case.id for case in inputs.cases}) == len(inputs.cases)
    for case, recorded in zip(inputs.cases, predictions.cases, strict=True):
        assert case.id == recorded.id
        assert (
            recorded.input_sha256
            == hashlib.sha256(canonical_bytes(case.model_dump(mode="json"))).hexdigest()
        ), "Recapture actual predictions after changing the named inputs."
    return inputs, predictions, identity


def unieval_settings(
    *, api: ApiSettings | None = None, **scoring: object
) -> tuple[ApiSettings, UnievalSettings]:
    api = api or load_scorer_api_settings(
        REPOSITORY / "config" / "summary-evals" / "api.json", "unieval"
    )
    inputs = read_unieval_inputs()
    settings = load_unieval_settings(REPOSITORY, api)
    controls = inputs.cases[0].controls.model_copy(update=scoring)
    settings = UnievalSettings.model_validate_json(
        settings.model_copy(update={"scoring": controls}).model_dump_json()
    )
    return api, settings


@dataclass(frozen=True)
class UnievalScenario:
    invalid_at: int | None = None
    fail_at: int | None = None
    block_at: int | None = None
    crash_at: int | None = None
    load_failure: bool = False


@dataclass
class RecordedUnievalPredictor:
    identity: UnievalModelIdentity
    resources: UnievalResources
    predictions: dict[str, float]
    scenario: UnievalScenario
    calls: int = 0

    def score(self, prompt: str) -> float:
        current = self.calls
        self.calls += 1
        if self.scenario.block_at == current:
            threading.Event().wait()
        if self.scenario.crash_at == current:
            os._exit(17)
        if self.scenario.fail_at == current:
            raise RuntimeError("PrivateModelFailureCanary")
        if self.scenario.invalid_at == current:
            return float("nan")
        key = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        if key not in self.predictions:
            raise AssertionError("This exact UniEval prompt has no captured model prediction.")
        return self.predictions[key]


@dataclass(frozen=True)
class RecordedUnievalLoader:
    scenario: UnievalScenario

    def __call__(self, settings: UnievalSettings, root: Path) -> RecordedUnievalPredictor:
        if self.scenario.load_failure:
            raise ValueError("PrivateModelLoadFailureCanary")
        _, predictions, identity = read_unieval_recordings()
        assert identity.loaded_revision == settings.assets.model.revision
        return RecordedUnievalPredictor(
            identity,
            load_unieval_resources(settings, root),
            {
                prediction.prompt_sha256: prediction.score
                for case in predictions.cases
                for prediction in case.comparisons
            },
            self.scenario,
        )


def run_recorded_unieval_worker(
    channel: ByteChannel,
    lifetime: ByteChannel,
    root: Path,
    generation: int,
    command_limit: int,
    scenario: UnievalScenario,
) -> None:
    run_unieval_worker(
        channel,
        lifetime,
        root,
        generation,
        command_limit,
        loader=RecordedUnievalLoader(scenario),
    )


class RecordedUnievalSupervisor(UnievalSupervisor):
    def __init__(self, settings: UnievalSettings, scenario: UnievalScenario | None = None) -> None:
        super().__init__(settings, REPOSITORY)
        self.scenario = scenario or UnievalScenario()

    def _create_process(
        self, channel: ByteChannel, lifetime: ByteChannel, generation: int
    ) -> BaseProcess:
        return multiprocessing.get_context("spawn").Process(
            target=run_recorded_unieval_worker,
            args=(channel, lifetime, self.root, generation, self.command_limit, self.scenario),
            daemon=False,
        )


@asynccontextmanager
async def running_unieval(
    *,
    settings: UnievalSettings | None = None,
    scenario: UnievalScenario | None = None,
    log_directory: Path | None = None,
) -> AsyncIterator[tuple[httpx.AsyncClient, RecordedUnievalSupervisor, io.StringIO]]:
    api, selected = unieval_settings()
    selected = settings or selected
    worker = RecordedUnievalSupervisor(selected, scenario)
    stream = io.StringIO()
    events = EventWriter(api.logging, stream, directory=log_directory)
    app = create_app(
        api,
        None,
        REPOSITORY,
        writer=events,
        unieval_settings=selected,
        unieval_supervisor=worker,
    )
    async with app.router.lifespan_context(app):
        await app.state.unieval.loading_task
        assert (await app.state.unieval.health()).status == "ready", stream.getvalue()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app),
            base_url=httpx.URL(
                scheme="http", host=api.listener.host, port=api.listener.port,
            ),
            trust_env=False,
        ) as client:
            yield client, worker, stream
    assert worker.exit_confirmed
