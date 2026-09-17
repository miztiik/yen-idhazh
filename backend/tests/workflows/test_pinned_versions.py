"""Is every fetched build, action and interpreter pinned rather than whichever is newest?"""

from __future__ import annotations

import re
import tomllib

import pytest
from conftest import REPO_ROOT, read_text

from ._harness import (
    APPROVED_ACTION_MAJORS,
    LLAMA_DIGEST_CHECK,
    LLAMA_INLINE_RUNTIME_WORKFLOWS,
    LLAMA_PIN_NAMES,
    LLAMA_PIN_SCRIPT,
    LLAMA_PIN_VALUES,
    LLAMA_PINNED_ENDPOINT,
    LLAMA_RUNTIME_SCRIPT,
    LLAMA_RUNTIME_WORKFLOWS,
    LLAMA_SCRIPT_CALLERS,
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


def test_every_workflow_that_runs_llama_cpp_pins_the_same_build() -> None:
    """Production, the validation case and the harness run one binary.

    A throughput number is only about the pipeline if the pipeline runs the
    build the number was measured on (Guardrail #10).

    An unconverted workflow spells the pin in its own `env:` block. A converted
    one reads it off the shared script, which is the next test.
    """
    workflows = _load_workflows()

    for filename in sorted(LLAMA_INLINE_RUNTIME_WORKFLOWS):
        env = _mapping(workflows[filename].get("env"), f"{filename} env")
        assert env.get("LLAMA_CPP_BUILD") == PINNED_LLAMA_BUILD, filename
        assert env.get("LLAMA_CPP_ASSET") == PINNED_LLAMA_ASSET, filename
        assert env.get("LLAMA_CPP_SHA256") == PINNED_LLAMA_SHA256, filename


def test_the_shared_fetch_script_is_the_one_home_of_the_pin_for_every_caller_on_it() -> None:
    """One home per converted caller, and the test tightens as the rest convert.

    The pin used to live in eleven places that had to change together - four
    workflow `env:` blocks and seven fetch steps - and nothing read them against
    each other. Miss one on an upgrade and a case runs on a build production
    does not run, which is a measurement about a binary nobody ships
    (Guardrail #10).

    A conversion is one line in `LLAMA_SCRIPT_CALLERS`: that workflow stops
    being asked for an `env:` copy above and starts being refused one here. The
    set is not the whole runtime list yet, and this names which ones are left.

    What a converted caller is refused is the VALUE, not the name. A job whose
    stage records which build decoded the bytes has to put `LLAMA_CPP_BUILD` in
    that step's environment, and taking it from the step that published the pin
    reads the one home rather than copying it. Refusing the name instead would
    have refused that, and it also missed the obvious regression: `_strings`
    walks values, so an `env:` block reintroducing `LLAMA_CPP_BUILD: <build>`
    was invisible to it - the key is not a value and the build does not contain
    its own name.
    """
    pin = read_text(SCRIPTS_DIR / LLAMA_PIN_SCRIPT)
    assert f"LLAMA_CPP_BUILD={PINNED_LLAMA_BUILD}" in pin
    assert f"LLAMA_CPP_SHA256={PINNED_LLAMA_SHA256}" in pin
    assert PINNED_LLAMA_ASSET in pin.replace("${LLAMA_CPP_BUILD}", PINNED_LLAMA_BUILD)

    # Every shipped script, not just the fetch: the runtime install moved into a
    # second file, and a check that named one file would stop covering the pin
    # the moment a third appeared.
    for script in sorted(SCRIPTS_DIR.glob("*.sh")):
        if script.name == LLAMA_PIN_SCRIPT:
            continue
        text = read_text(script)
        for name in LLAMA_PIN_NAMES:
            assert f"{name}=" not in text, f"{script.name} spells {name} for itself"

    reachable = _script_closure(f"bash .github/scripts/{LLAMA_RUNTIME_SCRIPT}")
    assert f".github/scripts/{LLAMA_PIN_SCRIPT}" in reachable, (
        "the fetch reads the pin rather than repeating it"
    )

    assert LLAMA_SCRIPT_CALLERS <= LLAMA_RUNTIME_WORKFLOWS, (
        "a caller of the fetch script installs the runtime, so it belongs to that set"
    )
    assert LLAMA_SCRIPT_CALLERS, "nothing is converted, so this is checking nothing"

    published = f".outputs.{_pin_output_name()} }}}}"
    workflows = _load_workflows()
    for filename in sorted(LLAMA_SCRIPT_CALLERS):
        workflow = workflows[filename]
        assert any(
            shared in body for body in _run_bodies(workflow) for shared in LLAMA_SHARED_SCRIPTS
        ), f"{filename} is converted, so it has to call one of {sorted(LLAMA_SHARED_SCRIPTS)}"

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


def test_every_llama_cpp_fetch_is_pinned_and_digest_checked() -> None:
    workflows = _load_workflows()

    for filename in sorted(LLAMA_RUNTIME_WORKFLOWS):
        scripts = _llama_fetch_scripts(workflows[filename])
        assert scripts, f"{filename} must still fetch llama.cpp"

        for job_name, step_name, script in scripts:
            where = f"{filename}/{job_name}/{step_name}"
            assert LLAMA_PINNED_ENDPOINT in script, f"{where} must ask for one tag"
            assert LLAMA_DIGEST_CHECK in script, f"{where} must check the archive digest"
            assert RELEASE_LOOKUP_FORM in script, f"{where} must fail on an HTTP error"
            assert WEIGHTS_FETCH_FORM in script, f"{where} must fail on an HTTP error"


def test_no_workflow_takes_whichever_llama_cpp_release_is_newest() -> None:
    """The list endpoint hands back a different binary on every cache eviction.

    The scripts as well as the workflows, because the pin is moving into
    `.github/scripts/` one caller at a time and a check that stopped at the YAML
    would stop covering a fetch the moment that fetch was extracted.
    """
    named = (
        *WORKFLOWS_DIR.glob("*.yml"),
        *WORKFLOWS_DIR.glob("*.yaml"),
        *SCRIPTS_DIR.glob("*.sh"),
    )
    for path in sorted(named):
        assert "releases?per_page" not in read_text(path), path.name


def test_every_action_is_pinned_to_an_approved_major() -> None:
    """GitHub retired Node 20 on the runners.

    An action major that still declares `using: node20` is force-run on Node 24
    today and stops running at all later. The warning names the action, not the
    workflow, so nothing in the repo pointed at the 35 call sites until this test
    existed. A new action must be added here with its Node 24 major.
    """
    for filename, workflow in _load_workflows().items():
        references = _action_references(workflow)
        assert references, f"{filename} must call at least one action"

        for job_name, uses in references:
            where = f"{filename}/{job_name}"
            # A `./` action is this repository at the commit the run checked
            # out, so it is already pinned to the thing under test and there is
            # no major to approve. It is held by `_composite_action_script`
            # instead, which reads what it actually runs.
            if uses.startswith("./"):
                assert (REPO_ROOT / uses[2:] / "action.yml").is_file(), (
                    f"{where} calls a local action that does not exist: {uses}"
                )
                continue
            action, separator, version = uses.partition("@")
            assert separator, f"{where} must pin a version: {uses}"
            assert action in APPROVED_ACTION_MAJORS, f"{where} uses unapproved {action}"
            expected = APPROVED_ACTION_MAJORS[action]
            assert version == expected, f"{where} must use {action}@{expected}, not {uses}"


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
