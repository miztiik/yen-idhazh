"""Is swapping a model one line, and must every entry declare the settings its weights run under?"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest
from conftest import CONFIG_DIR, CONTRACT_FIXTURES_DIR, read_text
from pydantic import ValidationError

from idhazh import config
from idhazh.contracts import canonical_json
from idhazh.contracts.app_config import SUPERSEDED_APP_NAMES, AppConfig
from idhazh.contracts.knobs.models import SUPERSEDED_MODELS_NAMES, ModelsConfig
from idhazh.contracts.knobs.turns import SystemPlacement
from idhazh.contracts.run_manifest import RunManifest

from ._fixtures import (
    committed_models,
    committed_models_raw,
    copy_config,
    entry_with,
    swapped_summarizer,
)

pytestmark = pytest.mark.contract


def test_swapping_the_model_is_one_line_and_reverting_is_the_same_line(tmp_path: Path) -> None:
    """The pointer is the whole swap, both ways.

    Before 2026-09-14 a swap was eleven lines edited in place in the file every
    other knob lives in, and a revert had to rebuild the previous model's
    measured numbers out of git history. Both models sit on disk now, so this
    moves one string and reads the resolved entry back - then moves it back and
    reads the incumbent.

    The candidate is BUILT rather than copied from a committed second model,
    because there is only one committed model and a test that waited for a
    second one would prove nothing until the day it was needed.
    """
    incumbent = copy_config(tmp_path)
    candidate = "models/other-model-q4km.json"
    other = committed_models_raw()
    other["summarize"] |= {
        "id": "some-other-model-q4-k-m",
        "repo": "someone/Other-GGUF",
        "file": "Other-Q4_K_M.gguf",
        "revision": "f" * 40,
        "sha256": "1" * 64,
        "hf_base_repo": None,
    }
    other["summarize"]["inference"]["declared_for"] = "1" * 64
    other["summarize"]["turns"]["declared_for"] = "1" * 64
    (tmp_path / "config" / candidate).write_text(
        canonical_json(other), encoding="utf-8", newline="\n"
    )
    before = read_text(tmp_path / "config" / "idhazh.json")

    point_at(tmp_path, candidate)
    swapped = config.load(tmp_path / "config")
    assert swapped.models.summarize.id == "some-other-model-q4-k-m"
    assert swapped.models.summarize.sha256 == "1" * 64
    assert changed_lines(before, read_text(tmp_path / "config" / "idhazh.json")) == 1

    point_at(tmp_path, incumbent)
    assert config.load(tmp_path / "config").models == committed_models()
    assert read_text(tmp_path / "config" / "idhazh.json") == before, (
        "the revert is the same one line, so the file comes back byte-identical"
    )


def point_at(root: Path, models_file: str) -> None:
    raw = json.loads(read_text(root / "config" / "idhazh.json"))
    raw["models_file"] = models_file
    (root / "config" / "idhazh.json").write_text(
        canonical_json(raw), encoding="utf-8", newline="\n"
    )


def test_folding_the_system_text_without_a_joiner_is_refused() -> None:
    """Decision 2, first half. The separator is what keeps the two blocks apart.

    Absent, the last instruction and the opening fence of the untrusted block
    render on one line. The prompt is still well formed, the grammar still
    accepts the reply, and the only symptom is a worse summary.
    """
    with pytest.raises(ValidationError) as raised:
        ModelsConfig.model_validate(entry_with(system_role="fold_into_first_user"))

    assert "system_joiner is required under system_role='fold_into_first_user'" in str(
        raised.value
    )


def test_a_joiner_declared_beside_a_system_turn_is_refused() -> None:
    """Decision 2, second half. A dead field is a field somebody will trust.

    `own_turn` gives the system text a turn of its own, so nothing joins it to
    anything. A joiner set here is a value an operator chose, a reviewer read,
    and no render ever applied.
    """
    with pytest.raises(ValidationError) as raised:
        ModelsConfig.model_validate(entry_with(system_role="own_turn", system_joiner="\n\n"))

    assert "where the system text has a turn of its own" in str(raised.value)


def test_a_fold_that_declares_a_joiner_loads() -> None:
    """The bite proof for both halves: the pair the refusals permit is legal."""
    folded = ModelsConfig.model_validate(
        entry_with(system_role="fold_into_first_user", system_joiner="\n\n")
    )

    assert folded.summarize.turns.system_joiner == "\n\n"


def test_a_template_that_reads_no_keyword_may_not_be_asked_to_think() -> None:
    """Decision 3, second half. Both halves are facts about the same template.

    A null keyword means the request carries no `chat_template_kwargs` at all,
    so a declared closing marker asks for reasoning through a channel nothing
    sends.
    """
    payload = entry_with(thinking_kwarg=None, thinking_close="</think>")

    with pytest.raises(ValidationError) as raised:
        ModelsConfig.model_validate(payload)

    assert "sends no chat_template_kwargs at all" in str(raised.value)


def test_a_template_that_reads_no_keyword_loads_with_reasoning_off() -> None:
    """The bite proof. Null is a legal declaration, not a broken entry."""
    silent = ModelsConfig.model_validate(entry_with(thinking_kwarg=None))

    assert silent.summarize.turns.thinking_kwarg is None
    assert silent.summarize.turns.thinks is False


def test_the_closing_marker_is_the_whole_declaration_that_reasoning_is_wanted() -> None:
    """One place, so there is no flag to disagree with it.

    `thinks` is read all over the pipeline - the render, the budget, the chat
    keyword and three refusals - and every one of them reads this field. A
    second switch beside it was retired for that reason.
    """
    quiet = ModelsConfig.model_validate(entry_with())
    loud = ModelsConfig.model_validate(entry_with(thinking_close="</think>"))

    assert quiet.summarize.turns.thinks is False
    assert loud.summarize.turns.thinks is True
    assert loud.summarize.turns.thinking_close == "</think>"


def test_a_config_that_still_spells_the_retired_thinking_flag_is_refused_by_name() -> None:
    """The read-side migration for a knob that moved block, not just name.

    Every model here forbids unknown keys, so the old spelling already fails -
    with "extra inputs are not permitted", which does not tell an operator that
    reasoning is declared on the envelope now. The message names the key that
    replaced it, in full, because `inference.turns.thinking_close` is not a path
    that exists.
    """
    payload = entry_with()
    payload["summarize"]["inference"]["thinking"] = False

    with pytest.raises(ValidationError) as raised:
        ModelsConfig.model_validate(payload)

    assert "models.<role>.turns.thinking_close" in str(raised.value)


def test_a_config_that_still_spells_the_one_output_budget_is_refused_by_name() -> None:
    """One budget over two spans could not say which span overran."""
    payload = entry_with()
    payload["summarize"]["inference"]["max_output_tokens"] = 900

    with pytest.raises(ValidationError) as raised:
        ModelsConfig.model_validate(payload)

    assert "models.<role>.inference.max_answer_tokens" in str(raised.value)


def test_the_committed_entry_names_the_keyword_rather_than_inheriting_it() -> None:
    """The name is a model fact, so the file that names the weights names it too.

    It was spelled in `backend/idhazh/llm/server.py` and sent to every model
    until 2026-09-14. The default is the incumbent's, which is why this asserts
    the file carries it rather than asserting the default resolves.
    """
    raw = committed_models_raw()

    assert raw["summarize"]["turns"]["thinking_kwarg"] == "enable_thinking"
    assert committed_models().summarize.turns.system_role is SystemPlacement.OWN_TURN


def changed_lines(before: str, after: str) -> int:
    old = before.splitlines()
    new = after.splitlines()
    assert len(old) == len(new), "a swap that adds or removes a line is not a one-line swap"
    return sum(1 for a, b in zip(old, new, strict=True) if a != b)


def test_a_config_that_still_carries_the_old_models_block_is_refused_by_name() -> None:
    """The read-side migration `CLAUDE.md` section 11 owes for the removal.

    Refused rather than lifted onto the new file. A lift would read one model
    out of the old block while `models_file` named another file, and the run
    would stand a server up on whichever won - which is the failure this row
    exists to end, one level up.
    """
    raw = json.loads(read_text(CONFIG_DIR / "idhazh.json"))
    raw["models"] = {"summarize": committed_models_raw()["summarize"]}

    with pytest.raises(ValidationError) as raised:
        AppConfig.model_validate(raw)

    assert "config.models is now config.models_file" in str(raised.value)
    assert SUPERSEDED_APP_NAMES["models"] == "models_file"


def test_the_pointer_may_not_leave_the_models_directory() -> None:
    """An operator's edit becomes a path this build opens, so the grammar bounds it.

    Held by the schema rather than checked in the loader, which is what makes it
    a refusal at load rather than a read four hundred seconds into a run.
    """
    for escape in (
        "../secrets.json",
        "models/../../secrets.json",
        "/etc/passwd",
        "models\\qwen.json",
        "models/qwen.txt",
        "idhazh.json",
    ):
        with pytest.raises(ValidationError, match="should match pattern"):
            AppConfig.model_validate({"models_file": escape})


def test_the_model_file_is_digested_with_the_rest_of_the_config() -> None:
    """A run that did not record it could not say which model's numbers it read.

    `models_file` names the file, so the digest of `config/idhazh.json` moves
    when the POINTER moves and says nothing about what the file it points at
    says. Both have to travel or a re-tuned model file is invisible to the
    record.
    """
    settings = config.load(CONFIG_DIR)
    recorded = {digest.path: digest.sha256 for digest in settings.digests}

    assert f"config/{settings.app.models_file}" in recorded
    text = read_text(CONFIG_DIR / settings.app.models_file)
    assert recorded[f"config/{settings.app.models_file}"] == sha256_of(text)


def sha256_of(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_a_model_swap_can_no_longer_inherit_settings_nothing_declared_for_it() -> None:
    """The Oracle: new weights under an untouched settings block are refused.

    Every number in an `inference` block is a measurement about one model on one
    runner. Until this gate, `models.summarize` could name a different
    repository, file, revision and digest with the block left exactly where it
    was and `AppConfig.model_validate` raised nothing - so the run stood a server
    up on numbers derived for weights it never opened and published a whole
    plausible day.
    """
    committed = committed_models()
    assert committed.summarize.inference.declared_for == committed.summarize.sha256

    with pytest.raises(ValidationError) as raised:
        ModelsConfig.model_validate(swapped_summarizer())
    message = str(raised.value)
    assert "models.summarize.inference" in message, "the message names the block"
    assert "1" * 64 in message, "and the weights the entry now names"


def test_a_refused_model_file_is_named_by_the_loader(tmp_path: Path) -> None:
    """Every model has a file of its own, so a refusal has to say which one.

    The validator cannot: it is handed a payload, not a path. So the loader adds
    the address, and this is the case that proves it rather than trusting it - an
    operator with two model files on disk and a refusal naming neither has to
    guess which one they broke.
    """
    written = copy_config(tmp_path, models=swapped_summarizer())

    with pytest.raises(ValueError) as raised:
        config.load(tmp_path / "config")

    message = str(raised.value)
    assert f"config/{written}" in message, "the refusal names the file that is wrong"
    assert "models.summarize.inference" in message, "and the block inside it"


def test_an_entry_that_declares_no_settings_of_its_own_is_refused_by_name() -> None:
    """A new entry written with no block of its own does not fall back to one."""
    raw = swapped_summarizer()
    del raw["summarize"]["inference"]
    with pytest.raises(ValidationError, match=re.escape("models.summarize.inference")):
        ModelsConfig.model_validate(raw)


def test_the_one_shared_settings_block_is_refused_by_name() -> None:
    """`models.inference` was one block applied to two models. It is gone.

    Refused rather than lifted onto both entries. A lift is the silent
    inheritance this row exists to end: it would hand a swapped entry the
    numbers the previous weights were measured on and raise nothing.

    It is the one entry in this map with a replacement to name. The other two
    are roles that were retired outright, so they carry an empty string and the
    refusal says so rather than inventing a successor.
    """
    raw = committed_models_raw()
    raw["inference"] = {"n_ctx": 8192}
    with pytest.raises(ValidationError) as raised:
        ModelsConfig.model_validate(raw)
    assert "models.inference is now models.<role>.inference" in str(raised.value)
    assert SUPERSEDED_MODELS_NAMES["inference"] == "models.<role>.inference"
    assert not SUPERSEDED_MODELS_NAMES["visual_planner"]
    assert not SUPERSEDED_MODELS_NAMES["route"]


def test_every_committed_model_entry_declares_the_weights_its_settings_are_for() -> None:
    """The committed file states the pairing rather than implying it."""
    raw = committed_models_raw()
    assert "inference" not in raw
    for role in ModelsConfig.roles():
        entry = raw[role]
        assert entry["inference"]["declared_for"] == entry["sha256"], role


def test_every_model_file_loads_and_not_only_the_one_the_pointer_names() -> None:
    """A file `models_file` does not currently name is still a file it can name.

    Only the active entry was ever validated, so an alternative sat unchecked
    until the day somebody switched to it - and that day is a pipeline run, not
    a test. The directory is hand-authored and bounded by how many models this
    project supports, so reading all of it costs what the code costs rather than
    what the archive has piled up (`CLAUDE.md` Guardrail #12).
    """
    files = sorted((CONFIG_DIR / "models").glob("*.json"))
    assert len(files) >= 2, "the swap has nothing to swap between"

    for path in files:
        entry = ModelsConfig.from_json(read_text(path)).summarize
        assert entry.inference.declared_for == entry.sha256, path.name
        assert entry.turns.declared_for == entry.sha256, path.name


def test_no_committed_file_declares_a_second_entry() -> None:
    """The optional entry is off by default, and the default is what ships.

    A knob whose default flipped in the same commit that declared it is a
    feature nobody agreed to run (Guardrail #6). This one is filled the day a
    replay says a reasoned verdict is a better verdict, and not before.
    """
    for path in sorted((CONFIG_DIR / "models").glob("*.json")):
        declared = ModelsConfig.from_json(read_text(path))
        assert declared.judge is None, path.name
        assert [name for name, _ in declared.entries()] == ["summarize"], path.name


def test_a_second_entry_naming_other_weights_is_refused() -> None:
    """No server is started for it, so it decodes on whatever the running one holds.

    Nothing raises in that case: every reply parses, every row writes, and every
    verdict is filed against a model that never saw the pair.
    """
    raw = committed_models_raw()
    elsewhere = json.loads(json.dumps(raw["summarize"]))
    elsewhere["sha256"] = "f" * 64
    elsewhere["inference"]["declared_for"] = "f" * 64
    elsewhere["turns"]["declared_for"] = "f" * 64

    ModelsConfig.model_validate(raw | {"judge": raw["summarize"]})
    with pytest.raises(ValidationError) as raised:
        ModelsConfig.model_validate(raw | {"judge": elsewhere})
    assert "decodes on the weights the summariser's server holds" in str(raised.value)


def test_a_run_manifest_that_named_a_draft_head_still_reads() -> None:
    """The read side: six committed `run.json` files carry `draft` on `model_ref`.

    `frontend/src/lib/server/payload.ts` opens every one of them at each build,
    and `Model` forbids a key it no longer declares - so without the migration
    the field left in a commit that today's build could not read yesterday's run
    with (`CLAUDE.md` section 11). Proved by putting the key back rather than by
    reading a committed day, so it cannot age out of retention.
    """
    current = json.loads(read_text(CONTRACT_FIXTURES_DIR / "run-manifest" / "two-runs.json"))
    for run in current["runs"]:
        for used in run["models"]:
            used["model_ref"]["draft"] = None

    parsed = RunManifest.model_validate(current)

    assert not hasattr(parsed.runs[0].models[0].model_ref, "draft")


def test_a_run_manifest_written_before_the_settings_moved_still_reads() -> None:
    """The read side: a `model_ref` with no settings block opens on the defaults.

    Nineteen manifests sit under `frontend/public/digest/` with the shape
    `model_ref` had yesterday, and `frontend/src/lib/server/payload.ts` opens
    them at every build. A block that could not default would make each of them
    a payload today's build cannot read (`CLAUDE.md` section 11). Proved by
    removing the key rather than by reading a committed day, so it cannot age
    out of retention.
    """
    current = json.loads(read_text(CONTRACT_FIXTURES_DIR / "run-manifest" / "two-runs.json"))
    for run in current["runs"]:
        for use in run["models"]:
            del use["model_ref"]["inference"]

    older = RunManifest.model_validate(current)
    entry = older.runs[0].models[0].model_ref
    assert entry.inference.declared_for is None
    assert entry.inference.n_ctx == 8192, "the contract default, not a guess"
