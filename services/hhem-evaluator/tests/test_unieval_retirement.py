"""Do concurrent health and admission observers wait for the real worker retirement?"""

import asyncio

import httpx
import pytest

from hhem_evaluator.contracts.unieval_result import UnievalResult
from hhem_evaluator.fail_unieval import UnievalFailure
from hhem_evaluator.unieval_router import UNIEVAL_HEALTH_PATH, UNIEVAL_PATH

from .unieval_cases import running_unieval


@pytest.mark.parametrize("cleanup_failure", [False, True])
def test_concurrent_observers_share_join_confirmation_and_cleanup_errors(
    cleanup_failure: bool,
) -> None:
    async def check() -> None:
        async with running_unieval() as (client, worker, _):
            assert worker.process is not None and worker.lifetime is not None
            process = worker.process
            pid = process.pid
            worker.lifetime.close()
            await asyncio.to_thread(process.join, worker.settings.worker.stop_grace_ms / 1000)
            assert not process.is_alive() and process.exitcode == 0

            async def observe(
                kind: str,
            ) -> tuple[httpx.Response, bool, tuple[int, int] | None]:
                if kind == "admission":
                    response = await client.post(
                        UNIEVAL_PATH, content=b"{}", headers={"Content-Type": "application/json"}
                    )
                else:
                    response = await client.get(
                        UNIEVAL_HEALTH_PATH if kind == "component" else "/health"
                    )
                return response, worker.exit_confirmed, worker.last_exit

            component = asyncio.create_task(observe("component"))
            # Enter retirement before the other observers, without a wall-clock delay.
            await asyncio.sleep(0)
            if cleanup_failure:
                process.close()
            observed = await asyncio.gather(component, observe("shared"), observe("admission"))
            component_response, shared_response, admission_response = [
                result[0] for result in observed
            ]
            expected_code = "WORKER_STOP_FAILED" if cleanup_failure else "WORKER_EXITED"
            assert component_response.status_code == shared_response.status_code == 503
            assert component_response.json()["failure_code"] == expected_code
            assert shared_response.json()["unieval"]["failure_code"] == expected_code
            assert admission_response.status_code == 500
            result = UnievalResult.model_validate_json(admission_response.content)
            assert result.errors[0].code == expected_code
            if not cleanup_failure:
                assert all(
                    confirmed and last_exit == (pid, 0) for _, confirmed, last_exit in observed
                )

    if cleanup_failure:
        with pytest.raises(UnievalFailure) as failure:
            asyncio.run(check())
        assert failure.value.error.code == "WORKER_STOP_FAILED"
    else:
        asyncio.run(check())
