"""Does the recovery entry point refuse early and publish only after its gates pass?

Each test runs `main` on a real checkout and a real bare origin, with the platform's answer
recorded in memory. A refusal is judged by what did not happen - nothing assembled, nothing
pushed - because a run that refused too late would end in the same exit status once a later
gate failed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

import pytest
from gardener._garden import an_origin, git, quiet_git
from support.paths import CONFIG_DIR

from idhazh import assemble, config
from idhazh.contracts.publication_inventory import PublicationInventory
from idhazh.contracts.run_plan import RunPlan
from idhazh.stages import common
from utilities import digest_recover
from utilities.digest_recovery_download import SourceRun
from utilities.digest_recovery_inputs import restore, unpack

from ._harness import _copy_config
from .test_digest_recovery import saved_inputs

pytestmark = pytest.mark.workflow

#: The recorded source run has one worker that failed, so its items artifact is absent.
FAILED_SHARD: Final = 1

#: A recovery execution that differs from the recorded source run.
RECOVERY_EXECUTION: Final = "99"


@dataclass
class Recovery:
    """A checkout ready to recover one saved day, its origin, and the platform's recorded answer."""

    origin: Path
    repo: Path
    saved: RunPlan
    source_run: SourceRun
    archives: dict[str, bytes]
    asked: list[str] = field(default_factory=list)

    def fetch(self, execution: str) -> tuple[SourceRun, dict[str, bytes], frozenset[int]]:
        """The platform's recorded answer; it remembers which run it was asked about."""
        self.asked.append(execution)
        return self.source_run, self.archives, frozenset({FAILED_SHARD})

    def recover(self, *options: str) -> int:
        return digest_recover.main([str(self.source_run.id), *options], fetch=self.fetch)

    def read_origin_tip(self) -> str:
        return git(self.origin, "rev-parse", "main").strip()

    @property
    def manifest_path(self) -> Path:
        return assemble.day_dir(common.PUBLIC_ROOT, self.saved.date) / "run.json"


@pytest.fixture
def recovery(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Recovery:
    quiet_git(tmp_path, monkeypatch)
    # Without an option the entry point takes its execution from this variable.
    monkeypatch.delenv("GITHUB_RUN_ID", raising=False)
    origin, repo = an_origin(
        tmp_path,
        {
            "seed": "seed\n",
            "frontend/public/publication.json": PublicationInventory(
                version=PublicationInventory.schema_version(),
                dates=[],
            ).to_json(),
        },
    )
    _copy_config(repo / "config")
    gardener_config = "gardener/config/idhazh_gardener.json"
    (repo / "config" / gardener_config).parent.mkdir(parents=True, exist_ok=True)
    (repo / "config" / gardener_config).write_bytes((CONFIG_DIR / gardener_config).read_bytes())
    git(repo, "add", "config")
    git(repo, "commit", "--quiet", "-m", "fixture config")
    git(repo, "push", "--quiet", "origin", "main")
    saved, source_run, archives = saved_inputs(tmp_path, git(repo, "rev-parse", "HEAD").strip())
    # Current code is one commit past the source run's code, as it is when a day is recovered.
    (repo / "current-code").write_text("recovery code\n")
    git(repo, "add", "current-code")
    git(repo, "commit", "--quiet", "-m", "current recovery code")
    monkeypatch.setattr(config, "REPO_ROOT", repo)
    monkeypatch.setattr(common, "VAR_ROOT", repo / "backend" / "var" / "run")
    monkeypatch.setattr(common, "STATE_ROOT", repo / "state")
    monkeypatch.setattr(common, "PUBLIC_ROOT", repo / "frontend" / "public" / "digest")
    monkeypatch.chdir(repo)
    return Recovery(origin, repo, saved, source_run, archives)


def test_restore_only_restores_the_saved_inputs_and_assembles_nothing(
    recovery: Recovery,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Restoring alone, in a second checkout, says where each saved file belongs.
    other = tmp_path / "other"
    git(tmp_path, "clone", "--quiet", str(recovery.origin), str(other))
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    restored = restore(
        other,
        scratch,
        recovery.archives,
        execution=str(recovery.source_run.id),
        attempt=recovery.source_run.run_attempt,
        commit=recovery.source_run.head_sha,
        failed_shards=frozenset({FAILED_SHARD}),
    )
    saved_files = {
        recovery.repo / restored.plan_path: unpack(recovery.archives["plan"])[
            Path(restored.plan_path).name
        ],
        **{
            common.VAR_ROOT / recovery.saved.date / "items" / name: data
            for name, data in unpack(recovery.archives["items-0"]).items()
        },
    }
    assert not any(path.exists() for path in saved_files)

    assert recovery.recover("--restore-only", "--execution", RECOVERY_EXECUTION) == 0

    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 1
    report = json.loads(lines[0])
    assert {key: report[key] for key in ("source_run", "source_commit", "date")} == {
        "source_run": recovery.source_run.id,
        "source_commit": recovery.source_run.head_sha,
        "date": recovery.saved.date,
    }
    for path, data in saved_files.items():
        assert path.read_bytes() == data
    assert not recovery.manifest_path.exists()


def test_an_execution_equal_to_the_source_run_refuses_before_assembling(
    recovery: Recovery,
) -> None:
    tip = recovery.read_origin_tip()
    assert recovery.recover("--execution", str(recovery.source_run.id)) == (
        digest_recover.EXIT_REFUSED
    )
    assert not recovery.manifest_path.exists()
    assert recovery.read_origin_tip() == tip


def test_a_run_outside_the_repository_root_refuses_before_asking_the_platform(
    recovery: Recovery,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(recovery.repo / "config")
    assert recovery.recover("--restore-only") == digest_recover.EXIT_REFUSED
    assert recovery.asked == []


def test_a_day_that_fails_a_gate_is_assembled_but_never_pushed(recovery: Recovery) -> None:
    # The checkout holds no site project, so the site build gate cannot pass on any machine.
    tip = recovery.read_origin_tip()
    assert recovery.recover("--execution", RECOVERY_EXECUTION) == digest_recover.EXIT_REFUSED
    assert recovery.manifest_path.is_file()
    assert recovery.read_origin_tip() == tip
