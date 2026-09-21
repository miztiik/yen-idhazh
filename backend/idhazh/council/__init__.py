"""The room a model verdict is taken in, and nothing about what any verdict says.

Nothing under this package imports a judge or names one. A judge is reached
through the protocol in `tenancy.py` and hands its rows to `metrics_sink.py`, so
the council declares, builds, tests and runs in a repository with no judge in
it. The council records which tenant ran; it never declares which tenants may
exist.

`docs/architecture/publishing/llm-council.md` owns the three layers this split
holds apart.
"""

from __future__ import annotations
