"""How is one independent execution UUID created?"""

from uuid import uuid4


def create_execution_id() -> str:
    """Create an independent lowercase UUIDv4 before reading an HTTP attempt."""
    return str(uuid4())
