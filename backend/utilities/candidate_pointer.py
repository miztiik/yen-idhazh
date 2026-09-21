"""Point a scratch config at the candidate, and say where its ledgers go.

Nothing is transplanted onto the entry: the candidate's own file carries its
own blocks. Two keys move and no third one may.

`run.trial_state_dirname` is the second, and it is optional. It already names
the directory a run that is not production writes under - see
`backend/idhazh/contracts/knobs/run.py` - and `cli` moves the state root onto it
for every stage of that run. A scratch config built without it behaves exactly
as it always did, which is how `Model validation` and the budget retake stay
unchanged.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

POINTER_KEY = "models_file"
TRIAL_STATE_BLOCK = "run"
TRIAL_STATE_KEY = "trial_state_dirname"
SCRATCH = Path("backend/var/candidate-config")

#: The only two key paths a scratch config may differ from the committed one at.
MOVABLE = ((POINTER_KEY,), (TRIAL_STATE_BLOCK, TRIAL_STATE_KEY))


def _differing_paths(
    before: object, after: object, trail: tuple[str, ...] = ()
) -> list[tuple[str, ...]]:
    if isinstance(before, dict) and isinstance(after, dict):
        moved: list[tuple[str, ...]] = []
        for key in sorted(set(before) | set(after)):
            moved.extend(_differing_paths(before.get(key), after.get(key), (*trail, str(key))))
        return moved
    return [] if before == after else [trail]


def refuse_any_other_move(before: dict[str, object], after: dict[str, object]) -> None:
    """Raise unless the scratch config moved the pointer and nothing else.

    This step used to write `sha256`, `repo`, `revision`, `file`, `id` and
    `quantisation` onto the copied entry and overwrite both `declared_for`
    digests, which said that numbers measured for one model held for another.
    """
    transplanted = [path for path in _differing_paths(before, after) if path not in MOVABLE]
    if transplanted:
        written = ", ".join(".".join(path) for path in transplanted)
        raise ValueError(
            f"a scratch config moves {' and '.join('.'.join(p) for p in MOVABLE)} and "
            f"nothing else; this one writes {written}"
        )


def point_at(models_file: str, *, scratch: Path = SCRATCH, trial_state: str = "") -> Path:
    path = scratch / "idhazh.json"
    committed = json.loads(path.read_text(encoding="utf-8"))
    settings = json.loads(json.dumps(committed))
    settings[POINTER_KEY] = models_file
    if trial_state:
        settings[TRIAL_STATE_BLOCK][TRIAL_STATE_KEY] = trial_state
    refuse_any_other_move(committed, settings)
    path.write_text(json.dumps(settings, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models-file", required=True)
    parser.add_argument("--scratch", type=Path, default=SCRATCH)
    parser.add_argument(
        "--trial-state",
        default="",
        help=(
            "Where this run's ledgers go under `state/`. Empty keeps the committed "
            "value, which is production."
        ),
    )
    args = parser.parse_args(argv)
    point_at(args.models_file, scratch=args.scratch, trial_state=args.trial_state)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
