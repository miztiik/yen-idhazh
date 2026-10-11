"""Which tenants is the council hosting, and where does a slug lead?

A slug in `judge_names` in `config/llm_council.json` names its package with
hyphens replaced by underscores. Only that package's tenant module is imported,
inside a function, so no module here carries a tenant in its import closure.

Resolving is also when a tenant gets to refuse the night. The planning job
resolves every registered slug before it can build its matrix, so a tenant that
cannot finish the work it would draw stops the run before any job restores a
model's weights. The venue asks the question and reads no number behind it.

A slug nothing declares is refused by name. Removing a tenant is a config edit
and a directory delete; adding one is a directory and a config edit. Neither is
a change to this file.
"""

from __future__ import annotations

import importlib
from collections.abc import Sequence
from types import ModuleType
from typing import Final, cast

from idhazh import config
from idhazh.contracts.app_config import AppConfig
from idhazh.contracts.knobs.council import CouncilConfig, derive_judge_package_name
from idhazh.council.tenancy import Tenant

#: The package the council looks in. Read on every call rather than bound as a
#: default, so the one name here is the one answer to where a tenant lives.
TENANT_PACKAGE: Final = "idhazh"

#: The declaration module and implementation attribute are the tenancy protocol's
#: fixed import address, not a roster of judge packages.
TENANT_MODULE: Final = "tenant"

TENANT_ATTRIBUTE: Final = "TENANT"

#: What a tenant module calls the check it makes of its own night, read off the
#: module the way the implementation is. Optional on purpose: a tenant whose work
#: has no cost to weigh against the venue's clock declares nothing here and is
#: asked nothing. It is not an eighth member of the protocol because the protocol
#: is what a tenant presents while it runs, and this is asked before it does.
TENANT_FIT_CHECK: Final = "refuse_a_night_this_tenant_cannot_finish"


def _declared(module_name: str) -> tuple[ModuleType, Tenant]:
    """The module one package declares a tenant in, and what it binds.

    Imported here and nowhere earlier. The module comes back beside the tenant
    because what a tenant says about the night ahead is read off the module and
    not off the implementation.
    """
    module = importlib.import_module(module_name)
    declared = getattr(module, TENANT_ATTRIBUTE, None)
    if declared is None:
        raise SystemExit(
            f"{module_name} is where the council looks for a tenant and it binds no "
            f"{TENANT_ATTRIBUTE}, so the slug it was going to answer to reaches nothing"
        )
    return module, cast(Tenant, declared)


def _refuse_a_night_this_tenant_cannot_finish(
    module: ModuleType, app: AppConfig | None, council: CouncilConfig | None
) -> None:
    """Give the tenant that answered to the slug its say on the night ahead.

    Asked of that tenant and of no other. A venue that ran every declared
    tenant's check would let a tenant nobody registered refuse a night it is not
    in, which is the opposite of a roster the config owns.

    Config is read here when the caller did not bring it, so the venue's own
    verbs keep the signature they had.
    """
    check = getattr(module, TENANT_FIT_CHECK, None)
    if check is None:
        return
    check(
        app if app is not None else config.load().app,
        council=council if council is not None else config.load_council(),
    )


def tenant(
    slug: str,
    *,
    package: str | None = None,
    app: AppConfig | None = None,
    council: CouncilConfig | None = None,
) -> Tenant:
    """The tenant that answers to `slug`, or a refusal naming the slug.

    Refused rather than skipped. A night that quietly dropped an unrecognised
    slug would run every step, report nothing wrong and judge less than the
    config asked for, which is the failure a typo in a slug list produces.
    """
    root = package or TENANT_PACKAGE
    module_name = f"{root}.{derive_judge_package_name(slug)}.{TENANT_MODULE}"
    try:
        module, found = _declared(module_name)
    except ModuleNotFoundError as exc:
        if exc.name is None or not (
            exc.name == module_name or module_name.startswith(f"{exc.name}.")
        ):
            raise
        raise SystemExit(
            f"judge_names in config/llm_council.json names '{slug}', but its "
            f"declaration module {module_name} is not in this checkout."
        ) from exc
    if found.judge_id != slug:
        raise SystemExit(
            f"judge_names in config/llm_council.json names '{slug}', but "
            f"{module_name} declares judge_id '{found.judge_id}'."
        )
    _refuse_a_night_this_tenant_cannot_finish(module, app, council)
    return found


def tenants(
    slugs: Sequence[str],
    *,
    package: str | None = None,
    app: AppConfig | None = None,
    council: CouncilConfig | None = None,
) -> tuple[Tenant, ...]:
    """Every tenant the council hosts, in the order the config names them.

    An empty list is a legal night. The venue runs every step it always runs and
    judges nothing, which is what a room with no case heard in it looks like.
    """
    return tuple(tenant(slug, package=package, app=app, council=council) for slug in slugs)
