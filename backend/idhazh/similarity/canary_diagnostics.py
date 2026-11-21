"""How closely did the judge agree with the known-answer key in both orders?"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Sequence

from idhazh.contracts.knobs.content_similarity_canaries import CanaryPair
from idhazh.contracts.story_similarity_diagnostics import CanaryExpectations, diagnostic_text
from idhazh.contracts.story_similarity_pair_verdict import SameStoryVerdict


def canary_columns(
    pairs: Sequence[CanaryPair], answers_text: str | None
) -> dict[str, str | float | int | None]:
    """Compare the configured key to the already-validated, merged runner answers."""
    expected = CanaryExpectations({pair.id: pair.expected for pair in pairs})
    answers = json.loads(answers_text) if answers_text is not None else {}
    observed: dict[str, SameStoryVerdict] = {}
    for key in expected.root.keys() & answers.keys():
        forward, swapped = answers[key][:2]
        if forward is not None and forward == swapped:
            observed[key] = SameStoryVerdict(forward)

    kappa = None
    size = len(expected.root)
    if len(observed) == size:
        expected_counts = Counter(expected.root.values())
        observed_counts = Counter(observed.values())
        # Scale both agreements by size squared so a zero denominator is exact.
        chance = sum(expected_counts[word] * observed_counts[word] for word in SameStoryVerdict)
        denominator = size * size - chance
        if denominator:
            matches = sum(observed[key] == answer for key, answer in expected.root.items())
            kappa = (size * matches - chance) / denominator

    return {
        "canary_expectations": diagnostic_text(expected),
        "canary_kappa_pairs": len(observed),
        "canary_kappa": kappa,
    }
