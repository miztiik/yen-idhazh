"""Run the production owned API lifespan and native recorded scoring over private test barriers."""

import asyncio
import json
import os
import sys
import threading
import time
from pathlib import Path

import httpx
from fastapi import FastAPI
from pydantic import BaseModel
from summary_eval_pipeline.channels import open_owned_channels
from summary_eval_pipeline.http import loopback_url
from summary_eval_pipeline.scorer_control import ScorerStartupPacket
from summary_eval_pipeline.serve_scorer_lifetime import serve_scorer_lifetime
from summary_eval_pipeline.settings import load_pipeline_settings
from summary_evaluator.hhem.contracts.evaluate_request import EvaluateRequest
from summary_evaluator.serve_http.api_settings import load_scorer_api_settings
from summary_evaluator.serve_http.configure_server import report_startup_failure
from summary_evaluator.serve_http.contracts.api_health import ApiHealth
from summary_evaluator.serve_http.contracts.api_settings import ApiComponent, ApiSettings
from summary_evaluator.serve_http.emit_events import EventWriter
from summary_evaluator.serve_http.serve_api import create_app
from summary_evaluator.shared.contracts.api_paths import (
    API_HEALTH_PATH,
    EVALUATE_PATH,
)
from summary_evaluator.shared.read_process_identity import read_owned_process_identity
from summary_evaluator.unieval.unieval_router import UNIEVAL_PATH
from summary_evaluator_cases.replay_predictions import Scenario, read_recordings
from summary_evaluator_cases.service_cases import RecordedSupervisor, service_settings
from summary_evaluator_cases.unieval_cases import (
    RecordedUnievalSupervisor,
    read_unieval_inputs,
    unieval_settings,
)


def recorded_app(
    root: Path, packet: ScorerStartupPacket, events: EventWriter
) -> tuple[ApiSettings, FastAPI]:
    api = load_scorer_api_settings(root / "config" / "summary-evals" / "api.json", packet.scorer)
    if packet.scorer == "hhem":
        hhem = service_settings().model_copy(
            update={"listener": api.listener, "logging": api.logging}
        )
        return api, create_app(
            api, hhem, root, packet.startup.context,
            supervisor=RecordedSupervisor(hhem, (Scenario(),)), writer=events,
        )
    _, unieval = unieval_settings()
    unieval = unieval.model_copy(update={"listener": api.listener, "logging": api.logging})
    return api, create_app(
        api, None, root, packet.startup.context, writer=events,
        unieval_settings=unieval, unieval_supervisor=RecordedUnievalSupervisor(unieval),
    )


def native_request(root: Path, scorer: ApiComponent) -> tuple[str, BaseModel]:
    if scorer == "hhem":
        inputs, _, _ = read_recordings(root)
        case = inputs.cases[0]
        return EVALUATE_PATH, EvaluateRequest(
            source_text=case.source_text, summary_text=case.summary_text
        )
    return UNIEVAL_PATH, read_unieval_inputs().cases[0].request


def save_observation(path: Path, value: dict[str, object]) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value), encoding="utf-8")
    temporary.replace(path)


async def record_journey(
    root: Path, directory: Path, api: ApiSettings, app: FastAPI, scorer: ApiComponent
) -> None:
    pipeline = load_pipeline_settings(root)
    runtime = app.state.components[scorer]
    deadline = time.monotonic() + runtime.worker_settings.startup_timeout_ms / 1000
    path, request = native_request(root, scorer)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app),
        base_url=loopback_url(api.listener.host, api.listener.port),
        trust_env=False,
        follow_redirects=False,
    ) as client:
        while True:
            health_response = await client.get(API_HEALTH_PATH)
            health = ApiHealth.model_validate_json(health_response.content)
            if health_response.status_code == 200 and health.status == "ready":
                break
            if time.monotonic() >= deadline:
                raise RuntimeError("Recorded scorer did not become ready")
            await asyncio.sleep(pipeline.poll_interval_ms / 1000)

        async def observe(destination: str) -> None:
            response = await client.post(
                path, content=request.model_dump_json(),
                headers={"content-type": "application/json"},
            )
            if response.status_code != 200:
                raise RuntimeError("Recorded native operation did not complete")
            observed = await client.get(API_HEALTH_PATH)
            validated = ApiHealth.model_validate_json(observed.content)
            identity = read_owned_process_identity(
                os.getpid(), runtime.worker_settings.max_proc_identity_bytes
            )
            save_observation(
                directory / destination,
                {
                    "process": identity.model_dump(mode="json"),
                    "health": validated.model_dump(mode="json"),
                    "result": response.json(),
                },
            )

        await observe("before.json")
        deadline = time.monotonic() + pipeline.native_startup_timeout_ms / 1000
        while not (directory / "continue.txt").is_file():
            if time.monotonic() >= deadline:
                raise RuntimeError("The bounded isolation barrier was not released")
            await asyncio.sleep(pipeline.poll_interval_ms / 1000)
        await observe("after.json")


def main() -> None:
    root, directory = Path(sys.argv[2]).resolve(), Path(sys.argv[3]).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    with open_owned_channels() as channels:
        try:
            controls = load_pipeline_settings(root)
            line = sys.stdin.buffer.readline(controls.control_max_bytes + 1)
            if len(line) > controls.control_max_bytes or not line.endswith(b"\n"):
                raise ValueError("Invalid owned test startup")
            packet = ScorerStartupPacket.model_validate_json(line)
            if packet.scorer != sys.argv[1]:
                raise ValueError("The test child must start its selected scorer")
            api = load_scorer_api_settings(
                root / "config" / "summary-evals" / "api.json", packet.scorer
            )
            events = EventWriter(
                api.logging, channels.events, directory=directory / "logs", scorer=packet.scorer
            )
            api, app = recorded_app(root, packet, events)
            finished, announced = threading.Event(), threading.Event()

            async def run() -> None:
                lifetime = asyncio.create_task(
                    serve_scorer_lifetime(app, api, packet, finished, channels, [], announced)
                )
                journey = asyncio.create_task(
                    record_journey(root, directory, api, app, packet.scorer)
                )
                try:
                    done, _ = await asyncio.wait(
                        (lifetime, journey), return_when=asyncio.FIRST_COMPLETED
                    )
                    if journey in done:
                        await journey
                    await lifetime
                finally:
                    for task in (lifetime, journey):
                        task.cancel()
                    await asyncio.gather(lifetime, journey, return_exceptions=True)
                    events.close()

            asyncio.run(run())
            finished.set()
        except (Exception, SystemExit):
            report_startup_failure("SCORER_RECORDING_FAILED", channels.events)
            os._exit(1)


if __name__ == "__main__":
    main()
