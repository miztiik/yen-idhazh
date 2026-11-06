"""Which pinned revisions and runtime versions identify the loaded model?"""

from typing import Annotated

from pydantic import ConfigDict, StringConstraints

from hhem_evaluator.contracts.base import SCHEMA_VERSION
from hhem_evaluator.shared.contracts.base import CommitId, ModelReference, NativeContract

RuntimeVersion = Annotated[
    str, StringConstraints(strict=True, pattern=r"^[A-Za-z0-9][A-Za-z0-9.+_-]{0,127}$")
]


class RuntimeVersions(NativeContract):
    """Name the three runtimes used by actual scoring."""

    python: RuntimeVersion
    pytorch: RuntimeVersion
    transformers: RuntimeVersion


class ModelIdentity(NativeContract):
    """Identify the selected upstream assets without re-hashing loaded tensors."""

    model_config = ConfigDict(
        json_schema_extra={
            "version": SCHEMA_VERSION,
            "changelog": [
                {
                    "version": SCHEMA_VERSION,
                    "change": "Identify pinned revisions without runtime fingerprints.",
                },
                {"version": SCHEMA_VERSION, "change": "Declare standalone model identity."},
            ],
        }
    )

    reference: ModelReference
    configured_revision: CommitId
    loaded_revision: CommitId
    foundation_reference: ModelReference
    foundation_revision: CommitId
    runtime_versions: RuntimeVersions
