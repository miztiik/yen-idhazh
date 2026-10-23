"""Which headline matches and optional feed votes were actually observed?"""

from typing import Annotated, Self

from pydantic import Field, model_validator

from idhazh.contracts.base import Model, Slug

NonEmpty = Annotated[str, Field(min_length=1)]
Positive = Annotated[float, Field(gt=0, allow_inf_nan=False)]


class WeightedLensObservation(Model):
    """The strongest configured headline match, retained without a score bonus."""

    id: Slug
    weight: Positive


class SalienceFeedObservation(Model):
    """Whether one configured voting feed named this existing candidate."""

    feed_id: Slug
    available: bool = Field(description="Complete voting input, independent of a known positive vote.")
    voted: bool | None
    unavailable_reason: NonEmpty | None

    @model_validator(mode="after")
    def validate_availability(self) -> Self:
        if self.available and self.voted is None:
            raise ValueError("available salience requires a measured vote")
        if not self.available and self.voted is False:
            raise ValueError("incomplete salience cannot prove an absent vote")
        if self.available != (self.unavailable_reason is None):
            raise ValueError("unavailable salience requires a reason")
        return self


class PlanningObservations(Model):
    """Headline evidence is not an article classifier verdict or a score bonus."""

    feed_headline: NonEmpty | None
    best_weighted_lens: WeightedLensObservation | None
    watchlist_match: bool | None
    salience: list[SalienceFeedObservation]
    salience_available: bool = Field(description="All configured voting inputs are complete.")
    on_front_page: bool | None
    salience_unavailable_reason: NonEmpty | None

    @model_validator(mode="after")
    def validate_availability(self) -> Self:
        if self.salience_available != (self.salience_unavailable_reason is None):
            raise ValueError("unavailable salience requires a reason")
        if self.salience_available:
            if not self.salience or not all(feed.available for feed in self.salience):
                raise ValueError("salience requires every configured feed to be available")
        expected: bool | None = None
        if any(feed.voted is True for feed in self.salience):
            expected = True
        elif self.salience_available:
            expected = False
        if self.on_front_page is not expected:
            raise ValueError("front-page observation must preserve positive votes and unknown absence")
        if len({feed.feed_id for feed in self.salience}) != len(self.salience):
            raise ValueError("salience feed ids must be distinct")
        if self.feed_headline is None and (
            self.best_weighted_lens is not None or self.watchlist_match is not None
        ):
            raise ValueError("headline matches require the original feed headline")
        return self
