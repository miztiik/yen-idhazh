"""Compose separate native ASGI apps for caller tests without claiming API process isolation."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

import httpx
from summary_eval_pipeline.evaluation import read_owned_health
from summary_eval_pipeline.phase_services import ScorerService
from summary_eval_pipeline.settings import load_pipeline_settings
from summary_evaluator.hhem.contracts.service_settings import ServiceSettings
from summary_evaluator.unieval.contracts.unieval_settings import UnievalSettings
from summary_evaluator_cases.contract_examples import REPOSITORY
from summary_evaluator_cases.replay_predictions import Scenario
from summary_evaluator_cases.service_cases import ServiceCase, running_service, service_settings
from summary_evaluator_cases.unieval_cases import (
    RecordedUnievalSupervisor,
    UnievalScenario,
    unieval_settings,
)


class ScorerTransport(httpx.AsyncBaseTransport):
    """Send each authored origin only to its real native ASGI app, never to a network."""

    def __init__(self, hhem: ServiceCase, unieval: ServiceCase) -> None:
        self.transports = {
            (case.app.state.api_settings.listener.host, case.app.state.api_settings.listener.port):
            httpx.ASGITransport(case.app)
            for case in (hhem, unieval)
        }
        if len(self.transports) != 2:
            raise ValueError("Caller tests require separately selected scorer listeners")
        self.requests: list[httpx.Request] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        key = (request.url.host, request.url.port)
        if request.url.scheme != "http" or key not in self.transports:
            raise AssertionError("The caller selected an origin outside its authored scorers")
        self.requests.append(request)
        return await self.transports[key].handle_async_request(request)

    async def aclose(self) -> None:
        for transport in self.transports.values():
            await transport.aclose()


@dataclass
class ScorerCallerCase:
    hhem: ServiceCase
    unieval: ServiceCase
    unieval_worker: RecordedUnievalSupervisor
    apis: tuple[ScorerService, ScorerService]
    client: httpx.AsyncClient
    transport: ScorerTransport


@asynccontextmanager
async def running_scorers(
    settings: ServiceSettings | None = None,
    scenarios: tuple[Scenario, ...] = (Scenario(),),
    *,
    selected_unieval: UnievalSettings | None = None,
    unieval_scenario: UnievalScenario | None = None,
    unieval_supervisor: RecordedUnievalSupervisor | None = None,
    wait_ready: bool = True,
) -> AsyncIterator[ScorerCallerCase]:
    selected_hhem = settings or service_settings()
    if selected_unieval is None:
        _, selected_unieval = unieval_settings()
    worker = unieval_supervisor or RecordedUnievalSupervisor(selected_unieval, unieval_scenario)
    async with (
        running_service(selected_hhem, scenarios, routes=("hhem",), wait_ready=wait_ready) as hhem,
        running_service(
            selected_hhem,
            routes=("unieval",),
            unieval_settings=selected_unieval,
            unieval_supervisor=worker,
            wait_ready=wait_ready,
        ) as unieval,
    ):
        apis = (
            ScorerService("hhem", hhem.app.state.api_settings, selected_hhem.worker),
            ScorerService("unieval", unieval.app.state.api_settings, selected_unieval.worker),
        )
        transport = ScorerTransport(hhem, unieval)
        async with httpx.AsyncClient(
            transport=transport, trust_env=False, follow_redirects=False,
        ) as client:
            if wait_ready:
                for api, case in zip(apis, (hhem, unieval), strict=True):
                    api.health = await read_owned_health(
                        client, api.origin, case.app.state.service_instance_id,
                        api.worker_settings, load_pipeline_settings(REPOSITORY), api.scorer,
                    )
            yield ScorerCallerCase(hhem, unieval, worker, apis, client, transport)
