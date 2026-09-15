"""What does qualification upload, and where does the browser it runs in come from?"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping

import pytest
from conftest import REPO_ROOT

from ._harness import (
    BROWSER_CACHE_PATH,
    BROWSER_VERSION_SOURCE,
    _job,
    _load_workflows,
    _mapping,
    _script,
    _step,
    _steps,
)

pytestmark = pytest.mark.workflow


def test_the_candidate_bytes_are_verified_before_the_server_starts() -> None:
    """Wrong weights must cost one step, not a whole shard of measurements filed
    under a model that never ran (Guardrail #10)."""
    workflow = _load_workflows()["validate.yml"]
    names = [step.get("name") for step in _steps(workflow, "qualify")]
    verify = names.index("Verify the candidate bytes")
    assert verify < names.index("Start the candidate")
    assert verify < names.index("Freeze the corpus and replay it")

    step = _step(workflow, "qualify", "name", "Verify the candidate bytes")
    script = _script(step, "validate.yml/qualify/Verify the candidate bytes")
    assert "sha256sum --check" in script
    assert "candidate_byte_count" in script, "the entry's declared size is checked too"
    assert step.get("if") is None, "a restored cache entry is checked as well"


def test_the_qualification_uploads_no_article_body() -> None:
    """This repository is public. A frozen corpus is hashes and measurements;
    the article text stays on the runner that captured it and dies with it."""
    workflow = _load_workflows()["validate.yml"]
    upload = _step(workflow, "qualify", "uses", "actions/upload-artifact@v7")
    path = _mapping(upload.get("with"), "qualify upload 'with'").get("path")
    assert path == "backend/var/qualification/shard-*.json"
    assert "items" not in str(path)


def test_the_whole_day_check_gets_its_own_build_and_never_the_canary() -> None:
    """`frontend/build` is one directory, and two builds write it.

    `whole-day.spec.ts` refuses to load against a tree that is not the published
    site, which is the guard that makes it worth running at all. Sharing a job
    with the canary build would mean either running it against the thing it was
    written to catch, or ordering two builds inside one job and hoping nobody
    reorders them. Its own job cannot be got wrong that way.
    """
    workflow = _load_workflows()["ci.yml"]
    steps = _steps(workflow, "whole-day")
    scripts = [
        _script(step, "ci.yml/whole-day") for step in steps if isinstance(step.get("run"), str)
    ]
    joined = "\n".join(scripts)

    assert "build:canary" not in joined, "the canary must never reach this job's build directory"
    assert "build_canary_day" not in joined
    builds = [index for index, text in enumerate(scripts) if "npm run build" in text]
    checks = [index for index, text in enumerate(scripts) if "test:whole-day" in text]
    assert builds and checks, "the job builds the real site and then looks at it"
    assert max(builds) < min(checks), "the build has to land before the spec opens the tree"


def test_the_whole_day_check_is_bought_by_the_same_change_the_browser_half_is() -> None:
    """One allow-list, because it is one question about the published page.

    A second list would drift from the first, and the drift is silent: the
    change that needed this check is exactly the change that needed the browser
    half, and a job nobody buys is a check that stopped existing.
    """
    workflow = _load_workflows()["ci.yml"]

    assert _job(workflow, "whole-day")["if"] == _job(workflow, "browser")["if"]
    assert _job(workflow, "whole-day")["needs"] == "scope"


def _browser_install_jobs(
    workflows: Mapping[str, dict[str, object]],
) -> dict[tuple[str, str], list[dict[str, object]]]:
    """Every job in the repository that installs a browser, found and not listed.

    Found, because the hazard is the job nobody remembered: a new job that
    downloads 300 MB of Chromium on every run costs the same whether or not
    anybody added it to a list here.
    """
    found: dict[tuple[str, str], list[dict[str, object]]] = {}
    for filename, workflow in workflows.items():
        for job_name in _mapping(workflow.get("jobs"), "jobs"):
            steps = _steps(workflow, job_name)
            if any(
                isinstance(script := step.get("run"), str) and "playwright install" in script
                for step in steps
            ):
                found[(filename, job_name)] = steps
    return found


def test_every_job_that_installs_a_browser_restores_it_from_one_shared_key() -> None:
    """The browser bytes are restored, and the two jobs share one entry.

    Measured on run 34678620051, 2026-09-12: the download is 184.3 MB of
    Chromium, 114.7 MB of headless shell and 2.3 MB of FFmpeg, about 9 s of a
    23 s step, paid twice a run because `browser` and `whole-day` each need a
    browser. The other 14 s is the `--with-deps` apt-get, which a cache cannot
    hold - so the install step stays, and stays unconditional.

    Two keys would be the quiet failure rather than a loud one. The repository
    cache ceiling is 10 GB (Guardrail #2) and the two weights entries held 7.5 GB of
    it on 2026-09-12, so a second browser entry is not headroom this has. One
    key is also the only way either job can hit: they start together, so
    neither can ever warm the other.
    """
    workflows = _load_workflows()
    jobs = _browser_install_jobs(workflows)
    assert jobs, "the repository installs a browser somewhere, or this test is dead"

    keys: set[str] = set()
    for (filename, job_name), steps in jobs.items():
        where = f"{filename}/{job_name}"
        restores = [
            step for step in steps if str(step.get("uses", "")).startswith("actions/cache@")
        ]
        assert len(restores) == 1, f"{where}: one restore for the browser bytes, not {len(restores)}"
        with_block = _mapping(restores[0].get("with"), f"{where} cache 'with'")
        assert with_block.get("path") == BROWSER_CACHE_PATH, (
            f"{where}: cache the directory Playwright unpacks into"
        )
        key = with_block.get("key")
        assert isinstance(key, str), f"{where}: the cache key must be a string"
        keys.add(key)

        positions = {
            index: str(step.get("run", "")) for index, step in enumerate(steps)
        }
        install = min(
            index for index, script in positions.items() if "playwright install" in script
        )
        assert steps.index(restores[0]) < install, f"{where}: restore before the download"

    assert len(keys) == 1, f"one key for every browser job, found {sorted(keys)}"
    key = keys.pop()
    assert "hashFiles(" not in key, (
        "a lockfile hash moves when any dependency moves, so an unrelated bump "
        "would refetch 300 MB of browser for nothing"
    )
    source_file, source_job, source_step, source_output = BROWSER_VERSION_SOURCE
    assert f"needs.{source_job}.outputs.{source_output}" in key, (
        f"the key reads the version {source_file}/{source_job} published"
    )
    outputs = _mapping(
        _job(workflows[source_file], source_job).get("outputs"),
        f"{source_file}/{source_job} outputs",
    )
    assert outputs.get(source_output) == f"${{{{ steps.{source_step}.outputs.{source_output} }}}}"


def test_the_browser_cache_key_names_a_version_the_lockfile_really_holds() -> None:
    """The reader is run against the committed lockfile, not just read.

    This is the failure that has no symptom. A renamed package path or a moved
    lockfile makes the expression evaluate to nothing, the key becomes a
    constant prefix, and every run from then on restores an entry that was
    saved under it once - or misses forever. Nothing goes red; CI just gets
    slower and stays slower. So the test resolves the same path the step
    resolves and asserts it lands on a version.
    """
    source_file, source_job, source_step, source_output = BROWSER_VERSION_SOURCE
    step = _step(_load_workflows()[source_file], source_job, "id", source_step)
    script = _script(step, f"{source_file}/{source_job}/{source_step}")

    read = re.search(
        r"require\('(?P<lockfile>[^']+)'\)\.packages\['(?P<package>[^']+)'\]\.version",
        script,
    )
    assert read is not None, "the step reads one package's version out of one lockfile"
    lockfile = REPO_ROOT / read.group("lockfile")
    assert lockfile.is_file(), f"the step reads {read.group('lockfile')}, which is not there"
    packages = json.loads(lockfile.read_text(encoding="utf-8"))["packages"]
    assert read.group("package") in packages, (
        f"{read.group('package')} is not in {read.group('lockfile')}"
    )
    version = packages[read.group("package")]["version"]
    assert re.fullmatch(r"\d+\.\d+\.\d+", version), (
        f"the pinned browser build reads as {version!r}, which the step would refuse"
    )

    assert f'echo "{source_output}=$version" >> "$GITHUB_OUTPUT"' in script
    assert r"^[0-9]+\.[0-9]+\.[0-9]+$" in script, (
        "the value is substituted into a cache key, so its shape is checked here first"
    )
    assert "exit 1" in script, "an unreadable version fails the step rather than keying on it"
