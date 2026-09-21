"""Which tenants is the council hosting, and where does a slug lead?

A slug in `council.tenants` is the whole of what the venue is told. What stands
behind it is found by asking each package that declares a tenant what its own
slug is, and every one of those imports happens inside a function - so no module
here carries a tenant in its import closure and nothing here lists who may
exist.

A slug nothing declares is refused by name. Removing a tenant is a config edit
and a directory delete; adding one is a directory and a config edit. Neither is
a change to this file.
"""

from __future__ import annotations

import importlib
import pkgutil
from collections.abc import Sequence
from pathlib import Path
from typing import Final, cast

from idhazh.council.tenancy import Tenant

#: The package the council looks in. Read on every call rather than bound as a
#: default, so the one name here is the one answer to where a tenant lives.
TENANT_PACKAGE: Final = "idhazh"

#: The module name a package declares a tenant in, and the name it binds the
#: implementation to. A package without that module is not a tenant and is never
#: imported, which is what keeps the search off every other subpackage.
TENANT_MODULE: Final = "tenant"

TENANT_ATTRIBUTE: Final = "TENANT"


def _declaring_modules(package: str) -> tuple[str, ...]:
    """Every module under `package` that could declare a tenant, in a fixed order.

    Read off the directory listing rather than by importing each subpackage: a
    package that declares no tenant is never executed, so one tenant's broken
    import cannot hide another tenant's slug.
    """
    root = importlib.import_module(package)
    locations = getattr(root, "__path__", None)
    if locations is None:
        return ()
    found: list[str] = []
    for entry in pkgutil.iter_modules(list(locations)):
        if not entry.ispkg:
            continue
        inside = [str(Path(location) / entry.name) for location in locations]
        if any(module.name == TENANT_MODULE for module in pkgutil.iter_modules(inside)):
            found.append(f"{package}.{entry.name}.{TENANT_MODULE}")
    return tuple(sorted(found))


def _declared(module_name: str) -> Tenant:
    """The tenant one module binds, imported here and nowhere earlier."""
    module = importlib.import_module(module_name)
    declared = getattr(module, TENANT_ATTRIBUTE, None)
    if declared is None:
        raise SystemExit(
            f"{module_name} is where the council looks for a tenant and it binds no "
            f"{TENANT_ATTRIBUTE}, so the slug it was going to answer to reaches nothing"
        )
    return cast(Tenant, declared)


def tenant(slug: str, *, package: str | None = None) -> Tenant:
    """The tenant that answers to `slug`, or a refusal naming the slug.

    Refused rather than skipped. A night that quietly dropped an unrecognised
    slug would run every step, report nothing wrong and judge less than the
    config asked for, which is the failure a typo in a slug list produces.
    """
    root = package or TENANT_PACKAGE
    declared: list[str] = []
    for module_name in _declaring_modules(root):
        found = _declared(module_name)
        if found.judge_id == slug:
            return found
        declared.append(found.judge_id)
    known = ", ".join(declared) if declared else "none"
    raise SystemExit(
        f"council.tenants names '{slug}' and no package under {root}/ declares it. "
        f"The tenants that do declare themselves: {known}. Either the slug is a typo "
        f"or the tenant's own {TENANT_MODULE} module is not in this checkout."
    )


def tenants(slugs: Sequence[str], *, package: str | None = None) -> tuple[Tenant, ...]:
    """Every tenant the council hosts, in the order the config names them.

    An empty list is a legal night. The venue runs every step it always runs and
    judges nothing, which is what a room with no case heard in it looks like.
    """
    return tuple(tenant(slug, package=package) for slug in slugs)
