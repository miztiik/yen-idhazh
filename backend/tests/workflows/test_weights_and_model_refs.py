"""Are the weights checked before anything reads them, and who may write a model ref?"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from pathlib import Path

import pytest
from conftest import CONFIG_DIR, read_text

from idhazh.contracts.base import SLUG_PATTERN
from utilities import measure_llm, model_refs

from ._harness import (
    ACTIONS_DIR,
    CONFIG_FILE_NAME,
    DOWNLOAD_MODEL_FILES,
    GITHUB_DIR,
    HUB_HOST,
    LLAMA_RUNTIME_WORKFLOWS,
    MODEL_ENV_NAMES,
    MODEL_REF_FIELDS,
    MODEL_REF_OUTPUTS,
    MODEL_SERVER_ACTION,
    MODELS_POINTER_KEY,
    PINNED_LLAMA_BUILD,
    SHARED_WEIGHTS_KEY_PREFIX,
    VERIFY_MODEL_FILES,
    WEIGHTS_CACHE_ROLES,
    WEIGHTS_CACHE_SUFFIX,
    WEIGHTS_CHECKS,
    WEIGHTS_FETCH_JOBS,
    WORKFLOWS_DIR,
    _action_call,
    _committed_models,
    _declared_dispatch_inputs,
    _every_env,
    _expression,
    _load_workflows,
    _mapping,
    _model_server_callers,
    _pin_output_name,
    _published,
    _runtime_cache_keys,
    _script,
    _shared_download_jobs,
    _step,
    _steps,
    _weights_fetch_steps,
)

pytestmark = pytest.mark.workflow

#: What a workflow runs instead of carrying its own copy. Three of them called
#: this program by heredoc and the copies drifted; the call is asserted so a
#: fourth cannot quietly go back to inlining it.
MODEL_REFS_CALL = "python3 backend/utilities/model_refs.py"

#: The one file under `.github/` that may still spell the hub host. Its four
#: inline download steps are plan 46's to convert; delete this exception when
#: they go.
HUB_HOST_EXCEPTION = "measure.yml"

#: Every name the model file's reader publishes, read off the reader rather than
#: retyped. A key retyped here would go stale the day a field is added, and the
#: rule below would stop covering the field nobody remembered.
PUBLISHED_KEYS = frozenset(
    model_refs.CANDIDATE_FIELDS
    + model_refs.CONFIGURED_FIELDS
    + model_refs.COMPANION_FIELDS
    + model_refs.PUBLISHED_EXTRA
    + model_refs.CONFIGURED_EXTRA
)

#: The three contexts a `run:` body may substitute a job's own answers from.
#: `github`, `matrix`, `env` and `secrets` carry no model value at all.
PASTEABLE_CONTEXTS = ("steps", "needs", "inputs")


def test_every_fetched_weight_is_checked_before_anything_reads_it() -> None:
    """The Oracle. Wrong bytes fail on one step, not hours later as wrong output.

    Closed-world: the fetches are discovered by reading every workflow, and the
    discovered set must equal the written table plus the jobs that reach the
    shared download. A tenth workflow that downloads a `.gguf` fails here until
    it carries a check of its own.

    A converted job is derived rather than listed, because what would be listed
    is the same four step names four times: the check is one call to a verb, and
    what it checks is the declaration rather than a filename somebody typed.
    The four arms still spelling their own download keep their written rows,
    because each of those names a different digest source.

    No check carries an `if:`, on purpose. A restored cache entry is the one
    case where nobody watched the bytes arrive, so it is the case that most
    needs checking.
    """
    workflows = _load_workflows()
    converted = _shared_download_jobs(workflows)
    assert set(_weights_fetch_steps(workflows)) == set(WEIGHTS_CHECKS) | set(converted)
    assert not set(WEIGHTS_CHECKS) & set(converted), (
        "a job cannot both reach the shared download and spell its own"
    )

    for (filename, job_name), expected in sorted(WEIGHTS_CHECKS.items()):
        fetch_name, check_name, reader_name, digest_source = expected
        where = f"{filename}/{job_name}"
        names = [step.get("name") for step in _steps(workflows[filename], job_name)]

        for expected_name in (fetch_name, check_name, reader_name):
            assert expected_name in names, f"{where} has no step named {expected_name!r}"
        assert names.index(fetch_name) < names.index(check_name), where
        assert names.index(check_name) < names.index(reader_name), where

        check = _step(workflows[filename], job_name, "name", check_name)
        assert "if" not in check, f"{where}: a restored cache is what most needs checking"
        script = _script(check, f"{where}/{check_name}")
        assert digest_source in script, f"{where} must read one recorded digest"
        assert "sha256sum --check" in script, where

    for converted_where in sorted(converted):
        filename, job_name = converted_where
        names = [str(step.get("name")) for step in _steps(workflows[filename], job_name)]
        check = _one_step_running(workflows, converted_where, VERIFY_MODEL_FILES)
        fetch = _one_step_running(workflows, converted_where, DOWNLOAD_MODEL_FILES)
        named = "/".join(converted_where)
        assert names.index(str(fetch["name"])) < names.index(str(check["name"])), named
        assert "if" not in check, f"{named}: a restored cache is what most needs checking"


def test_no_arm_starts_measuring_before_it_knows_which_model_answered() -> None:
    """The Oracle. A number is about a model only if that model produced it.

    `validate.yml` has asked `/v1/models` since it was written. `measure.yml`
    waited for a 200 and started the clock, so a server answering under any
    other alias would have had its throughput filed under the candidate - which
    is a Guardrail #10 failure that no gate would have caught, because every
    number in the report would be internally consistent and wrong.

    Discovery is over every step that waits for `/health`, so an arm added later
    is held to the same rule whether or not anybody remembered it. The drift this
    catches has run in both directions: `test_model_server_jobs` records the last
    time it was `validate.yml` that nobody diffed.

    Absorbing what was a second test beside it: the alias says which name the
    server answered under, and only the loaded path says which bytes. A step
    that asks for the path has to compare it against a filename it was handed by
    name - a probe comparing against a name nothing filled passes on an empty
    string and says nothing at all.
    """
    compared = 0
    for filename, workflow in sorted(_load_workflows().items()):
        for job_name in _mapping(workflow.get("jobs"), f"{filename} jobs"):
            for step in _steps(workflow, job_name):
                script = step.get("run")
                if not isinstance(script, str) or "/health" not in script:
                    continue
                where = f"{filename}/{job_name}/{step.get('name')}"
                assert "/v1/models" in script, (
                    f"{where} waits for health and never asks which model answered"
                )
                if "/props" not in script:
                    continue
                compared += 1
                given = _mapping(step.get("env"), f"{where} env")
                handed = sorted(name for name in given if f"${{{name}}}" in script)
                assert handed, f"{where} compares the loaded path against no name it was handed"
                assert ".gguf" not in script, f"{where} names a weights file of its own"

    assert compared, "no step compares the path the server loaded, so this checks nothing"


def test_the_daily_run_writes_no_model_ref_of_its_own() -> None:
    """The Oracle. One place writes a production model ref, and it is config.

    `digest.yml` used to carry the repo and the filename as workflow `env` while
    the alias came from config. Two answers to one question drift the moment
    either is edited: llama-server then serves the old bytes under the new alias
    and every eval row names a model that never ran (Guardrail #6, Guardrail #10).
    """
    text = read_text(WORKFLOWS_DIR / "digest.yml")
    assert ".gguf" not in text, "a weights filename is written in config, not here"
    assert not re.search(r"huggingface\.co/(?!\$\{\{)", text), "no repo literal"

    workflow = _load_workflows()["digest.yml"]
    for scope, env in _every_env(workflow):
        named = MODEL_ENV_NAMES & set(env)
        assert not named, f"{scope} names a model through env: {sorted(named)}"


def test_no_workflow_that_loads_weights_writes_a_model_ref_or_a_moving_one() -> None:
    """The Oracle, widened to every workflow that downloads weights.

    `digest.yml` had already been cleaned; `measure.yml` still carried the two
    production refs as job `env` and a third copy as a dispatch default, and
    `validate.yml` carried a candidate's repo and filename as defaults. Each was
    a second answer to a question config already answers, and each one drifts
    silently the day config moves (Guardrail #6).

    Every download also names an immutable commit. A branch hands back whatever
    was uploaded last, so a measurement taken from one describes bytes nobody
    can fetch again (Guardrail #10).

    A dispatch INPUT is not a hardcode and is deliberately left alone: it is how
    an operator points the measurement harness at a model config does not name.
    What this test forbids is a literal written into the file.
    """
    hub = re.compile(r"huggingface\.co/(?!\$\{)")
    branch = re.compile(r"(?:resolve|tree|blob|raw)/(?:main|master)\b")
    # A weights repository is `<publisher>/<name>GGUF` by convention, so the
    # shape catches the next one; the two publishers that were written into
    # these files are named outright, so a repository that breaks the
    # convention is still caught.
    repo_shape = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]*GGUF\b")
    publishers = re.compile(r"\b(?:Qwen|unsloth|bartowski|TheBloke)\b")

    # The action the five weights steps moved into is read on the same terms. A
    # rule that stopped at `.github/workflows/` would have stopped covering the
    # fetch the day it was extracted, which is the one thing an extraction must
    # not buy.
    named = [WORKFLOWS_DIR / filename for filename in sorted(LLAMA_RUNTIME_WORKFLOWS)]
    named.append(ACTIONS_DIR / MODEL_SERVER_ACTION.rsplit("/", 1)[-1] / "action.yml")

    for path in named:
        filename = path.name
        text = read_text(path)
        assert ".gguf" not in text, f"{filename}: a weights filename belongs in config"
        assert not hub.search(text), f"{filename}: a repository literal belongs in config"
        assert not repo_shape.search(text), f"{filename}: a repository literal belongs in config"
        assert not publishers.search(text), f"{filename}: a model publisher belongs in config"
        assert not branch.search(text), f"{filename}: a download must name an immutable commit"

    for filename in sorted(LLAMA_RUNTIME_WORKFLOWS):
        for scope, env in _every_env(_load_workflows()[filename]):
            for name, value in env.items():
                if name not in MODEL_ENV_NAMES:
                    continue
                assert isinstance(value, str) and value.startswith("${{"), (
                    f"{filename}: {scope} writes {name} as a literal"
                )


def test_the_model_block_reads_the_refs_out_of_config_where_it_uses_them(
    tmp_path: Path,
) -> None:
    """One reader, called where the answer is needed, and no relay in between.

    The refs used to be read in a plan job and republished as seven job outputs,
    because `needs` resolves before a job's first step and `steps` does not - so
    a weights cache key could not otherwise name the file it held. The key is
    computed inside the action now, from the same call that publishes the refs,
    which removes the relay and the four hops a value could be pasted at.

    A companion's four refs are not published at all any more. The download
    reads the declaration, so a second copy of one companion's facts is a second
    answer to a question nobody asks.
    """
    step = _step(
        _load_workflows()["digest.yml"], "work", "name", "Read what the model declares"
    )
    script = _script(step, "model-server/model")
    assert MODEL_REFS_CALL in script, "the refs come from the one module that reads config"
    assert '>> "$GITHUB_OUTPUT"' in script

    models = _committed_models()
    role = WEIGHTS_CACHE_ROLES["work"]
    published = _published(model_refs.pinned_rows(CONFIG_DIR))
    assert set(published) == {
        *(f"{role}_{field}" for field in MODEL_REF_FIELDS),
        f"{role}_id",
        f"{role}_weights_path",
        f"{role}_cache_key",
    }
    for name in MODEL_REF_OUTPUTS:
        assert name in published, f"the daily run stopped publishing {name}"
    for field in (*MODEL_REF_FIELDS, "id"):
        assert published[f"{role}_{field}"] == models[role][field]
    assert published[f"{role}_weights_path"] == f"{model_refs.MODELS_DIR}/{models[role]['file']}"
    assert model_refs.SHA256_RE.fullmatch(published[f"{role}_cache_key"])

    # Every ref is substituted straight into a shell command downstream, so the
    # one step that writes them is where a value that is not one bare word has
    # to stop. Nothing else between config and those commands can catch it.
    pointer = "models/probe.json"
    (tmp_path / "config" / "models").mkdir(parents=True)
    models["summarize"]["file"] = "Qwen3-8B-Q4_K_M.gguf; rm -rf /"
    (tmp_path / "config" / pointer).write_text(json.dumps(models), encoding="utf-8")
    (tmp_path / "config" / "idhazh.json").write_text(
        json.dumps({MODELS_POINTER_KEY: pointer}), encoding="utf-8"
    )
    with pytest.raises(SystemExit, match=re.escape("summarize.file")):
        model_refs.pinned_rows(tmp_path / "config")


def test_a_daily_run_refuses_a_draft_head_that_declares_only_half_of_itself(
    tmp_path: Path,
) -> None:
    """Four fields or none. A head with three is a file fetched against a blank.

    The guard read `if value and value.split() != [value]`, so an empty field
    passed it. An entry naming a draft `file` with no `sha256` therefore reached
    the fetch step, downloaded the head, and only then failed inside
    `sha256sum --check` on a line with nothing to check - which reports "no
    properly formatted checksum lines found" and names neither the entry nor
    the field. The two measurement arms have always used `if draft and`.

    The absent case is the one this must not break: no committed entry declares
    a head today, and a guard that refused `{}` would take down every run this
    repository makes.
    """
    pointer = "models/probe.json"
    (tmp_path / "config" / "models").mkdir(parents=True)
    models = _committed_models()
    models["summarize"]["companion_files"] = [
        {
            "repo": "publisher/head-GGUF",
            "revision": "8c5a9e4fd5482e2be20fe0bf013b4c262a8f4265",
            "file": "head.gguf",
            "sha256": "",
        }
    ]
    (tmp_path / "config" / pointer).write_text(json.dumps(models), encoding="utf-8")
    (tmp_path / "config" / "idhazh.json").write_text(
        json.dumps({MODELS_POINTER_KEY: pointer}), encoding="utf-8"
    )

    with pytest.raises(
        SystemExit, match=re.escape("summarize.companion_files[0].sha256")
    ):
        model_refs.pinned_rows(tmp_path / "config")


def test_a_candidate_is_named_by_its_models_file_and_by_nothing_else(tmp_path: Path) -> None:
    """One argument, so the two copies of a candidate's facts cannot disagree.

    A form that asked for the repository, the commit, the filename, the digest,
    the byte count, the alias and the quantisation was asking an operator to
    retype seven facts already written in the candidate's own file. Two copies
    can differ, and the failure is silent: the bench measures one set of bytes
    and the adoption points at another, with every gate green.

    The path becomes a file the step opens, so containment is proved rather than
    spelled - `..` in a form field is the whole reason this is a resolve check
    and not a name check.
    """
    committed = _committed_models()
    for filename, step_id, prefix in (
        ("validate.yml", "candidate", ""),
        ("measure.yml", "models", "candidate_"),
    ):
        workflow = _load_workflows()[filename]
        declared = sorted(
            name for name in _declared_dispatch_inputs(workflow) if name.startswith("candidate")
        )
        assert declared == ["candidate_models_file"], (
            f"{filename} asks for more than the one file that already holds the answer"
        )

        job = "plan" if step_id == "candidate" else step_id
        script = _script(_step(workflow, job, "id", step_id), filename)
        assert MODEL_REFS_CALL in script, f"{filename} resolves the candidate somewhere else"
        assert f"--prefix {prefix}" in script or not prefix, (
            f"{filename} publishes its keys under a prefix this test does not know"
        )

        published = _published(model_refs.trial_rows(CONFIG_DIR, "", prefix=prefix))
        for field in ("repo", "revision", "file", "id", "quantisation", "sha256"):
            assert published[f"{prefix}{field}"] == committed["summarize"][field], (
                f"{filename} publishes a {field} the committed entry does not carry"
            )

        # A named file is read instead, and a traversal out of the config root
        # stops here - nothing downstream opens the path again to check it.
        (tmp_path / "config" / "models").mkdir(parents=True, exist_ok=True)
        other = json.loads(json.dumps(committed))
        other["summarize"]["id"] = "some-other-model"
        (tmp_path / "config" / "models" / "other.json").write_text(
            json.dumps(other), encoding="utf-8"
        )
        (tmp_path / "config" / CONFIG_FILE_NAME).write_text(
            json.dumps({MODELS_POINTER_KEY: "models/other.json"}), encoding="utf-8"
        )
        named = _published(
            model_refs.trial_rows(tmp_path / "config", "models/other.json", prefix=prefix)
        )
        assert named[f"{prefix}id"] == "some-other-model"
        assert named[f"{prefix}models_file"] == "models/other.json"

        with pytest.raises(SystemExit, match="under config/"):
            model_refs.trial_rows(
                tmp_path / "config", "../../etc/passwd.json", prefix=prefix
            )


def test_the_weights_cache_key_names_the_model_and_the_build_it_holds() -> None:
    """The Oracle. Every part of what the entry holds, and all of them from one source.

    The fetch step runs only on a cache miss, so a key that omits any part turns
    that step into dead code and serves the wrong bytes silently.

    **There is one key now, so this is not a comparison between two workflows.**
    The block moved into `model-server` and neither caller spells a key any
    more, which is what makes them share the entry rather than merely agree
    about it. What the literal is held against instead is the pair of committed
    files that decide its halves: each half is substituted for what the reader
    and the pin say, and the composed string is compared character for
    character. An expression that does not resolve leaves a literal `${{` in the
    key, and Actions would key the cache on that text.

    The model half is one digest over every file the entry declares, where it
    was a filename and a commit. Two builds of one model share a filename, so
    the commit was there to tell them apart - and a digest over the whole
    declared set tells them apart AND tells apart two entries that differ only
    in a companion, which the old key could not.
    """
    workflows = _load_workflows()
    callers = _model_server_callers(workflows)
    assert callers, "no job calls the model-server action, so there is no key to read"
    keys = {
        (filename, job_name): dict(_runtime_cache_keys(workflows[filename]))[job_name]
        for filename, job_name in callers
    }
    assert len(set(keys.values())) == 1, f"one entry cannot hold two sets of weights: {keys}"
    key = next(iter(keys.values()))

    digest = _expression("steps.model.outputs.summarize_cache_key")
    build = _expression(f"inputs.{_pin_output_name()}")
    assert key == f"llm-{digest}-{build}-{WEIGHTS_CACHE_SUFFIX}"

    published = _published(model_refs.pinned_rows(CONFIG_DIR))
    composed = key.replace(digest, published["summarize_cache_key"]).replace(
        build, PINNED_LLAMA_BUILD
    )
    assert "${{" not in composed, "every half of the key must resolve"
    assert composed == (
        f"llm-{published['summarize_cache_key']}-{PINNED_LLAMA_BUILD}-{WEIGHTS_CACHE_SUFFIX}"
    )

    # The build is the one half the model file does not decide, so it is the one
    # half that still crosses the boundary - and it has to arrive as a job
    # output that read the pin, never as a literal a caller composed.
    relayed = re.compile(r"\$\{\{ needs\.[a-z_]+\.outputs\.[a-z_0-9]+ \}\}")
    for filename, job_name in sorted(callers):
        given = _action_call(workflows[filename], job_name, MODEL_SERVER_ACTION)
        name = _pin_output_name()
        assert relayed.fullmatch(given[name]), (
            f"{filename}/{job_name} hands {name} the literal {given[name]!r}"
        )


#: Where each bench-side workflow decides what the candidate is: the step that
#: reads the entry, and the prefix it puts on what it publishes.
CANDIDATE_STEPS = (
    ("measure.yml", "models", "models", "candidate_"),
    ("validate.yml", "plan", "candidate", ""),
)


def _an_entry(**extra: object) -> dict[str, object]:
    """A summarize entry carrying everything the step requires, plus what a test adds."""
    return {
        "repo": "publisher/Model-GGUF",
        "revision": "0" * 40,
        "file": "model-Q4_K_M.gguf",
        "sha256": "a" * 64,
        "id": "model-q4-k-m",
        "quantisation": "Q4_K_M",
        **extra,
    }


def _digest_of(*entries: Mapping[str, object]) -> str:
    """C5's serialisation, spelled here rather than read off the module under test.

    TAB between fields, LF between rows, no trailing LF, ASCII, lowercase hex. A
    test that called the reader twice and compared its two answers would assert
    nothing at all.
    """
    return hashlib.sha256(
        b"\n".join(
            b"\t".join(
                str(entry[field]).encode("ascii")
                for field in ("repo", "revision", "file", "sha256")
            )
            for entry in entries
        )
    ).hexdigest()


def _a_config_tree(tmp_path: Path, summarize: dict[str, object]) -> Path:
    """One models file, built rather than borrowed, and the config root over it.

    The committed tree has one entry with a draft head and two without, so a
    test driven from it could only ever ask what today's config happens to say -
    and it would go quiet on the day somebody retired the entry it relied on.
    """
    models = tmp_path / "config" / "models"
    models.mkdir(parents=True, exist_ok=True)
    (tmp_path / "config" / "idhazh.json").write_text(
        json.dumps({"models_file": "models/candidate.json"}) + "\n", encoding="utf-8"
    )
    (models / "candidate.json").write_text(
        json.dumps({"summarize": summarize}) + "\n", encoding="utf-8"
    )
    return tmp_path / "config"


def _candidate_outputs(
    filename: str, job_name: str, step_id: str, tmp_path: Path, summarize: dict[str, object]
) -> dict[str, str]:
    """What the step publishes, driven through the module the step now calls.

    The step is still read, because the thing that would break silently is a
    workflow quietly going back to its own copy - and then this would be
    checking a program nothing runs.
    """
    step = _step(_load_workflows()[filename], job_name, "id", step_id)
    script = _script(step, f"{filename}/{job_name}/{step_id}")
    assert MODEL_REFS_CALL in script, f"{filename} resolves the candidate somewhere else"
    prefix = {name: value for name, _, _, value in CANDIDATE_STEPS}[filename]
    return _published(
        model_refs.trial_rows(_a_config_tree(tmp_path, summarize), "", prefix=prefix)
    )


@pytest.mark.parametrize(("filename", "job_name", "step_id", "prefix"), CANDIDATE_STEPS)


def test_a_declared_draft_head_is_published_and_named_in_the_cache_key(
    filename: str, job_name: str, step_id: str, prefix: str, tmp_path: Path
) -> None:
    """The cache holds every file the candidate needs, so the key names every digest.

    A key that named only the target served a complete-looking entry with the
    draft head missing, and llama-server exits at load rather than at fetch - so
    the arm that restored it spent a runner hour and measured nothing.
    """
    draft = {
        "repo": "publisher/Model-GGUF",
        "revision": "0" * 40,
        "file": "mtp-model.gguf",
        "sha256": "b" * 64,
    }
    published = _candidate_outputs(
        filename, job_name, step_id, tmp_path, _an_entry(companion_files=[draft])
    )

    for field, value in draft.items():
        assert published[f"{prefix}draft_{field}"] == value

    key = published[f"{prefix}cache_key" if prefix else "cache_key"]
    assert key == _digest_of(_an_entry(), draft), "the key must name both files, to the byte"


@pytest.mark.parametrize(("filename", "job_name", "step_id", "prefix"), CANDIDATE_STEPS)


def test_the_key_moves_when_the_declared_set_moves(
    filename: str, job_name: str, step_id: str, prefix: str, tmp_path: Path
) -> None:
    """The key is over the whole declared set, so declaring one more file moves it.

    Two entries alike but for a companion must not share an entry: the one that
    needs two files would restore a complete-looking cache holding one, and
    llama-server exits at load rather than at fetch.

    The key is also not any single field. It was the target's own digest until
    this row, which read as a key and was a copy - so a second file could join
    the set with the key standing still.
    """
    alone = _candidate_outputs(filename, job_name, step_id, tmp_path / "alone", _an_entry())
    with_companion = _candidate_outputs(
        filename,
        job_name,
        step_id,
        tmp_path / "with-companion",
        _an_entry(
            companion_files=[
                {
                    "repo": "publisher/Model-GGUF",
                    "revision": "0" * 40,
                    "file": "mtp-model.gguf",
                    "sha256": "b" * 64,
                }
            ]
        ),
    )

    for field in ("repo", "revision", "file", "sha256"):
        assert alone[f"{prefix}draft_{field}"] == ""

    name = f"{prefix}cache_key" if prefix else "cache_key"
    assert alone[name] != with_companion[name], "one more file must move the key"
    assert alone[name] == _digest_of(_an_entry()), "the key is C5's serialisation"
    assert alone[name] not in set(_an_entry().values()), "the key is no single declared field"
    assert model_refs.SHA256_RE.fullmatch(alone[name]), "a key is 64 lowercase hex characters"


@pytest.mark.parametrize(("filename", "job_name", "step_id", "prefix"), CANDIDATE_STEPS)


def test_a_draft_head_that_declares_no_digest_is_refused(
    filename: str, job_name: str, step_id: str, prefix: str, tmp_path: Path
) -> None:
    """A head with no digest would be downloaded unchecked, which is the one thing we never do."""
    entry = _an_entry(
        companion_files=[{"repo": "p/M", "revision": "0" * 40, "file": "mtp.gguf"}]
    )

    with pytest.raises(SystemExit, match=re.escape("companion_files[0].sha256")):
        _candidate_outputs(filename, job_name, step_id, tmp_path, entry)


def test_two_config_roots_holding_one_entry_render_one_key(tmp_path: Path) -> None:
    """The key says what the files are, never how they were found.

    One caller reads the committed `config/` and another reads the scratch tree
    the candidate action builds under `backend/var/`. Putting the root into the
    key would make those two miss each other, and the second would refetch
    several gigabytes to land on bytes the first already paid for. A worker who
    "fixes" a cross-caller miss that way has broken the property, not the bug.
    """
    entry = _an_entry()
    one = _published(
        model_refs.trial_rows(_a_config_tree(tmp_path / "committed", entry), "", prefix="")
    )
    two = _published(
        model_refs.trial_rows(_a_config_tree(tmp_path / "scratch", entry), "", prefix="")
    )

    assert one["cache_key"] == two["cache_key"], "the root is how the files were found"
    assert one["cache_key"] == _digest_of(entry)
    assert one["weights_path"] == two["weights_path"] == f"{model_refs.MODELS_DIR}/{entry['file']}"


def test_the_pinned_keys_and_the_trial_keys_do_not_collide(tmp_path: Path) -> None:
    """One job writes both sets into one `$GITHUB_OUTPUT`, so a shared name wins twice.

    Scoped to the `--also-configured` call, which is the only case that writes
    two sets into one block. A global claim is false: the trial verb at an empty
    prefix also emits `draft_*`, exactly as the pinned verb does.
    """
    root = _a_config_tree(tmp_path, _an_entry())
    pinned = set(_published(model_refs.pinned_rows(root)))
    trial = set(_published(model_refs.trial_rows(root, "", prefix="")))

    assert pinned, "the also-configured call publishes nothing, so this checks nothing"
    assert pinned & trial == set(), f"one block cannot carry two answers: {sorted(pinned & trial)}"


def test_the_grammar_this_reader_copies_is_the_grammar_the_others_apply() -> None:
    """The copy is legal because this gate exists, and only while it does.

    `model_refs.py` may import nothing from `idhazh` and nothing from
    `measure_llm`: that module runs both by path in a job with no install and as
    a package under pytest, and no single plain import works in both. So the
    patterns are spelled twice and held equal here. A test may import both.

    `.flags` is checked beside `.pattern` because `re.IGNORECASE` on one side is
    a second grammar sharing one pattern string, and the strings would still be
    equal.
    """
    for name in ("REPO_RE", "REVISION_RE", "GGUF_RE"):
        here = getattr(model_refs, name)
        there = getattr(measure_llm, name)
        assert here.pattern == there.pattern, f"{name} is two grammars"
        assert here.flags == there.flags, f"{name} carries two flag sets"

    assert model_refs.SLUG_RE.pattern == SLUG_PATTERN, "the alias is a slug or it is not"


@pytest.mark.parametrize(
    ("field", "value", "says"),
    [
        ("file", "../../etc/passwd.gguf", "not a .gguf filename"),
        ("file", "x$(id).gguf", "not a .gguf filename"),
        ("file", "model.txt", "not a .gguf filename"),
        ("repo", "publisher/Model GGUF", "not a Hugging Face repository"),
        ("revision", "main", "not a 40-character commit"),
        ("sha256", "", "not a 64-character digest"),
        ("id", "Model_Q4", "not a slug"),
        ("quantisation", "Q4 K M", "not a quantisation"),
        ("byte_count", "0", "not a count of bytes"),
    ],
)
def test_a_value_a_shell_would_read_as_more_than_itself_is_refused(
    field: str, value: str, says: str, tmp_path: Path
) -> None:
    """Every one of these is pasted into a `run:` body, so this is where it stops.

    The refusal names four things in this order: the models file, where in it,
    the rule in plain words, and the value. Never the regex - a reader who
    wanted a character class would open the module.
    """
    root = _a_config_tree(tmp_path, _an_entry(**{field: value}))

    with pytest.raises(SystemExit) as refused:
        model_refs.trial_rows(root, "", prefix="")

    said = str(refused.value)
    assert "models/candidate.json" in said, "a refusal names the file it read"
    assert f"summarize.{field}:" in said, "a refusal names where in that file"
    assert says in said, "a refusal says the rule in plain words"
    assert repr(value) in said, "a refusal shows the value that broke it"
    assert "[A-Za-z" not in said, "a refusal prints the rule in words, never the pattern"


def test_a_companion_keeps_the_segment_rule_without_the_suffix_rule(tmp_path: Path) -> None:
    """A companion may be a projector, an adapter or a vocoder, so it carries no suffix.

    What it may not be is a path. `../../x.gguf` is one segment rule away from
    a file landing outside `backend/models`, and nothing downstream looks again.
    """
    projector = {
        "repo": "publisher/Model-GGUF",
        "revision": "0" * 40,
        "file": "mmproj-model-f16",
        "sha256": "b" * 64,
        "flag": "-md",
    }
    entry = _an_entry(byte_count=4215695776, companion_files=[projector])
    files = model_refs.list_model_files(_a_config_tree(tmp_path / "good", entry))
    assert [one.file for one in files] == ["model-Q4_K_M.gguf", "mmproj-model-f16"]
    assert files[1].landed_path == f"{model_refs.MODELS_DIR}/mmproj-model-f16"
    assert files[1].flag == "-md", "one leading dash is llama.cpp's short draft-model flag"
    assert files[0].flag == "", "the weights are named by the launcher, not by config"
    assert files[0].byte_count == "4215695776", "the declared size, as the string its rule reads"
    assert files[1].byte_count == "", "a companion that declares no size skips the cross-check"

    escaping = dict(projector, file="../../x.gguf")
    with pytest.raises(SystemExit, match=re.escape("not one path segment")):
        model_refs.list_model_files(
            _a_config_tree(tmp_path / "bad", _an_entry(companion_files=[escaping]))
        )


def test_the_search_that_finds_a_weights_fetch_still_finds_every_one_of_them() -> None:
    """The count, beside the set, because the two go blind in different ways.

    The set above catches a job that appeared. It cannot catch discovery itself
    narrowing: a search that stops matching four of the eight leaves an equality
    comparing a four-entry table against a four-entry answer, and it passes.
    That is what happens the moment a download stops spelling a URL in a `run:`
    body and starts calling a program, so the count is asserted as a number
    rather than inferred from a table that would shrink with it.

    If this ever has to move, the number moves in the commit that adds or
    retires the job, and the closed-world table below moves with it.
    """
    discovered = _weights_fetch_steps(_load_workflows())
    assert len(discovered) == WEIGHTS_FETCH_JOBS, (
        f"{len(discovered)} jobs download weights and this expects "
        f"{WEIGHTS_FETCH_JOBS}: {sorted(discovered)}"
    )

    converted = _shared_download_jobs(_load_workflows())
    assert converted, "no job fetches through the shared download, so the rules below check nothing"
    assert set(converted) <= set(discovered), sorted(set(converted) - set(discovered))


def test_no_file_the_platform_runs_spells_the_hub_host() -> None:
    """The Oracle. One address, in one program, and a caller cannot take it back.

    A download written into a workflow is a second answer to where the weights
    come from, and the one that drifts: it carries its own retry rule, its own
    `-f`, and its own idea of what a revision is. Once the fetch is a program,
    the host belongs to the program - so a file under `.github/` that spells it
    again has undone the conversion, whatever else it kept.

    Everything under `.github/` is read, not only the four workflows that fetch
    today, because a rule scoped to a list stops covering the file somebody adds
    beside it.
    """
    spelling = [
        path.relative_to(GITHUB_DIR).as_posix()
        for path in sorted(GITHUB_DIR.rglob("*"))
        if path.is_file()
        and path.name != HUB_HOST_EXCEPTION
        and HUB_HOST in path.read_text(encoding="utf-8")
    ]
    assert not spelling, f"the hub host belongs to the download program: {spelling}"


def _pasted(body: str) -> list[str]:
    """Every expression in a `run:` body that resolves to a value the reader published.

    `env:`, `with:`, `key:` and `if:` are out of scope on purpose: `env:` is
    where these values are allowed to be, and the whole rule is that a value
    reaches a shell as a variable rather than as text the Actions engine has
    already substituted.
    """
    found: list[str] = []
    for expression in re.findall(r"\$\{\{(.*?)\}\}", body, re.S):
        segments = expression.strip().split(".")
        if segments[0] not in PASTEABLE_CONTEXTS:
            continue
        # An expression can carry an operator after the value it reads, so the
        # last segment is cut at the first character a name cannot hold.
        name = re.split(r"[^A-Za-z0-9_-]", segments[-1], maxsplit=1)[0]
        if name in PUBLISHED_KEYS or any(name.endswith(f"_{key}") for key in PUBLISHED_KEYS):
            found.append(expression.strip())
    return found


def test_no_job_that_reaches_the_shared_download_pastes_a_value_the_reader_published() -> None:
    """The Oracle. A model value reaches a shell as a variable, never as text.

    The Actions engine substitutes an expression into a `run:` body before bash
    reads the line, so a value spelling `$(id)` runs and one spelling `../..`
    escapes. `model_refs.py` refuses both at the point it publishes them - but
    the refusal only holds while nothing downstream composes a second copy, and
    a `run:` body that pastes one has composed exactly that.

    The rule does not go green-and-empty once the relay job outputs are gone:
    the action's own reader step is a producer inside this set, and the steps
    that start the server and probe its health are its consumers.

    It says nothing about `measure.yml`'s own paste sites. Those four arms reach
    neither the shared action nor the shared download, so they are not in this
    set at all, and the file is plan 46's.
    """
    workflows = _load_workflows()
    closed = _shared_download_jobs(workflows)
    assert closed, "no job reaches the shared download, so this checks nothing"

    pasted: list[str] = []
    for filename, job_name in sorted(closed):
        for step in _steps(workflows[filename], job_name):
            body = step.get("run")
            if not isinstance(body, str):
                continue
            where = f"{filename}/{job_name}/{step.get('name')}"
            pasted += [f"{where}: {expression}" for expression in _pasted(body)]

    assert not pasted, "a model value is read through env, never pasted:\n  " + "\n  ".join(pasted)


def _one_step_running(
    workflows: Mapping[str, dict[str, object]], where: tuple[str, str], call: str
) -> dict[str, object]:
    """The single step of a job whose own body makes that call."""
    filename, job_name = where
    matches = [
        step
        for step in _steps(workflows[filename], job_name)
        if isinstance(step.get("run"), str) and call in str(step["run"])
    ]
    assert len(matches) == 1, f"{filename}/{job_name} must run `{call}` once, not {len(matches)}"
    return matches[0]


def test_every_file_the_model_declares_reaches_a_check_a_cache_hit_cannot_skip() -> None:
    """The Oracle. The check reads the declaration, so it cannot cover fewer files than it.

    The check used to be handed two filenames through `env` - the weights and
    one companion - while the cache key digested every file the entry declared.
    An entry declaring two companions therefore keyed on three files, fetched
    three, and checked two, and the unchecked one is the one llama-server exits
    at load over. Driving the check off the declaration instead makes the two
    counts the same number by construction.

    The step carries no `if:`, which is the half a restored cache entry needs:
    it is the one case where nobody watched the bytes arrive. That clause is
    asserted at the closed-world table above as well, and it is asserted twice
    on purpose - the most likely way this row goes wrong is somebody reading the
    second check as redundant and deleting it.
    """
    workflows = _load_workflows()
    closed = _shared_download_jobs(workflows)
    assert closed, "no job reaches the shared download, so this checks nothing"

    for where in sorted(closed):
        check = _one_step_running(workflows, where, VERIFY_MODEL_FILES)
        named = "/".join(where)
        assert "if" not in check, f"{named}: a restored cache is what most needs checking"
        body = str(check["run"])
        assert ".gguf" not in body, f"{named} names a weights file the declaration already holds"
        assert "sha256sum" not in body, (
            f"{named} checks a digest of its own beside the one the program checks"
        )


def _config_root_of(step: Mapping[str, object], where: str) -> str:
    """The config root a step hands the program, as written."""
    found = re.search(r"--config-root\s+(\S+)", str(step["run"]))
    assert found, f"{where} names no config root, so it reads whichever one is the default"
    return found.group(1)


def test_the_check_reads_the_config_root_the_download_read() -> None:
    """Two roots is two models, and the check then passes on bytes nobody asked for.

    One caller reads the committed `config/` and three read a scratch tree built
    under `backend/var/`. A check pointed at the committed root while the
    download read the scratch one compares the candidate's bytes against the
    incumbent's recorded digest - which fails honestly. Pointed the other way it
    passes, and the run measures a model nobody selected.
    """
    workflows = _load_workflows()
    closed = _shared_download_jobs(workflows)
    assert closed, "no job reaches the shared download, so this checks nothing"

    for where in sorted(closed):
        named = "/".join(where)
        download = _config_root_of(_one_step_running(workflows, where, DOWNLOAD_MODEL_FILES), named)
        check = _config_root_of(_one_step_running(workflows, where, VERIFY_MODEL_FILES), named)
        assert download == check, f"{named} downloads from {download} and checks against {check}"


def _resolve(
    template: str, published: Mapping[str, str], given: Mapping[str, str], where: str
) -> str:
    """The string Actions composes, with every expression replaced by its value.

    Two hops, because a composite action's key reads `inputs.x` and the caller
    fills that from a job output. Following the call is what makes this the key
    a runner really uses rather than the text the file holds.
    """

    def one(found: re.Match[str]) -> str:
        body = found.group(1).strip()
        name = body.split(".")[-1]
        if body.startswith("inputs.") and name in given:
            return _resolve(given[name], published, given, where)
        assert name in published, f"{where}: nothing the reader publishes is called {body}"
        return published[name]

    return re.sub(r"\$\{\{(.*?)\}\}", one, template, flags=re.S)


def _published_values(root: Path) -> dict[str, str]:
    """Every key a workflow can read, under the names its expressions spell.

    The pin is in it because a weights cache key names the build as well, and
    the build is the one half of that key the model file does not decide.
    """
    values = _published(model_refs.pinned_rows(root))
    values |= _published(model_refs.trial_rows(root, "", prefix="candidate_"))
    values["llama_cpp_build"] = PINNED_LLAMA_BUILD
    return values


def _shared_weights_keys(
    workflows: Mapping[str, dict[str, object]],
) -> dict[tuple[str, str], str]:
    """Every cache step over the weights whose key carries the one shared format."""
    return {
        (filename, job_name): key
        for filename, workflow in workflows.items()
        for job_name, key in _runtime_cache_keys(workflow)
        if key.startswith(SHARED_WEIGHTS_KEY_PREFIX)
    }


def test_a_companion_digest_moves_the_key_the_runner_resolves(tmp_path: Path) -> None:
    """The Oracle. The entry the cache holds is the whole declared set, so the key is too.

    The module's own key has covered every declared file since the reader
    landed. What a runner uses is the string the cache step composes, and that
    is a different question: a step naming the weights filename and its revision
    renders one key for two entries that differ in a companion, so the second
    restores a complete-looking entry with a file missing and llama-server exits
    at load rather than at fetch.

    Driven through the action's real key template and the real caller's `with:`
    block, because the defect this catches is a key that stops naming what the
    download reads - and only the composed string can say that.
    """
    workflows = _load_workflows()
    callers = sorted(_model_server_callers(workflows))
    assert callers, "no job calls the model-server action, so there is no key to resolve"
    filename, job_name = callers[0]
    template = _shared_weights_keys(workflows)[(filename, job_name)]
    given = _action_call(workflows[filename], job_name, MODEL_SERVER_ACTION)

    companion = {
        "repo": "publisher/Model-GGUF",
        "revision": "0" * 40,
        "file": "mtp-model.gguf",
        "sha256": "b" * 64,
    }
    keys = {
        _resolve(
            template,
            _published_values(
                _a_config_tree(
                    tmp_path / digest, _an_entry(companion_files=[dict(companion, sha256=digest)])
                )
            ),
            given,
            f"{filename}/{job_name}",
        )
        for digest in ("b" * 64, "c" * 64)
    }
    assert len(keys) == 2, f"two declared sets render one key, so one of them restores the other: {keys}"


def test_every_step_that_names_the_shared_weights_entry_resolves_to_one_string() -> None:
    """Two spellings of one key, and a move that takes only one of them is a silent refetch.

    The format is written in two places - the shared action and the pipeline-test
    workflow - because one is reached through a composite action and one is not.
    They are held equal by what they resolve to rather than by their text, so
    either may read its half from wherever suits it as long as the runner ends
    up at the same entry.

    Scoped to this one format. `qualify-` and `bench-` are deliberately
    different, because production must not share an entry with a bench
    candidate, so an equality across every cache step over the weights would be
    false by construction.
    """
    workflows = _load_workflows()
    keys = _shared_weights_keys(workflows)
    assert len(keys) > 1, f"the shared format is written once, so nothing can drift: {sorted(keys)}"

    published = _published_values(CONFIG_DIR)
    callers = _model_server_callers(workflows)
    resolved = {
        f"{filename}/{job_name}": _resolve(
            template,
            published,
            _action_call(workflows[filename], job_name, MODEL_SERVER_ACTION)
            if (filename, job_name) in callers
            else {},
            f"{filename}/{job_name}",
        )
        for (filename, job_name), template in sorted(keys.items())
    }
    assert "${{" not in "".join(resolved.values()), f"every half of the key must resolve: {resolved}"
    assert len(set(resolved.values())) == 1, f"one entry cannot have two names: {resolved}"


def test_two_declared_files_landing_on_one_name_are_refused(tmp_path: Path) -> None:
    """One would overwrite the other, and the digest check would pass on whichever won.

    A whole-set rule, so the refusal names every participating location rather
    than one file that is not wrong on its own.
    """
    twin = {
        "repo": "publisher/Model-GGUF",
        "revision": "0" * 40,
        "file": "model-Q4_K_M.gguf",
        "sha256": "b" * 64,
    }
    root = _a_config_tree(tmp_path, _an_entry(companion_files=[twin]))

    with pytest.raises(SystemExit) as refused:
        model_refs.list_model_files(root)

    said = str(refused.value)
    assert "two files land on one name" in said
    assert "summarize.file 'model-Q4_K_M.gguf'" in said
    assert "summarize.companion_files[0].file 'model-Q4_K_M.gguf'" in said


def test_a_second_companion_is_refused_rather_than_dropped(tmp_path: Path) -> None:
    """The projection publishes one companion while the key digests every one.

    So an entry declaring two keyed on two files and fetched one - a cache entry
    that looks complete with a file missing, which is the failure the key exists
    to prevent. It is refused by name and by count, never truncated.
    """
    two = [
        {
            "repo": "publisher/Model-GGUF",
            "revision": "0" * 40,
            "file": f"companion-{index}.gguf",
            "sha256": f"{index}" * 64,
        }
        for index in (1, 2)
    ]
    root = _a_config_tree(tmp_path, _an_entry(companion_files=two))

    assert len(model_refs.list_model_files(root)) == 3, "the reader still sees every file"
    with pytest.raises(SystemExit) as refused:
        model_refs.trial_rows(root, "", prefix="")

    said = str(refused.value)
    assert "(2)" in said, "a refusal names the count"
    assert "companion-1.gguf" in said and "companion-2.gguf" in said, "it truncates nothing"


def test_a_key_over_seven_files_still_fits_the_cap_a_cache_key_has(tmp_path: Path) -> None:
    """A cache key may carry 512 characters. The join this replaced reached 519 at seven.

    A digest is fixed-width, so the count of declared files cannot push the key
    past the cap - and a key Actions truncates is a key two entries share.
    """
    seven = [
        {
            "repo": "publisher/Model-GGUF",
            "revision": "0" * 40,
            "file": f"companion-{index}.gguf",
            "sha256": f"{index}" * 64,
        }
        for index in range(1, 8)
    ]
    files = model_refs.list_model_files(
        _a_config_tree(tmp_path, _an_entry(companion_files=seven))
    )

    assert len(files) == 8
    key = _digest_of(_an_entry(), *seven)
    assert len(key) == 64
    assert key != _digest_of(_an_entry(), *seven[:6]), "the key covers every declared file"
