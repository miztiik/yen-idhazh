"""The closed names of checks that can refuse a visual plan."""

from enum import StrEnum


class ValidatorCheck(StrEnum):
    """The eleven checks, in the order the validator runs them.

    Each member names the property that must hold, not the failure.
    """

    #: Every declared element id is present in the article's table.
    ELEMENT_EXISTS = "element_exists"
    #: Each element's kind fits the channel it fills.
    SEMANTICALLY_COMPATIBLE = "semantically_compatible"
    #: Units within one measured channel are convertible or identical.
    UNITS_CONVERTIBLE = "units_convertible"
    #: The filled roles are the ones this type declares.
    ROLES_VALID_FOR_TYPE = "roles_valid_for_type"
    #: Stacked parts exactly make a separate source-declared whole.
    STACKED_BAR_EXHAUSTIVE = "stacked_bar_exhaustive"
    #: Pie parts exactly make a separate source-declared whole.
    PIE_EXHAUSTIVE = "pie_exhaustive"
    #: The marks fit the configured chart-point bounds.
    ENOUGH_DATA = "enough_data"
    #: No element fills one channel twice.
    NO_DUPLICATE_IN_ROLE = "no_duplicate_in_role"
    #: Every drawn figure reads from the characters the element names.
    NO_INVENTED_VALUES = "no_invented_values"
    #: Every numeral in the prose is one a cited element states.
    NUMERALS_MATCHED = "numerals_matched"
    #: The plan met the vocabulary this build holds.
    PLAN_VERSION_CURRENT = "plan_version_current"
