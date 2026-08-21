"""The injection canaries: five planted attacks, asserted on every change.

This suite lands before the summarizer, not after, so the summarizer is written
against a live assertion rather than audited afterwards. A prompt asking a model
to ignore embedded instructions is a request; the controls asserted here - the
sanitizer, the fence, and the pinned output shape - are the controls
(Holy Law #11).

The oracle is that all five fail to inject, and a single success fails the
build. The counter-oracle matters just as much: every canary also declares text
that MUST survive, because a sanitizer that deletes the article passes an
absence check trivially and produces nothing worth reading.

No mocks and no network (Holy Law #7): every attack is a committed fixture.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any, Literal

import pytest
from conftest import CONTRACT_FIXTURES_DIR, FIXTURES_DIR, REPO_ROOT, read_text
from pydantic import ValidationError

from idhazh.contracts.base import Model
from idhazh.contracts.summary import Summary
from idhazh.sanitize import FENCE_CLOSE, FENCE_OPEN, sanitize, untrusted_block

CANARY_DIR = FIXTURES_DIR / "canaries"

#: The acceptance gate names these five and no fewer. A canary file that
#: disappears is a control that stopped being asserted.
REQUIRED_ATTACKS = frozenset(
    {
        "direct-instruction-override",
        "fake-system-delimiter",
        "encoded-payload",
        "tool-call-injection",
        "exfiltration-via-url",
    }
)

# Modules the pipeline has no reason to reach for, and every reason not to:
# each one turns a string into an action, which is what an injection wants.
FORBIDDEN_IMPORTS = frozenset({"subprocess", "os.system", "pty", "shlex"})
FORBIDDEN_CALLS = frozenset({"eval", "exec", "compile", "__import__"})


class Canary(Model):
    """One planted attack, and what the pipeline's controls must do to it."""

    name: str
    attack: str
    neutralised_by: Literal["framing", "sanitizer", "schema"]
    source_url: str
    raw_title: str
    raw_text: str
    must_not_survive: list[str]
    must_survive: list[str]
    forbidden_output: dict[str, Any]


def canaries() -> list[Canary]:
    return [Canary.model_validate_json(read_text(p)) for p in sorted(CANARY_DIR.glob("*.json"))]


ALL = canaries()


# --- The Oracle: nothing injects -------------------------------------------


def test_every_required_attack_is_covered() -> None:
    assert {canary.name for canary in ALL} == REQUIRED_ATTACKS


@pytest.mark.parametrize("canary", ALL, ids=lambda c: c.name)
def test_the_attack_does_not_survive_the_boundary(canary: Canary) -> None:
    cleaned = sanitize(canary.raw_text)
    for planted in canary.must_not_survive:
        assert planted not in cleaned, f"{canary.name}: {planted!r} crossed the trust boundary"


@pytest.mark.parametrize("canary", ALL, ids=lambda c: c.name)
def test_the_article_survives_the_boundary(canary: Canary) -> None:
    """The counter-oracle: a sanitizer that deletes everything is not a control."""
    cleaned = sanitize(canary.raw_text)
    for kept in canary.must_survive:
        assert kept in cleaned, f"{canary.name}: sanitization ate the article"


@pytest.mark.parametrize("canary", ALL, ids=lambda c: c.name)
def test_source_text_cannot_close_the_fence_it_sits_in(canary: Canary) -> None:
    """Decision 1: the text is delimited and labelled data, and cannot escape."""
    block = untrusted_block(canary.raw_text)
    assert block.startswith(FENCE_OPEN)
    assert block.endswith(FENCE_CLOSE)
    assert block.count(FENCE_OPEN) == 1
    assert block.count(FENCE_CLOSE) == 1


@pytest.mark.parametrize("canary", ALL, ids=lambda c: c.name)
def test_the_boundary_is_idempotent(canary: Canary) -> None:
    """A defensive second pass must be free, so no caller has to remember order."""
    once = sanitize(canary.raw_text)
    assert sanitize(once) == once


def test_an_injected_field_cannot_change_the_output_shape() -> None:
    """Decision 2: the shape is pinned by schema, so content is all an attack can move."""
    base: dict[str, Any] = json.loads(read_text(CONTRACT_FIXTURES_DIR / "summary" / "ok.json"))
    # Without this the raises below could pass for any reason at all.
    Summary.model_validate(base)

    injected = [c for c in ALL if c.forbidden_output]
    assert injected, "at least one canary must attack the output shape"
    for canary in injected:
        with pytest.raises(ValidationError):
            Summary.model_validate({**base, **canary.forbidden_output})


# --- Decision 3: model output never becomes an action ----------------------


def test_a_summary_payload_cannot_carry_an_address() -> None:
    """Nothing the model writes is shaped like a URL or a path, so nothing can dereference it."""
    schema = Summary.model_json_schema()
    for name, spec in schema["properties"].items():
        rendered = json.dumps(spec)
        assert "uri" not in rendered, f"Summary.{name} is address-shaped"
        assert "https?://" not in rendered, f"Summary.{name} is address-shaped"


def test_no_pipeline_module_can_turn_a_string_into_an_action() -> None:
    """Decision 3, made structural: the machinery an injection would need is absent."""
    package = REPO_ROOT / "backend" / "idhazh"
    for module in sorted(package.rglob("*.py")):
        tree = ast.parse(read_text(module), filename=str(module))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name not in FORBIDDEN_IMPORTS, f"{module.name} imports {alias.name}"
            elif isinstance(node, ast.ImportFrom) and node.module in FORBIDDEN_IMPORTS:
                pytest.fail(f"{module.name} imports {node.module}")
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in FORBIDDEN_CALLS, f"{module.name} calls {node.func.id}"


# --- Housekeeping the fixtures have to keep --------------------------------


@pytest.mark.parametrize("path", sorted(CANARY_DIR.glob("*.json")), ids=lambda p: p.name)
def test_a_canary_file_is_ascii_and_lf(path: Path) -> None:
    """The attack payloads are escaped, so the file itself stays reviewable."""
    raw = path.read_bytes()
    raw.decode("ascii")
    assert b"\r\n" not in raw


@pytest.mark.parametrize("canary", ALL, ids=lambda c: c.name)
def test_a_canary_names_its_file(canary: Canary) -> None:
    assert (CANARY_DIR / f"{canary.name}.json").exists()
