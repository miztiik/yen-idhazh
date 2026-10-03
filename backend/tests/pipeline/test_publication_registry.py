"""Does discovery find every check on disk, and refuse every way of mis-wiring one?

Unit tier (CLAUDE.md section 13). A registry that silently ran three of its
four rules would pass a day it should have refused, and nothing in the log
would say a rule was missing - so each of the four wiring faults is raised, and
each one is held here by the message an operator would read, and by the exit
code the CLI turns it into.

The bijection test is the other half: it names the four checks that must be
bound, so adding a file to `checks/` without meaning to, or deleting one, fails
here rather than in a quiet publish.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from idhazh.cli import main
from idhazh.contracts.ledger_name import LedgerName
from idhazh.publication_checks import registry, runner
from idhazh.publication_checks.registry import (
    Check,
    CheckResult,
    CheckScope,
    PublicationCheckError,
    discover,
    validate_registry,
)

#: Every check this repository ships, and the scope each is handed. A new file
#: under `checks/` joins this tuple in the same change, which is the point.
SHIPPED = (
    ("console", CheckScope.TREE),
    ("pictures", CheckScope.DAY),
    ("planned-items-reconciliation", CheckScope.DAY),
    ("projection", CheckScope.DAY),
)


def a_check(name: str, ledger: LedgerName | None = None) -> Check:
    return Check(
        name=name, scope=CheckScope.DAY, run=lambda _ctx: CheckResult(), ledger=ledger
    )


def a_package(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, **modules: str) -> None:
    """A throwaway checks package on disk, pointed at by `CHECKS_PACKAGE`.

    Written to a real directory and imported for real, because what is under
    test is the walk over a package - a fake module object would prove that a
    dict lookup works.
    """
    package = tmp_path / "scratch_checks"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    for name, body in modules.items():
        (package / f"{name}.py").write_text(body, encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(registry, "CHECKS_PACKAGE", "scratch_checks")
    for name in list(sys.modules):
        if name == "scratch_checks" or name.startswith("scratch_checks."):
            monkeypatch.delitem(sys.modules, name)


DECLARES = """
from idhazh.publication_checks.registry import Check, CheckResult, CheckScope

CHECK = Check(name={name!r}, scope=CheckScope.DAY, run=lambda ctx: CheckResult())
"""


def test_discovery_binds_every_check_this_repository_ships() -> None:
    """The bijection. A file added to `checks/` and never run is the failure."""
    found = discover()

    assert [(check.name, check.scope) for check in found] == list(SHIPPED)
    assert all(check.ledger is None for check in found), "no shipped check files rows"


def test_a_check_module_that_will_not_import_takes_the_run_down(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Failure 1. A gate that skipped an unimportable rule would pass on silence."""
    a_package(tmp_path, monkeypatch, broken="raise RuntimeError('the rule is broken')")

    with pytest.raises(RuntimeError, match="the rule is broken"):
        discover()


def test_a_module_declaring_no_check_is_named(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Failure 2. A file that looks like a rule and declares none is a typo."""
    a_package(tmp_path, monkeypatch, empty="WRONG_NAME = 1\n")

    with pytest.raises(PublicationCheckError, match="declares no CHECK/CHECKS"):
        discover()


def test_two_modules_claiming_one_name_are_both_named(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Failure 3. Silently, the second would replace the first and run alone."""
    a_package(
        tmp_path,
        monkeypatch,
        first=DECLARES.format(name="pictures"),
        second=DECLARES.format(name="pictures"),
    )

    with pytest.raises(PublicationCheckError, match="two modules declare check 'pictures'"):
        discover()


def test_a_check_naming_a_ledger_the_door_has_no_entry_for_is_refused() -> None:
    """Failure 4. The write would fail after the gate had already passed the day.

    The eval ledger's ID folder is a real ledger the door has no entry for, so
    this is the fault an author actually makes: a name that exists, used where
    it cannot be written.
    """
    with pytest.raises(PublicationCheckError, match="no ledger-door entry"):
        validate_registry([a_check("probe", LedgerName.SUMMARY_QUALITY_EVALS_INDEX)])


def test_a_check_naming_a_door_ledger_passes() -> None:
    """The denominator: a refusal that refused everything would look the same."""
    validate_registry([a_check("probe", LedgerName.FEED_HEALTH)])
    validate_registry([a_check("probe")])


def test_a_mis_wired_gate_exits_two_rather_than_failing_the_day(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """All four faults reach an operator as one code, and it is not `1`.

    `1` says a day is broken and names it. `2` says the gate itself is wrong
    and nothing was checked at all, which is the worse of the two and the one a
    workflow log makes hardest to see. Raising out of the CLI instead would
    print a traceback and exit `1`, which reads as a broken day.
    """
    day = tmp_path / "digest" / "2026" / "08" / "21"
    day.mkdir(parents=True)
    (day / "digest.json").write_text("{}", encoding="utf-8")

    def refuse() -> tuple[Check, ...]:
        raise PublicationCheckError("two modules declare check 'pictures'")

    monkeypatch.setattr(runner, "discover", refuse)

    assert (
        main(
            [
                "check-publication",
                "--digest-root",
                str(tmp_path / "digest"),
                "--state-root",
                str(tmp_path / "state"),
            ]
        )
        == 2
    )
