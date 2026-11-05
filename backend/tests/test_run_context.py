"""Do tests isolate the runner attempt while retaining explicit reruns?"""

import pytest

from idhazh.run_context import FIRST_ATTEMPT, run_attempt


def test_the_runner_attempt_does_not_leak_into_a_test() -> None:
    assert run_attempt() == FIRST_ATTEMPT


def test_a_test_can_explicitly_choose_a_rerun(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "2")
    assert run_attempt() == 2
