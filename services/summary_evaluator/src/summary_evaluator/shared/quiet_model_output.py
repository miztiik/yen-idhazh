"""How is untrusted native and Python model output suppressed?"""

import contextlib
import os
from collections.abc import Iterator


@contextlib.contextmanager
def quiet_model_output() -> Iterator[None]:
    """Discard untrusted native and Python diagnostics rather than forwarding them."""
    with open(os.devnull, "w", encoding="utf-8") as sink:
        saved = [(descriptor, os.dup(descriptor)) for descriptor in (1, 2)]
        try:
            for descriptor, _ in saved:
                os.dup2(sink.fileno(), descriptor)
            with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
                yield
        finally:
            for descriptor, original in saved:
                os.dup2(original, descriptor)
                os.close(original)
