"""Do the live judge's existing paths route into one trial and return to production?"""

from pathlib import Path

import pytest

from idhazh.content_similarity_judge import tenant
from idhazh.council import session, trial_paths


def test_live_judge_scratch_and_settlement_inputs_use_the_trial_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(session, "COUNCIL_ROOT", tmp_path / "council")
    root = trial_paths.root(session.COUNCIL_ROOT, run_id="2026-10-11-123", judge_id=tenant.JUDGE_ID)
    day = "2026-10-10"
    public = tmp_path / "frontend" / "public"
    with trial_paths.route(root):
        assert tenant._draw_path(day).is_relative_to(root / "scratch")
        assert tenant._verdict_path(day, shard=0).is_relative_to(root / "scratch")
        assert tenant._verdicts_dir(day).is_relative_to(root / "scratch")
        assert tenant._shipping_dir(day).is_relative_to(root / "scratch")
        assert session.outcomes_dir(day).is_relative_to(root / "scratch")
        assert trial_paths.public_root(public) == root / "frontend" / "public"
    assert tenant._draw_path(day).is_relative_to(session.COUNCIL_ROOT / day)
    assert trial_paths.public_root(public) == public


def test_trial_attempts_never_share_a_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "1")
    first = trial_paths.root(tmp_path, run_id="2026-10-11-123", judge_id="paused-judge")
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "2")
    second = trial_paths.root(tmp_path, run_id="2026-10-11-123", judge_id="paused-judge")
    assert first != second


@pytest.mark.parametrize("run", ["../escape", "2026-02-30-123", "2026-10-11-1/other"])
def test_trial_roots_refuse_unsafe_or_invalid_runs(tmp_path: Path, run: str) -> None:
    with pytest.raises(ValueError):
        trial_paths.root(tmp_path, run_id=run, judge_id="paused-judge")
