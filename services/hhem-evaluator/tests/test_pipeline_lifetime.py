"""Preserve private channels, parent-loss deadlines and trustworthy worker-exit receipts."""

from typing import Literal

import pytest
from summary_eval_pipeline.control import StartupPacket
from summary_eval_pipeline.failures import WorkflowFailure
from summary_eval_pipeline.services import OwnedService
from summary_eval_pipeline.settings import load_pipeline_settings

from hhem_evaluator.contracts.base import SCHEMA_VERSION
from hhem_evaluator.contracts.service_settings import StartupContext

from .contract_examples import REPOSITORY, REQUEST_ID
from .pipeline_cases import owned_child_command
from .service_cases import service_settings


def start_child(service: Literal["hhem", "host"], mode: str) -> OwnedService:
    return OwnedService(
        service,
        owned_child_command(mode),
        REPOSITORY,
        StartupPacket(version=SCHEMA_VERSION, startup_id=REQUEST_ID, context=StartupContext()),
        service_settings(
            worker={
                "stop_grace_ms": 500,
                "forced_stop_ms": 1000,
                "shutdown_timeout_ms": 1500,
            }
        ),
        load_pipeline_settings(REPOSITORY),
    )


@pytest.mark.parametrize("mode", ["clean", "mismatch", "early_exit", "blocked_close"])
def test_only_owned_children_are_joined_even_when_readiness_or_close_fails(mode: str) -> None:
    child = start_child("host", mode)
    try:
        if mode in ("mismatch", "early_exit"):
            with pytest.raises(WorkflowFailure) as failure:
                child.wait_ready(10000)
            assert failure.value.error.code == (
                "STARTUP_IDENTITY_MISMATCH" if mode == "mismatch" else "CHILD_EXITED"
            )
        else:
            ready = child.wait_ready(10000)
            assert ready.pid == child.process.pid and child.process.poll() is None
    finally:
        if mode in ("early_exit", "blocked_close"):
            with pytest.raises(WorkflowFailure):
                child.close(100 if mode == "blocked_close" else 1500)
        else:
            assert child.close(1500).clean
        assert child.process.poll() is not None


@pytest.mark.parametrize("blocked", [False, True])
def test_actual_api_parent_watcher_closes_or_exits_its_own_child(blocked: bool) -> None:
    child = start_child("host", "parent_loss_blocked" if blocked else "parent_loss")
    child.wait_ready(10000)
    assert child.process.stdin is not None
    child.process.stdin.close()
    child.process.wait(timeout=5)
    if blocked:
        with pytest.raises(WorkflowFailure):
            child.close(1000)
        assert child.process.returncode == 1
    else:
        assert child.close(1000).clean
        assert child.process.returncode == 0


def test_invalid_child_diagnostics_fail_without_forwarding_raw_output(
    capsys: pytest.CaptureFixture[str],
) -> None:
    child = start_child("hhem", "invalid_event")
    try:
        with pytest.raises(WorkflowFailure) as failure:
            child.wait_ready(10000)
            assert child.events_failed.wait(5)
            child.check_alive()
        assert failure.value.error.code == "EVENT_STREAM_FAILED"
    finally:
        with pytest.raises(WorkflowFailure):
            child.close(1500)
    assert child.process.poll() is not None
    assert "PrivateRawChildCanary" not in str(capsys.readouterr())


def test_inherited_output_cannot_corrupt_a_private_shutdown_receipt(
    capsys: pytest.CaptureFixture[str],
) -> None:
    child = start_child("hhem", "raw_inherited_output")
    child.wait_ready(10000)
    stopped = child.close(6000)
    assert stopped.clean and stopped.worker_exit_confirmed is True
    assert child.process.poll() == 0
    output = str(capsys.readouterr())
    assert "PrivateInheritedOutputCanary" not in output
    assert "PrivateInheritedErrorCanary" not in output


@pytest.mark.parametrize(
    ("mode", "confirmed"), [("unclean_stop", True), ("unconfirmed_stop", False)]
)
def test_unclean_shutdown_preserves_an_observed_worker_exit(mode: str, confirmed: bool) -> None:
    child = start_child("hhem", mode)
    child.wait_ready(10000)
    with pytest.raises(WorkflowFailure) as failure:
        child.close(6000)
    assert failure.value.error.code == "SERVICE_STOP_FAILED"
    assert child.process.poll() == 0
    assert child.stopped is not None and child.stopped.worker_exit_confirmed is confirmed
    assert not child.protocol_failed.is_set() and not child.events_failed.is_set()
