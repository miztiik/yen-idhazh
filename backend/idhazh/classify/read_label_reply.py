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


class _AddressedLabel(_LegacyModel):
    element_id: _Address
    measure: str = Field(max_length=60)
    entity: str = Field(max_length=60)


class _AddressedMentions(_LegacyModel):
    mentions: list[_LegacyCitation] = Field(max_length=4)
    kind: Literal["entity", "place"]
    name: _Phrase


class _AddressedReply(_LegacyModel):
    labels: list[_AddressedLabel] = Field(max_length=16)
    proposed: list[_LegacyCitation] = Field(max_length=4)
    named_mentions: list[_AddressedMentions] = Field(max_length=12)


def _has_sentence_address(data: dict[str, Any]) -> bool:
    proposed = data.get("proposed")
    if isinstance(proposed, list) and any(
        isinstance(citation, dict) and "sentence_id" in citation for citation in proposed
    ):
        return True
    groups = data.get("named_mentions")
    if not isinstance(groups, list):
        return False
    return any(
        isinstance(citation, dict) and "sentence_id" in citation
        for group in groups
        if isinstance(group, dict) and isinstance(group.get("mentions"), list)
        for citation in group["mentions"]
    )


def read_label_reply(data: Any) -> dict[str, Any] | None:
    """Normalize strict historical replies, or defer a current reply to its own model."""
    if not isinstance(data, dict):
        return None
    if {"entity_mentions", "place_mentions"} & data.keys():
        retired = _LegacyObservations.model_fields.keys() & data.keys()
        if retired:
            _LegacyObservations.model_validate({name: data[name] for name in retired})
        legacy = _LegacyLabelReply.model_validate(
            {name: value for name, value in data.items() if name not in retired}
        )
        data = {
            "labels": [
                {"element_id": label.element_id, "measure": label.measure, "entity": label.entity}
                for label in legacy.labels
            ],
            "proposed": [citation.model_dump() for citation in legacy.proposed],
            "named_mentions": [
                {
                    "mentions": [one.model_dump() for one in group.mentions],
                    "kind": kind,
                    "name": group.name,
                }
                for kind, groups in (
                    ("entity", legacy.entity_mentions), ("place", legacy.place_mentions)
                )
                for group in groups
            ],
        }
    elif not _has_sentence_address(data):
        return None
    reply = _AddressedReply.model_validate(data)
    return {
        "labels": [label.model_dump() for label in reply.labels],
        "proposed": [
            {"surface": citation.surface, "legacy_sentence_id": citation.sentence_id}
            for citation in reply.proposed
        ],
        "named_mentions": [
            {
                "mentions": [
                    {"surface": one.surface, "legacy_sentence_id": one.sentence_id}
                    for one in group.mentions
                ],
                "kind": group.kind,
                "name": group.name,
            }
            for group in reply.named_mentions
        ],
    }
