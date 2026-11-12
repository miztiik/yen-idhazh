"""How are historical label replies validated before their retired fields are discarded?"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

# These bounds describe the saved format, not the current decoder.
_Address = Annotated[str, StringConstraints(min_length=1, max_length=48)]
_Phrase = Annotated[str, StringConstraints(min_length=1, max_length=60)]
_Salience = Literal["primary", "supporting", "background"]
_Attribution = Literal["named", "self_reported", "anonymous", "unattributed"]


class _LegacyModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _LegacyCitation(_LegacyModel):
    sentence_id: _Address
    surface: _Phrase


class _LegacyLabel(_LegacyModel):
    element_id: _Address
    measure: str = Field(max_length=60)
    dimension: str = Field(max_length=60)
    entity: str = Field(max_length=60)
    time_element_id: str = Field(max_length=48)
    attribution: _Attribution
    hedge: bool
    salience: _Salience


class _LegacyMentions(_LegacyModel):
    mentions: list[_LegacyCitation] = Field(max_length=4)
    name: _Phrase
    salience: _Salience


class _LegacyLabelReply(_LegacyModel):
    labels: list[_LegacyLabel] = Field(max_length=16)
    proposed: list[_LegacyCitation] = Field(max_length=4)
    entity_mentions: list[_LegacyMentions] = Field(max_length=6)
    place_mentions: list[_LegacyMentions] = Field(max_length=6)


class _LegacyRange(_LegacyModel):
    sentence_start_id: _Address
    sentence_end_id: _Address
    speaker: str = Field(max_length=60)
    attribution: _Attribution
    hedge: bool


class _LegacyObservations(_LegacyModel):
    quotes: list[_LegacyRange] = Field(max_length=8)
    claims: list[_LegacyRange] = Field(max_length=8)
    keyphrases: list[_Phrase] = Field(max_length=8)
    lede_sentence_ids: list[_Address] = Field(max_length=2)


def read_label_reply(data: Any) -> Any:
    """Adapt only a complete, closed historical reply; current replies pass unchanged."""
    if not isinstance(data, dict) or not {"entity_mentions", "place_mentions"} & data.keys():
        return data
    retired = _LegacyObservations.model_fields.keys() & data.keys()
    if retired:
        _LegacyObservations.model_validate({name: data[name] for name in retired})
    reply = _LegacyLabelReply.model_validate(
        {name: value for name, value in data.items() if name not in retired}
    )
    return {
        "labels": [
            {"element_id": label.element_id, "measure": label.measure, "entity": label.entity}
            for label in reply.labels
        ],
        "proposed": [citation.model_dump() for citation in reply.proposed],
        "named_mentions": [
            {
                "mentions": [one.model_dump() for one in group.mentions],
                "kind": kind,
                "name": group.name,
            }
            for kind, groups in (
                ("entity", reply.entity_mentions), ("place", reply.place_mentions)
            )
            for group in groups
        ],
    }
