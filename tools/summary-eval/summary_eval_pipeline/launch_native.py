"""Use the same parent-death bootstrap for native generation workers."""

import sys
from pathlib import Path

backend_root = str(Path(__file__).resolve().parents[3] / "backend")
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

from utilities.own_native_model import parent_bound_command as parent_bound_command  # noqa: E402
