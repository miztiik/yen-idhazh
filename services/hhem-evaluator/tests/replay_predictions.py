"""Replay captured predictions only at the production worker's model-call boundary."""

import hashlib
import json
import os
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import AwareDatetime

from hhem_evaluator.contracts.base import NativeContract, NonblankText, SchemaVersion, Score, Sha256
from hhem_evaluator.contracts.model_identity import ModelIdentity
from hhem_evaluator.contracts.service_settings import ServiceSettings
from hhem_evaluator.exchange_packets import ByteChannel
from hhem_evaluator.fingerprint_model import canonical_bytes, settings_digest
from hhem_evaluator.load_model import Predictor
from hhem_evaluator.run_worker import run_worker

type Action = Literal["score", "hold", "block", "crash", "invalid", "raise"]


class ModelInput(NativeContract):
    id: str
    source_text: NonblankText
    summary_text: NonblankText


class ModelInputs(NativeContract):
    version: SchemaVersion
    provenance: str
    cases: tuple[ModelInput, ...]


class RecordedPrediction(NativeContract):
    id: str
    input_sha256: Sha256
    score: Score


class ModelPredictions(NativeContract):
    version: SchemaVersion
    recorded_at: AwareDatetime
    model_identity_sha256: Sha256
    cases: tuple[RecordedPrediction, ...]


def read_recordings(
    root: Path,
) -> tuple[ModelInputs, ModelPredictions, ModelIdentity]:
    directory = root / "tests" / "fixtures" / "hhem-evaluator"
    try:
        inputs = ModelInputs.model_validate_json((directory / "model-inputs.json").read_bytes())
        replies = ModelPredictions.model_validate_json(
            (directory / "model-predictions.json").read_bytes()
        )
        identity = ModelIdentity.model_validate_json(
            (directory / "model-identity.json").read_bytes()
        )
    except FileNotFoundError:
        raise AssertionError(
            "Capture real fixtures with scripts/capture-model-recordings.py in the model "
            "environment before running the offline runtime tests."
        ) from None
    if len({case.id for case in inputs.cases}) != len(inputs.cases):
        raise AssertionError("The model input fixture contains duplicate case identities.")
    if hashlib.sha256(canonical_bytes(identity.model_dump(mode="json"))).hexdigest() != (
        replies.model_identity_sha256
    ):
        raise AssertionError("The predictions and captured model identity do not belong together.")
    if {case.id for case in inputs.cases} != {reply.id for reply in replies.cases}:
        raise AssertionError("The prediction fixture does not cover the named model inputs.")
    if len(replies.cases) != len(inputs.cases):
        raise AssertionError("The prediction fixture contains duplicate case identities.")
    for case, reply in zip(inputs.cases, replies.cases, strict=True):
        expected = hashlib.sha256(
            canonical_bytes([case.source_text, case.summary_text])
        ).hexdigest()
        if case.id != reply.id or expected != reply.input_sha256:
            raise AssertionError("Recapture predictions after changing a model input.")
    return inputs, replies, identity


@dataclass(frozen=True)
class Scenario:
    actions: tuple[Action, ...] = ()
    hold_loading: bool = False
    changed_identity: bool = False


@dataclass
class RecordedPredictor:
    identity: ModelIdentity
    scores: dict[str, float]
    control: ByteChannel
    actions: tuple[Action, ...]
    calls: int = 0

    def score(self, source: str, summary: str) -> float:
        key = hashlib.sha256(canonical_bytes([source, summary])).hexdigest()
        action = self.actions[self.calls] if self.calls < len(self.actions) else "score"
        self.control.send_bytes(json.dumps({"phase": "prediction", "index": self.calls}).encode())
        self.calls += 1
        if action == "hold":
            self.control.recv_bytes(1)
        elif action == "block":
            if sys.platform == "linux":
                import ctypes

                library = ctypes.PyDLL(None)
                while True:
                    library.pause()
            else:
                threading.Event().wait()
        elif action == "crash":
            os._exit(17)
        elif action == "invalid":
            return float("nan")
        elif action == "raise":
            raise RuntimeError(source + summary)
        if key not in self.scores:
            raise AssertionError("No actual prediction exists for this exact source/summary pair.")
        return self.scores[key]


@dataclass
class RecordedLoader:
    control: ByteChannel
    scenario: Scenario

    def __call__(self, settings: ServiceSettings, root: Path, *, local_only: bool) -> Predictor:
        _, predictions, identity = read_recordings(root)
        if (
            identity.reference != settings.hhem.model.reference
            or identity.loaded_revision != settings.hhem.model.revision
            or identity.foundation_reference != settings.hhem.foundation.reference
            or identity.foundation_revision != settings.hhem.foundation.revision
        ):
            raise AssertionError("The recording does not match the selected immutable model.")
        self.control.send_bytes(json.dumps({"phase": "loading", "local_only": local_only}).encode())
        if self.scenario.hold_loading:
            self.control.recv_bytes(1)
        observed = identity.model_copy(update={"service_config_sha256": settings_digest(settings)})
        if self.scenario.changed_identity:
            observed = observed.model_copy(
                update={
                    "loaded_config_sha256": hashlib.sha256(
                        b"changed cached configuration"
                    ).hexdigest()
                }
            )
        return RecordedPredictor(
            observed,
            {reply.input_sha256: reply.score for reply in predictions.cases},
            self.control,
            self.scenario.actions,
        )


def run_recorded_worker(
    channel: ByteChannel,
    lifetime: ByteChannel,
    root: Path,
    generation: int,
    max_command_bytes: int,
    control: ByteChannel,
    scenario: Scenario,
) -> None:
    run_worker(
        channel,
        lifetime,
        root,
        generation,
        max_command_bytes,
        loader=RecordedLoader(control, scenario),
    )
