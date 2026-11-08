"""Does restarting an actual API process leave a sibling API, worker and result intact?"""

import ast
import contextlib
import json
import sys
import time
from pathlib import Path

import pytest
from local_api_host.propagate_trace_context import (
    OperationMetadata,
    create_child_operation,
    create_root_operation,
)
from summary_eval_pipeline.contracts import WORKFLOW_VERSION
from summary_eval_pipeline.control import StartupPacket
from summary_eval_pipeline.failures import WorkflowError
from summary_eval_pipeline.scorer_control import (
    SCORER_CONTROL_VERSION,
    ScorerReady,
    ScorerStartupPacket,
    ScorerStopped,
)
from summary_eval_pipeline.serve_api import create_argument_parser
from summary_eval_pipeline.services import OwnedService
from summary_eval_pipeline.settings import load_pipeline_settings
from summary_evaluator.serve_http.api_settings import load_scorer_api_settings
from summary_evaluator.serve_http.contracts.api_settings import ApiComponent
from summary_evaluator.shared.contracts.service_settings import StartupContext
from summary_evaluator.shared.create_execution_id import create_execution_id
from summary_evaluator_cases.contract_examples import REPOSITORY
from summary_evaluator_cases.service_cases import service_settings

from summary_eval_tests.pipeline_cases import owned_child_command
from summary_eval_tests.test_pipeline_lifetime import CHILD_STARTUP_MS


def start_scorer(
    scorer: ApiComponent, directory: Path, *, operation_metadata: OperationMetadata | None = None
) -> OwnedService:
    api = load_scorer_api_settings(REPOSITORY / "config" / "summary-evals" / "api.json", scorer)
    command = [
        *owned_child_command(
            scorer, script_path=Path(__file__).with_name("owned_scorer_child.py")
        ),
        str(REPOSITORY),
        str(directory),
    ]
    return OwnedService(
        "api", command, REPOSITORY,
        ScorerStartupPacket(
            version=SCORER_CONTROL_VERSION, scorer=scorer,
            operation_metadata=create_child_operation(
                operation_metadata or create_root_operation()
            ),
            startup=StartupPacket(
                version=WORKFLOW_VERSION, startup_id=create_execution_id(),
                context=StartupContext(),
            ),
        ),
        service_settings().worker,
        load_pipeline_settings(REPOSITORY),
        api_settings=api,
    )


def read_observation(child: OwnedService, path: Path) -> dict[str, object]:
    deadline = time.monotonic() + CHILD_STARTUP_MS / 1000
    while not path.is_file():
        child.check_alive()
        if time.monotonic() >= deadline:
            raise AssertionError("The native recorded operation did not reach its test barrier")
        time.sleep(child.manual.poll_interval_ms / 1000)
    with path.open("rb") as stream:
        encoded = stream.read(child.manual.max_response_bytes + 1)
    assert len(encoded) <= child.manual.max_response_bytes
    value: dict[str, object] = json.loads(encoded)
    return value


def test_owned_caller_arguments_are_accepted_by_the_actual_private_entrypoint() -> None:
    source = (
        REPOSITORY / "tools" / "summary-eval"
        / "summary_eval_pipeline" / "phases.py"
    )
    module = ast.parse(source.read_text(encoding="utf-8"))
    calls = [
        node for node in ast.walk(module)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "OwnedService"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and node.args[0].value == "api"
    ]
    assert len(calls) == 1
    command = calls[0].args[1]
    assert isinstance(command, ast.List)
    flags = [
        part.value for part in command.elts
        if isinstance(part, ast.Constant)
        and isinstance(part.value, str)
        and part.value.startswith("--")
    ]
    args = create_argument_parser().parse_args(
        [argument for flag in flags for argument in (flag, "configuration")]
    )
    assert args.root == Path("configuration")


@pytest.mark.skipif(
    sys.platform != "linux", reason="Actual owned API-process and start-pin proof runs on Linux"
)
@pytest.mark.parametrize("scorer", ["hhem", "unieval"])
def test_restarting_one_api_preserves_its_sibling_api_worker_and_completed_result(
    scorer: ApiComponent, tmp_path: Path
) -> None:
    siblings: dict[ApiComponent, ApiComponent] = {
        "hhem": "unieval", "unieval": "hhem"
    }
    first_directory, sibling_directory = tmp_path / "first", tmp_path / "sibling"
    first, sibling = start_scorer(scorer, first_directory), start_scorer(
        siblings[scorer], sibling_directory
    )
    owned = [first, sibling]
    try:
        ready, sibling_ready = first.wait_ready(CHILD_STARTUP_MS), sibling.wait_ready(
            CHILD_STARTUP_MS
        )
        assert isinstance(ready, ScorerReady) and isinstance(sibling_ready, ScorerReady)
        assert ready.pid != sibling_ready.pid
        assert ready.process.start_ticks is not None
        assert ready.service_instance_id != sibling_ready.service_instance_id
        initial = read_observation(first, first_directory / "before.json")
        retained = read_observation(sibling, sibling_directory / "before.json")
        original_bytes = (sibling_directory / "before.json").read_bytes()
        stopped = first.close(CHILD_STARTUP_MS)
        assert isinstance(stopped, ScorerStopped)
        assert stopped.worker_exit.confirmed is True
        assert first.process.poll() == 0 and sibling.process.poll() is None

        restarted_directory = tmp_path / "restarted"
        restarted = start_scorer(scorer, restarted_directory)
        owned.append(restarted)
        restarted_ready = restarted.wait_ready(CHILD_STARTUP_MS)
        assert isinstance(restarted_ready, ScorerReady)
        assert restarted_ready.pid != ready.pid
        assert restarted_ready.service_instance_id != ready.service_instance_id
        again = read_observation(restarted, restarted_directory / "before.json")
        assert initial["process"] != again["process"]
        (sibling_directory / "continue.txt").write_text("continue", encoding="ascii")
        after = read_observation(sibling, sibling_directory / "after.json")
        assert retained["process"] == after["process"]
        assert retained["health"] == after["health"]
        assert sibling.ready == sibling_ready and sibling.process.poll() is None
        assert (sibling_directory / "before.json").read_bytes() == original_bytes
        retained_health = retained["health"]
        assert isinstance(retained_health, dict)
        assert retained_health["enabled_routes"] == [siblings[scorer]]
        for name in ("hhem", "unieval"):
            if name != siblings[scorer]:
                observation = retained_health[name]
                assert isinstance(observation, dict)
                assert observation["status"] == "disabled"
    finally:
        for child in owned:
            if not child.closed:
                with contextlib.suppress(WorkflowError):
                    child.close(CHILD_STARTUP_MS)
            assert child.process.poll() is not None
