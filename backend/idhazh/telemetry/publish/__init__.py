"""Every projection of the instrument a run publishes, one module per payload.

`dispatch.py` is the only thing that knows the order they run in; each other
module writes exactly one surface and knows nothing about its siblings'
schedule. `series.py` is the shared write rule the month-sharded payloads obey -
where a file goes, when its bytes are rewritten, and when it is pruned.

The product's own producers are deliberately not here. `frontend/public/digest/`
and `frontend/public/assist/` are what a reader came for, and this package is
what the operator reads about the run that built them.

No name is re-exported from this file. A publisher is imported from the module
that owns it, so there is one name for one thing (Guardrail #6).
"""

from __future__ import annotations
