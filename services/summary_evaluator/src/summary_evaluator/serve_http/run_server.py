"""How does a server exit retain its actual ASGI lifespan outcome?"""

import socket

import uvicorn
from uvicorn.lifespan.on import LifespanOn


def has_clean_lifespan(server: uvicorn.Server) -> bool:
    lifespan = getattr(server, "lifespan", None)
    return (
        server.started
        and isinstance(lifespan, LifespanOn)
        and not lifespan.error_occurred
        and not lifespan.startup_failed
        and not lifespan.shutdown_failed
    )


def run_server(server: uvicorn.Server, sockets: list[socket.socket]) -> None:
    server.run(sockets=sockets)
    if not has_clean_lifespan(server):
        raise SystemExit(1)
