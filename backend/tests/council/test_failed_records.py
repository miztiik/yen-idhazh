"""Do raised units file once while preserving exceptions, siblings and safe events?"""

from __future__ import annotations

import logging
import time
from pathlib import Path

import pytest

from idhazh import config, ledger
from idhazh.contracts.council_run_record import CouncilRunRecord, EvaluationStep, ShardOutcome
from idhazh.contracts.ledger_name import LedgerName
from idhazh.council import metrics_sink, outcome, registry, session
from idhazh.council.tenancy import ShardResult

from ._tenants import TENANT_SOURCE, a_venue, forget
from .test_events import DATE, HOSTILE, RUN, lines
from .test_publication import configuration

PACKAGE = "failed_record_judges"


@pytest.mark.parametrize(
    ("step", "statement"),
    [
        (EvaluationStep.SELECT_JUDGE_WORK, "self.prepared.append(date)"),
        (EvaluationStep.EVALUATE_WORK_PART, "self.ran.append((date, run_id, shard, shards))"),
        (EvaluationStep.COMBINE_JUDGE_RESULTS, "self.settled.append(date)"),
    ],
)
def test_each_raising_path_files_one_row_and_preserves_earlier_work(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
    step: EvaluationStep, statement: str,
) -> None:
    source = TENANT_SOURCE.replace(
        f"        {statement}",
        f"        {statement}\n"
        f"        if self.judge_id == 'raised-judge':\n"
        f"            raise RuntimeError({HOSTILE!r})",
    )
    a_venue(
        tmp_path, package=PACKAGE,
        slugs={"first-judge": (1, ()), "raised-judge": (1, ()), "last-judge": (1, ())},
        source=source,
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(registry, "TENANT_PACKAGE", PACKAGE)
    monkeypatch.setattr(session, "COUNCIL_ROOT", tmp_path / "scratch")
    council = config.load_council(configuration(tmp_path, ("first-judge", "raised-judge", "last-judge")))
    forget(PACKAGE)
    try:
        with caplog.at_level(logging.INFO), pytest.raises(RuntimeError, match="SOURCE-TEXT"):
            if step is EvaluationStep.SELECT_JUDGE_WORK:
                session.prepare(council, date=DATE, run_id=RUN)
            elif step is EvaluationStep.EVALUATE_WORK_PART:
                for slug in council.running():
                    session.run_shard(
                        council, slug=slug, date=DATE, run_id=RUN, shard=0, shards=1,
                        started=time.monotonic(),
                    )
            else:
                session.settle(
                    council, date=DATE, run_id=RUN, state_dir=tmp_path / "state",
                    commit_sha="a" * 40,
                )
        (row,) = metrics_sink.shipped_rows(
            session.outcomes_dir(DATE), judge_id="raised-judge", contract=CouncilRunRecord,
        )
        assert (row.evaluation_step, row.outcome, row.fault) == (step, ShardOutcome.FAILED, "raised")
        assert row.model_calls is None and row.tokens_in is None and row.tokens_out is None
        assert row.model_seconds is None
        (sibling,) = metrics_sink.shipped_rows(
            session.outcomes_dir(DATE), judge_id="first-judge", contract=CouncilRunRecord,
        )
        assert sibling.fault is None and sibling.outcome is not ShardOutcome.FAILED
        failed = [event for event in lines(caplog) if event.get("outcome") == "failed"]
        assert len(failed) == 1 and "SOURCE-TEXT" not in str(lines(caplog))
        if step is EvaluationStep.COMBINE_JUDGE_RESULTS:
            persisted = ledger.load_days(
                tmp_path / "state", LedgerName.COUNCIL_RUN_RECORDS, [DATE], model=CouncilRunRecord,
            )
            assert len(persisted) == 3
            assert sum(item.outcome is ShardOutcome.FAILED for item in persisted) == 1
    finally:
        forget(PACKAGE)


@pytest.mark.parametrize("error_type", [RuntimeError, KeyboardInterrupt, SystemExit])
def test_work_and_filing_failures_escape_together_without_a_success_event(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
    error_type: type[BaseException],
) -> None:
    monkeypatch.setattr(session, "COUNCIL_ROOT", tmp_path / "scratch")
    blocked = session.outcomes_dir(DATE)
    blocked.parent.mkdir(parents=True)
    blocked.write_text("blocked\n", encoding="ascii", newline="\n")
    original = error_type(HOSTILE)

    def raise_work() -> ShardResult:
        raise original

    with caplog.at_level(logging.INFO), pytest.raises(BaseExceptionGroup) as raised:
        session._recorded(
            "raised-judge", date=DATE, run_id=RUN,
            evaluation_step=EvaluationStep.SELECT_JUDGE_WORK,
            work_part_index=None, work_part_count=1, work=raise_work,
        )
    assert raised.value.exceptions[0] is original
    assert isinstance(raised.value.exceptions[1], OSError)
    assert len(raised.value.exceptions) == 2
    if error_type is RuntimeError:
        assert isinstance(raised.value, ExceptionGroup)
    (event,) = lines(caplog)
    assert event["outcome"] == "failed" and "SOURCE-TEXT" not in str(event)
    assert blocked.read_text(encoding="ascii") == "blocked\n"


def test_a_returned_failed_result_cannot_claim_an_exception_that_never_happened(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(session, "COUNCIL_ROOT", tmp_path)

    def return_failure() -> ShardResult:
        return ShardResult(outcome=ShardOutcome.FAILED, model_calls=99)

    with pytest.raises(ValueError, match="requires a raised unit"):
        session._recorded(
            "raised-judge", date=DATE, run_id=RUN,
            evaluation_step=EvaluationStep.SELECT_JUDGE_WORK,
            work_part_index=None, work_part_count=1, work=return_failure,
        )
    (row,) = metrics_sink.shipped_rows(
        session.outcomes_dir(DATE), judge_id="raised-judge", contract=CouncilRunRecord,
    )
    assert row.fault == "raised" and row.model_calls is None
    assert outcome.of_results((ShardResult(outcome=ShardOutcome.FAILED),)) == 1
