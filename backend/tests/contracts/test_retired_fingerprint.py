"""What happens to a payload that still carries the pipeline fingerprint?"""

from __future__ import annotations

import json

import pytest
from conftest import CONTRACT_FIXTURES_DIR, REPO_ROOT, read_text
from pydantic import ValidationError

from idhazh.contracts import CONTRACTS, canonical_json

from ._config import (
    FINGERPRINT_FIXTURES,
    FINGERPRINT_POPPERS,
    FINGERPRINT_SURVIVORS,
    misspell,
)

pytestmark = pytest.mark.contract


def test_nothing_reads_the_pipeline_fingerprint_except_the_places_named_here() -> None:
    """The stamp stopped gating, and the field is gone from nine of the ten shapes.

    A fixed-size read of code a person wrote, never of data a run appended
    (`CLAUDE.md` section 13). It grows with the codebase and not with the
    archive, so a day that publishes changes nothing here.

    The gate is not "the name appears nowhere", because two shapes have to name
    the key to pop it and one still declares the field. Both are named above,
    which is what makes this a rule rather than a habit.
    """
    roots = (
        (REPO_ROOT / "backend" / "idhazh", ("*.py",)),
        (REPO_ROOT / "frontend" / "src", ("*.ts", "*.svelte", "*.js")),
    )
    found: set[str] = set()
    for root, patterns in roots:
        for pattern in patterns:
            for path in root.rglob(pattern):
                if "pipeline_fingerprint" in path.read_text(encoding="utf-8"):
                    found.add(path.relative_to(REPO_ROOT).as_posix())

    assert found == set(FINGERPRINT_SURVIVORS), (
        "a module names pipeline_fingerprint that is not on the survivor list. "
        "Either it is a reader and has to stop reading, or it is a survivor and "
        "has to say why it survives."
    )


@pytest.mark.parametrize(("name", "key"), [(n, k) for n, (k, _) in FINGERPRINT_POPPERS.items()])
def test_a_payload_carrying_the_retired_key_parses_and_comes_back_without_it(
    name: str, key: str
) -> None:
    """The read-side migration `CLAUDE.md` section 11 owes for a breaking removal.

    Driven from a payload a real run wrote - `state/day-metrics/2026/09/11.json`
    and `frontend/public/digest/2026/09/11/run.json`, copied into
    `tests/fixtures/` so the oracle cannot change when the archive does.
    """
    contract = {model.__name__: model for model in CONTRACTS}[name]
    payload = json.loads(read_text(FINGERPRINT_FIXTURES[name]))
    assert key in canonical_json(payload), f"the fixture no longer carries {key}"

    parsed = contract.model_validate(payload)

    assert key not in canonical_json(parsed.model_dump(mode="json"))
    assert key not in contract.model_fields


@pytest.mark.parametrize(
    ("name", "key", "wrong"), [(n, k, w) for n, (k, w) in FINGERPRINT_POPPERS.items()]
)
def test_the_same_payload_with_the_key_misspelt_is_still_refused(
    name: str, key: str, wrong: str
) -> None:
    """The case that matters, and the reason the popper names its key.

    A migration written as "drop whatever the model does not declare" passes the
    test above perfectly and turns `extra="forbid"` into `extra="ignore"` for the
    shape it sits on - so a misspelt key in a hand-written payload would parse
    and the value it was meant to carry would simply be absent.

    The misspelling is made here rather than committed as a second fixture,
    because renaming one key of the payload above is what proves the two differ
    in the spelling and in nothing else.
    """
    contract = {model.__name__: model for model in CONTRACTS}[name]
    payload = misspell(json.loads(read_text(FINGERPRINT_FIXTURES[name])), key, wrong)

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        contract.model_validate(payload)


def test_no_other_contract_learned_to_accept_the_retired_key() -> None:
    """The popper is opted into by two shapes and inherited by none.

    Written on `Model` or `Contract` instead, a popper reading a shared key list
    passes both cases above and silently opens every contract in the repository
    to a key only two of them ever held. Nothing else can fail that, which is why
    this case is not optional.

    Driven from the committed contract fixtures, which are a fixed set of files a
    person wrote (`CLAUDE.md` section 13). `EvalRow` is skipped because it still
    declares the field.
    """
    checked = 0
    for model in CONTRACTS:
        key = "pipeline_fingerprint"
        if model.__name__ in FINGERPRINT_POPPERS or key in model.model_fields:
            continue
        directory = CONTRACT_FIXTURES_DIR / model.__schema_stem__
        for path in sorted(directory.glob("*.json")):
            payload = json.loads(read_text(path))
            if not isinstance(payload, dict):
                continue
            with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
                model.model_validate({**payload, key: "a" * 64})
            checked += 1
            break

    assert checked >= 30, f"only {checked} contracts were offered the retired key"
