"""What has to be true of a published day before it is committed, and who asks.

Every rule lives in its own plugin under `checks/`, is found by `registry.py`
and is run by `runner.py`. Nothing here decides what a rule says - a check
declares a name, a scope and a callable, and the runner hands it the days or
the tree it asked for.

`docs/architecture/publishing/what-stops-a-broken-day-being-published.md` owns
the framework: what a check is, how discovery fails, and how a new one joins.
"""

from __future__ import annotations

from idhazh.publication_checks.registry import PublicationCheckError
from idhazh.publication_checks.runner import run_publication_checks

__all__ = ["PublicationCheckError", "run_publication_checks"]
