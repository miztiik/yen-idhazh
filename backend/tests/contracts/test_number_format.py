"""Which number settings can the digest and console share?"""

import pytest
from pydantic import ValidationError

from idhazh.contracts.knobs.visuals import NumberFormatConfig


@pytest.mark.parametrize(
    "settings",
    [
        {"locale": ""},
        {"locale": "browser locale"},
        {"si_prefix_from": 0},
        {"si_prefix_from": float("inf")},
        {"significant_digits": 0},
        {"significant_digits": 22},
    ],
)
def test_invalid_number_settings_are_refused(settings: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        NumberFormatConfig.model_validate(settings)


def test_number_settings_accept_an_explicit_locale_and_precision() -> None:
    settings = {"locale": "de-DE", "si_prefix_from": 10_000, "significant_digits": 2}
    assert NumberFormatConfig.model_validate(settings).model_dump() == settings
