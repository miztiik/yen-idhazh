"""Is every fetched build, action and interpreter pinned rather than whichever is newest?"""

from __future__ import annotations

import re
import tomllib

import pytest
from conftest import REPO_ROOT, read_text

from ._harness import (
    LLAMA_DIGEST_CHECK,
    LLAMA_PIN_NAMES,
    LLAMA_PIN_SCRIPT,
    LLAMA_PIN_VALUES,
    LLAMA_PINNED_ENDPOINT,
    LLAMA_RUNTIME_SCRIPT,
    LLAMA_SHARED_SCRIPTS,
    PINNED_LLAMA_ASSET,
    PINNED_LLAMA_BUILD,
    PINNED_LLAMA_SHA256,
    RELEASE_LOOKUP_FORM,
    SCRIPTS_DIR,
    WEIGHTS_FETCH_FORM,
    WORKFLOWS_DIR,
    _action_references,
    _every_env,
    _llama_fetch_scripts,
    _load_workflows,
    _mapping,
    _pin_output_name,
    _run_bodies,
    _script_closure,
    _setup_python_versions,
    _strings,
)

pytestmark = pytest.mark.workflow

#: The one file that still carries a second copy of the pin, and why it may. Its
#: three values sit in a workflow-level `env:` block, which cannot read a file at
#: all, and its four consumers are the inline download arms plan 46 converts.
#: Delete this and the test below when those arms go.
PIN_SECOND_COPY = "measure.yml"


def _fetch_script_callers(workflows: dict[str, dict[str, object]]) -> dict[str, dict[str, object]]:
    """Every workflow whose steps reach the shared runtime fetch, found by reading.

    This was a written list, so converting a caller was an edit to a test file
    before it was a change to a workflow.
    """
    return {
        filename: workflow
        for filename, workflow in sorted(workflows.items())
        if any(shared in body for body in _run_bodies(workflow) for shared in LLAMA_SHARED_SCRIPTS)
    }


def test_the_shared_fetch_script_is_the_one_home_of_the_pin_for_every_caller_on_it() -> None:
    """One home per converted caller, and the callers are read rather than listed.

    The pin used to live in eleven places that had to change together - four
    workflow `env:` blocks and seven fetch steps - and nothing read them against
    each other. Miss one on an upgrade and a case runs on a build production
    does not run, which is a measurement about a binary nobody ships
    (Guardrail #10).

    The three values are read off the pin script now rather than repeated in the
    harness, so a bump is one edit instead of three and a stale copy cannot
    agree with itself while the runners run something else.

    What a converted caller is refused is the VALUE, not the name. A job whose
    stage records which build decoded the bytes has to put `LLAMA_CPP_BUILD` in
    that step's environment, and taking it from the step that published the pin
    reads the one home rather than copying it. Refusing the name instead would
    have refused that, and it also missed the obvious regression: `_strings`
    walks values, so an `env:` block reintroducing `LLAMA_CPP_BUILD: <build>`
    was invisible to it - the key is not a value and the build does not contain
    its own name.

    Two one-line rules are folded in rather than kept as tests of their own:
    nobody asks for whichever release is newest, and a fetch names a tag and
    checks a digest.
    """
    assert all(LLAMA_PIN_VALUES), f"{LLAMA_PIN_SCRIPT} declares an empty pin"
    assert re.fullmatch(r"[0-9a-f]{64}", PINNED_LLAMA_SHA256), "the pin's digest is not a sha256"
    assert PINNED_LLAMA_BUILD in PINNED_LLAMA_ASSET, "the asset does not name the build it holds"

    # The list endpoint hands back a different binary on every cache eviction.
    # The scripts as well as the workflows, because a fetch that was extracted
    # into a script is still a fetch.
    named = (
        *WORKFLOWS_DIR.glob("*.yml"),
        *WORKFLOWS_DIR.glob("*.yaml"),
        *SCRIPTS_DIR.glob("*.sh"),
    )
    assert named, "neither directory ships anything, so this is checking nothing"
    for path in sorted(named):
        assert "releases?per_page" not in read_text(path), path.name

    # Every shipped script, not just the fetch: the runtime install moved into a
    # second file, and a check that named one file would stop covering the pin
    # the moment a third appeared.
    scripts = sorted(SCRIPTS_DIR.glob("*.sh"))
    assert scripts, f"{SCRIPTS_DIR} ships nothing, so nothing here can spell a pin"
    for script in scripts:
        if script.name == LLAMA_PIN_SCRIPT:
            continue
        text = read_text(script)
        for name in LLAMA_PIN_NAMES:
            assert f"{name}=" not in text, f"{script.name} spells {name} for itself"

    reachable = _script_closure(f"bash .github/scripts/{LLAMA_RUNTIME_SCRIPT}")
    assert f".github/scripts/{LLAMA_PIN_SCRIPT}" in reachable, (
        "the fetch reads the pin rather than repeating it"
    )
    assert LLAMA_PINNED_ENDPOINT in reachable, "the shared fetch must ask for one tag"
    assert LLAMA_DIGEST_CHECK in reachable, "the shared fetch must check the archive digest"

    workflows = _load_workflows()

    # Every fetch a workflow still spells for itself, discovered rather than
    # listed. That set empties as callers convert, and the closure above is what
    # covers them once it has.
    for filename, workflow in sorted(workflows.items()):
        for job_name, step_name, script_body in _llama_fetch_scripts(workflow):
            where = f"{filename}/{job_name}/{step_name}"
            assert LLAMA_PINNED_ENDPOINT in script_body, f"{where} must ask for one tag"
            assert LLAMA_DIGEST_CHECK in script_body, f"{where} must check the archive digest"
            assert RELEASE_LOOKUP_FORM in script_body, f"{where} must fail on an HTTP error"
            assert WEIGHTS_FETCH_FORM in script_body, f"{where} must fail on an HTTP error"

    converted = _fetch_script_callers(workflows)
    assert converted, "no workflow reaches the shared fetch, so this is checking nothing"

    published = f".outputs.{_pin_output_name()} }}}}"
    for filename, workflow in converted.items():
        copied = sorted(
            text for text in _strings(workflow) if any(v in text for v in LLAMA_PIN_VALUES)
        )
        assert not copied, (
            f"{filename} is converted, so the pin lives only in "
            f"{LLAMA_PIN_SCRIPT}: it still writes {copied}"
        )

        for scope, env in _every_env(workflow):
            for name, value in sorted(env.items()):
                if name not in LLAMA_PIN_NAMES:
                    continue
                assert isinstance(value, str) and value.endswith(published), (
                    f"{filename}: {scope} writes {name} as {value!r}; a converted "
                    f"caller reads it from the step that published the pin"
                )


def test_the_one_second_copy_of_the_pin_says_what_the_one_home_says() -> None:
    """A copy that may stay is a copy that has to be held equal.

    Every other caller reads the pin from the file that decides it. This one
    cannot: its three values are a workflow-level `env:` block, and a block at
    that scope runs before any step, so there is nothing to read a file with.
    Two of the jobs that consume it have no Python set up at all.

    So the copy stays and the drift goes. A bump that moves one and not the
    other leaves this workflow benchmarking a binary nobody ships, and a number
    about a binary nobody ships is a number about nothing (Guardrail #10).
    """
    env = _mapping(_load_workflows()[PIN_SECOND_COPY].get("env"), f"{PIN_SECOND_COPY} env")
    copied = [str(env.get(name, "")) for name in LLAMA_PIN_NAMES]
    assert copied == list(LLAMA_PIN_VALUES), (
        f"{PIN_SECOND_COPY} pins {copied} and the one home pins {list(LLAMA_PIN_VALUES)}"
    )


def test_every_action_a_workflow_calls_is_pinned() -> None:
    """A `uses:` with no `@` takes whatever that action's default branch holds today.

    An approval table of Node 24 majors used to sit here, and calling a new
    action meant editing it first. What it guarded against - a major still
    declaring `using: node20` - GitHub already warns about in the run log, and
    the warning names the action rather than the workflow, so the table was a
    second copy of a notice a person is handed anyway.
    """
    for filename, workflow in _load_workflows().items():
        references = _action_references(workflow)
        assert references, f"{filename} must call at least one action"

        for job_name, uses in references:
            where = f"{filename}/{job_name}"
            # A `./` action is this repository at the commit the run checked
            # out, so it is already pinned to the thing under test and there is
            # no version to name. It is held by `_composite_action_script`
            # instead, which reads what it actually runs.
            if uses.startswith("./"):
                assert (REPO_ROOT / uses[2:] / "action.yml").is_file(), (
                    f"{where} calls a local action that does not exist: {uses}"
                )
                continue
            assert "@" in uses, f"{where} must pin a version: {uses}"


def test_every_setup_python_pin_is_inside_the_declared_interpreter_range() -> None:
    """`requires-python` is the only thing that refuses an interpreter early.

    Without it pip does not stop - it falls back to a source build and hangs
    with no error at all. The bound is therefore load-bearing, and it has to
    agree with what CI installs in both directions: a CI pin above the ceiling
    installs an environment nobody can reproduce locally, and a ceiling below
    the pin breaks every run. Neither file mentions the other, so only this
    test keeps them together.
    """
    document = tomllib.loads(read_text(REPO_ROOT / "pyproject.toml"))
    declared = _mapping(document.get("project"), "pyproject [project]").get("requires-python")
    assert isinstance(declared, str), "pyproject must declare requires-python"

    bounds = re.fullmatch(r">=(\d+)\.(\d+),<(\d+)\.(\d+)(?:\.0a0)?", declared)
    assert bounds is not None, f"requires-python must carry both bounds: {declared}"
    floor = (int(bounds.group(1)), int(bounds.group(2)))
    ceiling = (int(bounds.group(3)), int(bounds.group(4)))

    pins = [
        (filename, job_name, version)
        for filename, workflow in _load_workflows().items()
        for job_name, version in _setup_python_versions(workflow)
    ]
    assert pins, "no workflow sets Python up"

    for filename, job_name, version in pins:
        where = f"{filename}/{job_name}"
        match = re.fullmatch(r"(\d+)\.(\d+)", version)
        assert match is not None, f"{where} must pin a major.minor, not {version}"
        minor = (int(match.group(1)), int(match.group(2)))
        assert floor <= minor < ceiling, f"{where} pins {version}, outside {declared}"
