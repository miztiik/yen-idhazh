"""Can every workflow really run the script it names?"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Final

import pytest
from conftest import REPO_ROOT

from ._harness import SCRIPT_CALL, SCRIPTS_DIR, _load_workflows, _run_bodies

pytestmark = pytest.mark.workflow

#: The words that hand a script to an interpreter, which is what makes the file
#: mode stop deciding whether the step runs. `nohup bash <path>` ends in one of
#: these too, so the token immediately before the path is the whole question.
INTERPRETERS: Final = frozenset({"bash", "sh"})

#: What `git ls-files -s` prints for a file a runner can execute.
EXECUTABLE: Final = "100755"


def _calls() -> list[tuple[str, str, bool]]:
    """Every (workflow, script, runs as a command) a shell step spells out.

    A path inside a comment or inside backticks is prose about a script rather
    than a call to one, so the match has to start a shell word and its line must
    not be a comment.
    """
    found: list[tuple[str, str, bool]] = []
    for filename, workflow in sorted(_load_workflows().items()):
        for body in _run_bodies(workflow):
            for line in body.splitlines():
                if line.lstrip().startswith("#"):
                    continue
                for match in SCRIPT_CALL.finditer(line):
                    if match.start() and not line[match.start() - 1].isspace():
                        continue
                    before = line[: match.start()].split()
                    handed_over = bool(before) and before[-1] in INTERPRETERS
                    found.append((filename, match.group("name"), not handed_over))
    return found


def _sourced() -> set[str]:
    """Every script that another shipped script sources, which no step spells out.

    `fetch-model-runtime.sh` sources the install half so the pin lands in the
    same shell both run in. A sourced script is reached through its sourcer, and
    needs no mode of its own.
    """
    found: set[str] = set()
    for path in SCRIPTS_DIR.glob("*.sh"):
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.lstrip()
            if stripped.startswith("#") or not stripped.startswith((". ", "source ")):
                continue
            found.update(match.group("name") for match in SCRIPT_CALL.finditer(line))
    return found


def _committed_modes() -> dict[str, str]:
    """The mode git recorded for each shipped script, by filename.

    The index, never the working tree. Git does not carry an executable bit on a
    Windows checkout, so `Path.stat` there answers about the developer's
    filesystem rather than about the bytes and bits the runner checks out.
    """
    listed = subprocess.run(
        ["git", "ls-files", "-s", "--", SCRIPTS_DIR.relative_to(REPO_ROOT).as_posix()],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    modes: dict[str, str] = {}
    for line in listed:
        details, _, path = line.partition("\t")
        modes[Path(path).name] = details.split()[0]
    return modes


def test_every_script_a_workflow_runs_as_a_command_is_committed_executable() -> None:
    """A bare path runs only while the file carries the bit, and nothing else reads it.

    `idhazh-pipeline-tests.yaml` shipped three steps calling a script by its
    bare path while that script was committed 100644, and the first dispatch
    died on `Permission denied`, exit 126, before the first article. The tests
    over that workflow read the YAML and shellcheck reads the script; a file
    mode is text to neither of them, so this is the one place it is checked.

    Both conventions stay legal, because both are already shipped: a script
    handed to `bash` needs no mode at all, and a script named as a command needs
    100755. What is not legal is the pair that cannot run.
    """
    calls = _calls()
    assert calls, "no workflow names a shipped script, so this is checking nothing"

    modes = _committed_modes()
    unrunnable = sorted(
        {
            f"{filename} runs {name} as a command and git recorded it {modes.get(name, 'nowhere')}"
            for filename, name, as_a_command in calls
            if as_a_command and modes.get(name) != EXECUTABLE
        }
    )
    assert not unrunnable, (
        "a step naming a script as a command needs that script committed "
        f"{EXECUTABLE}, or it needs `bash ` in front of the path: "
        + "; ".join(unrunnable)
    )


def test_every_shipped_script_is_one_a_workflow_runs() -> None:
    """`.github/scripts/` holds a step, not a tool (`docs/reference/repository-layout.md`).

    It is also what makes the mode check above complete rather than merely
    green: a script nothing reaches is a script whose mode nothing here would
    ever look at, and a workflow naming a script that is not shipped is a step
    that fails on the runner over a path nobody can grep for.

    A step is not the only way in. A script another shipped script sources runs
    inside that one's shell, so it is reached without a workflow naming it.
    """
    shipped = {path.name for path in SCRIPTS_DIR.glob("*.sh")}
    assert shipped, "the directory ships nothing, so no workflow can be reaching it"

    named = {name for _, name, _ in _calls()}
    reached = named | _sourced()
    assert reached == shipped, (
        "every shipped script is reached and every script a workflow names is "
        f"shipped: workflows name {sorted(named - shipped)} that are not "
        f"here, and {sorted(shipped - reached)} is here and reached by nothing"
    )
