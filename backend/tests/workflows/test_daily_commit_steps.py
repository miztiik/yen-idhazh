"""Do all digest jobs observe real producers and publish through their declared policy?"""

from pathlib import Path

import pytest
from conftest import REPO_ROOT

from idhazh.contracts.base import ServerJob
from idhazh.contracts.file_envelope import WriterIdentity
from idhazh.ledger import staging
from utilities import digest_publish, publication_evidence
from utilities.publication_request import IntegrityError

from ._harness import COMMIT_STEPS, _load_workflows, _mapping, _script, _step, _steps


@pytest.mark.parametrize("job", ["plan", "work", "assemble"])
def test_each_daily_job_uses_its_policy_and_observes_every_producer(job: str) -> None:
    workflow = _load_workflows()["digest.yml"]
    call = _script(_step(workflow, job, "name", COMMIT_STEPS[job]), job)
    assert f"backend/utilities/digest_publish.py {job}" in call
    assert "--execution" in call and "--commit" in call and "--date" in call
    scripts = "\n".join(str(step.get("run", "")) for step in _steps(workflow, job))
    for verb in digest_publish.VERBS[job]:
        assert f"digest_publish.py run {verb}" in scripts
    assert "commit_and_push.py" not in scripts
    assert "REGENERATE_COMMAND" not in scripts
    assert "git add" not in scripts
    declared = digest_publish.permissions(job, date="2026-10-09")
    for name, held in staging.REGISTRY.items():
        if job in held.job_labels:
            assert staging.staged_path(name) in declared
    assert not {"state", "state/raw", "state/compact"} & set(declared)


def test_only_assemble_has_derived_and_corpus_permission() -> None:
    assert "corpus/corpus.jsonl" in digest_publish.permissions("assemble", date="2026-10-09")
    for job in ("plan", "work"):
        assert not any(
            scope.startswith("corpus/")
            for scope in digest_publish.permissions(job, date="2026-10-09")
        )


def test_final_site_build_uses_the_published_tip_not_a_rebased_checkout() -> None:
    steps = _steps(_load_workflows()["digest.yml"], "assemble")
    names = [step.get("name") for step in steps]
    assert names.index("Commit the day") < names.index("Read the actual published inputs")
    assert names.index("Read the actual published inputs") < names.index(
        "Rebuild the site against the tree that was pushed"
    )
    published = _step(
        _load_workflows()["digest.yml"], "assemble", "name", "Read the actual published inputs"
    )
    assert _mapping(published["env"], "published inputs")["PUBLISHED_TIP"] == (
        "${{ steps.commit_day.outputs.candidate }}"
    )
    assert "published-inputs" in str(published["run"])


def test_a_receipt_cannot_claim_another_executed_identity(tmp_path: Path) -> None:
    identity = WriterIdentity(
        run_id="2026-10-09-123",
        attempt=1,
        job=ServerJob.PLAN,
        shard=0,
        producer="utilities.digest_publish",
        git_sha="a" * 40,
    )
    publication_evidence.save(tmp_path, identity, "plan", {})
    with pytest.raises(IntegrityError, match="another executed identity"):
        publication_evidence.read(tmp_path, identity.model_copy(update={"attempt": 2}), ("plan",))


def test_imported_state_is_a_separate_named_baseline_not_a_staging_exception() -> None:
    source = (REPO_ROOT / "backend" / "utilities" / "take_state_from_the_tip.py").read_text(
        encoding="utf-8"
    )
    assert "refs/worktree/publication-input-state" in source
    assert "named_entries" in source
    for command in ('"checkout"', '"reset"', '"clean"', '"stash"', '"rm"', '"add"'):
        assert f"git.git({command}" not in source
