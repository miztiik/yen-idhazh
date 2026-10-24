"""Which annotations does the validate run page show for this verdict?"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path
from typing import Final

from idhazh.contracts.qualification import QualificationReport
from idhazh.evals import qualification_summary
from idhazh.stages.common import QUALIFICATION_ROOT
from idhazh.stages.qualify_decide import REPORT_JSON

#: The verdict the decide stage writes beside the markdown page it renders.
REPORT: Final = QUALIFICATION_ROOT / REPORT_JSON


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args(argv)
    if not args.report.is_file():
        print(qualification_summary.render_missing_verdict())
        return 0
    report = QualificationReport.read(args.report)
    for line in qualification_summary.render_annotations(report):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
