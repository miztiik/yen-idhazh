"""Which annotations does the validate run page show for this verdict?"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path
from typing import Final

from idhazh.contracts.qualification import QualificationReport
from idhazh.evals import qualification_summary
from idhazh.stages.common import QUALIFICATION_ROOT

#: The verdict the decide stage writes beside the markdown page it renders.
REPORT: Final = QUALIFICATION_ROOT / "report.json"

#: An error, because a run that never reached a verdict is red on its page, not green.
NO_VERDICT: Final = (
    "::error title=Qualification verdict::No verdict was written, so no gate was read. "
    "The Run the gates step log says why."
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args(argv)
    if not args.report.is_file():
        print(NO_VERDICT)
        return 0
    report = QualificationReport.read(args.report)
    for line in qualification_summary.render_annotations(report):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
