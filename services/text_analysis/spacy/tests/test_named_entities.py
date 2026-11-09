"""Which grouping rules preserve every exact native entity occurrence?"""

import unittest

from text_analysis.declare_api_contracts import EntitiesData, EntityMention
from text_analysis.declare_service_settings import NamedEntitiesSettings
from text_analysis.group_named_entities import group_named_entities


class NamedEntitiesTests(unittest.TestCase):
    def test_repeated_names_preserve_first_spelling_and_unicode_source_order(self) -> None:
        source = "\U0001f4f0 ALPHA met Alpha. Alpha arrived."
        positions = (source.index("ALPHA"), source.index("Alpha"), source.rindex("Alpha"))
        mentions = tuple(
            EntityMention(
                text=source[start:start + len("Alpha")],
                start_char=start,
                end_char=start + len("Alpha"),
                sentence_index=1 if index == 2 else 0,
                label="PERSON",
            )
            for index, start in enumerate(positions)
        )
        result = group_named_entities(
            EntitiesData(mentions=tuple(reversed(mentions))),
            NamedEntitiesSettings(),
        )
        self.assertEqual(len(result.entities), 1)
        entity = result.entities[0]
        self.assertEqual((entity.text, entity.type), ("ALPHA", "person"))
        self.assertEqual(tuple(item.start_char for item in entity.occurrences), positions)
        self.assertEqual(tuple(item.sentence_index for item in entity.occurrences), (0, 0, 1))
        for occurrence in entity.occurrences:
            self.assertEqual(
                source[occurrence.start_char:occurrence.end_char],
                occurrence.text,
            )

    def test_mapped_type_is_part_of_the_group_and_unmapped_mentions_remain_raw(self) -> None:
        source = "Bay Bay Bay Bay"
        labels = ("GPE", "LOC", "ORG", "DATE")
        raw = EntitiesData(
            mentions=tuple(
                EntityMention(
                    text="Bay",
                    start_char=index * len("Bay "),
                    end_char=index * len("Bay ") + len("Bay"),
                    sentence_index=0,
                    label=label,
                )
                for index, label in enumerate(labels)
            )
        )
        result = group_named_entities(raw, NamedEntitiesSettings())
        self.assertEqual(
            [(item.text, item.type, len(item.occurrences)) for item in result.entities],
            [("Bay", "location", 2), ("Bay", "organization", 1)],
        )
        self.assertEqual(tuple(item.label for item in raw.mentions), labels)
        self.assertEqual(source[raw.mentions[-1].start_char:raw.mentions[-1].end_char], "Bay")

    def test_configuration_changes_case_grouping_and_label_mapping(self) -> None:
        raw = EntitiesData(
            mentions=(
                EntityMention(
                    text="ALPHA", start_char=0, end_char=5, sentence_index=0, label="PERSON"
                ),
                EntityMention(
                    text="Alpha", start_char=6, end_char=11, sentence_index=0, label="PERSON"
                ),
            )
        )
        settings = NamedEntitiesSettings(ignore_case=False, label_map={"PERSON": "speaker"})
        result = group_named_entities(raw, settings)
        self.assertEqual(
            [(item.text, item.type) for item in result.entities],
            [("ALPHA", "speaker"), ("Alpha", "speaker")],
        )
        self.assertEqual(
            group_named_entities(raw, NamedEntitiesSettings(label_map={})).entities,
            (),
        )
        self.assertEqual(
            group_named_entities(EntitiesData(mentions=()), NamedEntitiesSettings()).entities,
            (),
        )


if __name__ == "__main__":
    unittest.main()
