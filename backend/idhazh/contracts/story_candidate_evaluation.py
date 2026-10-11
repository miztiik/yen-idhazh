"""Which candidate-only saved units form a separate evaluation vector snapshot?"""

from typing import ClassVar, Literal

from idhazh.contracts.base import ChangelogEntry, SchemaVersion, Sha256
from idhazh.contracts.story_encoder_candidate import PinnedEncoderCandidate
from idhazh.contracts.story_vectors import VectorSnapshot


class CandidateEvaluationSnapshot(VectorSnapshot):
    __schema_stem__ = "story-candidate-evaluation-snapshot"
    __changelog__: ClassVar[tuple[ChangelogEntry]] = (
        ChangelogEntry(
            version="2026-10-11",
            change="Bind candidate-only saved units to a portable evaluation snapshot.",
            why="Pinned controls must be evaluated without borrowing unknown historical rows.",
        ),
    )
    version: SchemaVersion = __changelog__[0].version
    candidate: PinnedEncoderCandidate
    candidate_state_sha256: Sha256
    unit_sha256: list[Sha256]
    native_files_sha256: list[Sha256]
    ordered_ids_sha256: Sha256
    inference: Literal[False] = False
    selection: Literal["development-before-confirmation"] = "development-before-confirmation"
