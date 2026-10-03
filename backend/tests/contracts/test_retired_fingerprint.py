"""What happens to a payload that still carries the pipeline fingerprint?"""

from __future__ import annotations

import json

import pytest
from conftest import read_text
from pydantic import ValidationError

from idhazh.contracts import CONTRACTS, canonical_json

from ._config import (
    FINGERPRINT_FIXTURES,
    FINGERPRINT_POPPERS,
    misspell,
)
from ._fixtures import fixture_paths

pytestmark = pytest.mark.contract


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

    Driven from the named fixture inputs. `EvalRow` still declares the field.
    """
    checked = 0
    fixtures = {path.parent.name: path for path in reversed(fixture_paths())}
    for model in CONTRACTS:
        key = "pipeline_fingerprint"
        if model.__name__ in FINGERPRINT_POPPERS or key in model.model_fields:
            continue
        payload = json.loads(read_text(fixtures[model.__schema_stem__]))
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            model.model_validate({**payload, key: "a" * 64})
        checked += 1

    assert checked >= 30, f"only {checked} contracts were offered the retired key"
