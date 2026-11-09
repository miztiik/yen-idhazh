"""How do complete independent native applications share one unchanged listener?"""

from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager

from fastapi import FastAPI
from starlette.routing import Route

from local_api_host.compose_api import ApplicationBinding, bind_application


class ComposedApplication(FastAPI):
    """Retain typed native bindings without combining their opaque service state."""

    application_bindings: tuple[ApplicationBinding, ...]


def compose_applications(applications: tuple[FastAPI, ...]) -> ComposedApplication:
    """Delegate unchanged requests, schemas and cleanup to their native applications."""
    if not applications:
        raise ValueError("At least one native application is required")
    bindings = tuple(bind_application(app) for app in applications)
    if len({id(binding.app) for binding in bindings}) != len(bindings):
        raise ValueError("Each native application must be composed exactly once")
    settings = bindings[0].host_settings
    routes: list[Route] = []
    path_bindings: dict[str, ApplicationBinding] = {}
    for binding in bindings:
        native_settings = binding.host_settings
        if (
            native_settings.listener != settings.listener
            or native_settings.shutdown_timeout_ms != settings.shutdown_timeout_ms
            or native_settings.propagate_trace_context != settings.propagate_trace_context
        ):
            raise ValueError("Native applications must share listener and lifecycle bounds")
        for route in binding.app.routes:
            if not isinstance(route, Route) or route.param_convertors:
                raise ValueError("Native application composition requires literal HTTP routes")
            paths = (
                (route.path, route.path + "/")
                if route.path != "/" and not route.path.endswith("/")
                else (route.path,)
            )
            for path in paths:
                previous = path_bindings.get(path)
                if previous is not None:
                    if previous.app is not binding.app:
                        raise ValueError("Native application route paths must not collide")
                    continue
                path_bindings[path] = binding
                routes.append(
                    Route(
                        path,
                        endpoint=binding.app,
                        name=route.name,
                        include_in_schema=False,
                    )
                )

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        async with AsyncExitStack() as stack:
            for binding in bindings:
                await stack.enter_async_context(
                    binding.app.router.lifespan_context(binding.app)
                )
            yield

    app = ComposedApplication(
        title=bindings[0].app.title,
        version=bindings[0].app.version,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        redirect_slashes=False,
        lifespan=lifespan,
    )
    app.application_bindings = bindings
    app.router.routes.extend(routes)
    app.router.routes.append(
        Route("/{path:path}", endpoint=bindings[0].app, include_in_schema=False)
    )
    return app
