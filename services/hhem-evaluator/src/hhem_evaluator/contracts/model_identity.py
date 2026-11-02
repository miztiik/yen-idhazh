"""Which observed assets and runtime versions identify the loaded model?"""

from typing import Annotated

from pydantic import StringConstraints

from .base import CommitId, ModelReference, NativeContract, Sha256

RuntimeVersion = Annotated[
    str, StringConstraints(strict=True, pattern=r"^[A-Za-z0-9][A-Za-z0-9.+_-]{0,127}$")
]


class RuntimeVersions(NativeContract):
    """Name the three runtimes used by actual scoring."""

    python: RuntimeVersion
    pytorch: RuntimeVersion
    transformers: RuntimeVersion


class ModelIdentity(NativeContract):
    """Require actual loaded fingerprints before describing model readiness."""

    reference: ModelReference
    configured_revision: CommitId
    loaded_revision: CommitId
    foundation_reference: ModelReference
    foundation_revision: CommitId
    loaded_weights_sha256: Sha256
    loaded_config_sha256: Sha256
    service_config_sha256: Sha256
    runtime_versions: RuntimeVersions
