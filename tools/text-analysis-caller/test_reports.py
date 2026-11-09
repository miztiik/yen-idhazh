"""Which pure report behaviors preserve native evidence and independent delivery?"""

import copy
import html
import json
import re
import sys
import unittest
from html.parser import HTMLParser

from render_entities import project_gliner_groups, project_spacy_groups
from render_report import (
    compose_report,
    render_gliner_results,
    render_report,
    render_source,
    render_spacy_results,
)
from write_reports import SUMMARY_MAX_BYTES, NativeFiles, render_saved_reports, select_summary


def span(text: str, start: int, sentence: int = 0) -> dict[str, object]:
    return {
        "text": text,
        "start_char": start,
        "end_char": start + len(text),
        "sentence_index": sentence,
    }


def feature(name: str, data: object) -> dict[str, object]:
    return {"feature": name, "status": "complete", "data": data, "error": None}


def spacy_result(features: list[dict[str, object]]) -> dict[str, object]:
    return {
        "status": "complete",
        "language": "en",
        "model": {
            "profile": "md",
            "package": "en_core_web_md",
            "model_version": "3.8.0",
            "spacy_version": "3.8.18",
        },
        "features": features,
    }


def spacy_settings() -> dict[str, object]:
    return {
        "languages": {
            "en": {
                "default_profile": "md",
                "default_features": ["named_entities", "important_terms"],
                "profiles": {"md": {"package": "en_core_web_md", "version": "3.8.0"}},
            }
        },
        "named_entities": {
            "ignore_case": True,
            "label_map": {
                "ORG": "organization",
                "LOC": "location",
                "PERSON": "person",
                "PRODUCT": "product",
            },
        },
        "important_terms": {"max_results": 25, "max_phrase_words": 3},
    }


class CodeText(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_code = False
        self.value = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "code":
            self.in_code = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "code":
            self.in_code = False

    def handle_data(self, data: str) -> None:
        if self.in_code:
            self.value += data


class ReportTests(unittest.TestCase):
    def test_source_preserves_characters_without_preformatted_no_wrap(self) -> None:
        source = "  alpha  beta\r\n<tag> *line* | `name`\r\t\u0ba4\u0bae\u0bbf\u0bb4\u0bcd\n\n"
        source += "longword" * 100
        markdown = render_source(source)
        parsed = CodeText()
        parsed.feed(markdown)
        self.assertEqual(parsed.value, source)
        self.assertNotIn("<pre", markdown)
        self.assertNotIn("style=", markdown)
        self.assertNotIn("<tag>", markdown)
        self.assertIn("&#13;&#10;", markdown)
        self.assertEqual(markdown.count("\n"), 2)

    def test_spacy_groups_sort_counts_positions_and_keep_native_case_evidence(self) -> None:
        source = "B A A C D A a B"
        entities = [
            {"text": "D", "type": "organization", "occurrences": [span("D", 8)]},
            {
                "text": "B",
                "type": "organization",
                "occurrences": [span("B", 14, 1), span("B", 0)],
            },
            {"text": "C", "type": "organization", "occurrences": [span("C", 6)]},
            {
                "text": "A",
                "type": "organization",
                "occurrences": [span("A", 10), span("a", 12), span("A", 4), span("A", 2)],
            },
        ]
        native_before = json.dumps(entities)
        groups = project_spacy_groups(entities, source)
        response = spacy_result([feature("named_entities", {"entities": entities})])
        report = html.unescape(
            render_spacy_results(source, response, spacy_settings=spacy_settings())
        )
        rows = [line for line in report.splitlines() if line.startswith("| BA")]
        self.assertEqual([row.split(" | ")[1] for row in rows], ["A", "B", "C", "D"])
        self.assertEqual(
            [row.split(" | ")[0] for row in rows], ["| BA4", "| BA2", "| BA3", "| BA1"]
        )
        self.assertIn("| BA4 | A | 4 |", report)
        self.assertIn("a ([12, 13), sentence 0)", report)
        self.assertLess(report.index("B ([0, 1)"), report.index("B ([14, 15)"))
        self.assertEqual([item["start_char"] for item in groups[3].occurrences], [2, 4, 10, 12])
        self.assertEqual(groups[3].text, "A")
        self.assertEqual(json.dumps(entities), native_before)

    def test_equal_counts_and_start_positions_keep_original_group_order(self) -> None:
        source = "Long Name"
        response = spacy_result(
            [
                feature(
                    "named_entities",
                    {
                        "entities": [
                            {
                                "text": "Long Name",
                                "type": "organization",
                                "occurrences": [span("Long Name", 0)],
                            },
                            {
                                "text": "Long",
                                "type": "organization",
                                "occurrences": [span("Long", 0)],
                            },
                        ]
                    },
                )
            ]
        )
        report = html.unescape(render_spacy_results(source, response))
        self.assertLess(report.index("| BA1 | Long Name"), report.index("| BA2 | Long |"))

    def test_gliner_exact_text_and_label_groups_keep_each_score_and_span(self) -> None:
        source = "Q q Q Q"
        mentions = [
            {"text": "Q", "label": "organization", "score": 0.0, "start_char": 6, "end_char": 7},
            {"text": "q", "label": "organization", "score": 0.3, "start_char": 2, "end_char": 3},
            {"text": "Q", "label": "person", "score": 0.4, "start_char": 0, "end_char": 1},
            {"text": "Q", "label": "organization", "score": 0.5, "start_char": 4, "end_char": 5},
            {"text": "Q", "label": "organization", "score": 0.6, "start_char": 0, "end_char": 1},
        ]
        labels = ["organization", "person", "location", "extra | <type>"]
        before = json.dumps(mentions)
        groups = project_gliner_groups(mentions, source, labels)
        self.assertEqual(len(groups), 3)
        self.assertEqual([item["score"] for item in groups[0].occurrences], [0.6, 0.5, 0.0])
        escaped_report = render_gliner_results(
            source,
            {"entities": mentions},
            gliner_request={"text": source, "labels": labels},
        )
        self.assertNotIn("<type>", escaped_report)
        report = html.unescape(escaped_report)
        self.assertIn("| KA1 | Q | 3 | [0, 1); score 0.6<br>[4, 5); score 0.5", report)
        self.assertIn("| KA2 | q | 1 | [2, 3); score 0.3", report)
        self.assertIn("| KB3 | Q | 1 | [0, 1); score 0.4", report)
        self.assertIn("<summary>extra | <type></summary>", report)
        self.assertIn("<summary>Locations</summary>", report)
        self.assertNotIn("sentence 0", report)
        self.assertEqual(json.dumps(mentions), before)

    def test_unicode_positions_are_codepoints_and_spacy_sentence_indexes_are_native(self) -> None:
        source = "\u0ba4\u0bae \U0001f600 X \U0001f600"
        occurrences = [span("\U0001f600", 7, 3), span("\U0001f600", 3, 2)]
        response = spacy_result(
            [
                feature(
                    "named_entities",
                    {
                        "entities": [
                            {
                                "text": "\U0001f600",
                                "type": "person",
                                "occurrences": occurrences,
                            }
                        ]
                    },
                )
            ]
        )
        report = html.unescape(render_spacy_results(source, response))
        self.assertIn("[3, 4), sentence 2", report)
        self.assertIn("[7, 8), sentence 3", report)
        gliner = render_gliner_results(
            source,
            {
                "entities": [
                    {
                        "text": "\U0001f600",
                        "label": "person",
                        "score": 0.5,
                        "start_char": 3,
                        "end_char": 4,
                    }
                ]
            },
            gliner_labels=["person"],
        )
        self.assertIn("[3, 4); score 0.5", gliner)
        self.assertNotIn("sentence 2", gliner)

    def test_empty_configured_types_are_not_a_hardcoded_filter(self) -> None:
        settings = spacy_settings()
        response = spacy_result([feature("named_entities", {"entities": []})])
        report = render_spacy_results("X", response, spacy_settings=settings)
        for title in ("Organizations", "Locations", "People", "product"):
            self.assertIn(f"<summary>{title}</summary>", report)
        self.assertEqual(report.count("No results were returned for this requested type."), 4)
        changed = copy.deepcopy(settings)
        changed["named_entities"] = {"ignore_case": False, "label_map": {"EVENT": "event"}}
        report = render_spacy_results("X", response, spacy_settings=changed)
        self.assertIn("<summary>event</summary>", report)
        self.assertNotIn("<summary>Organizations</summary>", report)

    def test_term_order_rank_count_and_native_score_are_not_entity_sorting(self) -> None:
        source = "low high high high"
        terms = [
            {"text": "low", "score": 0.1, "occurrences": [span("low", 0)]},
            {
                "text": "high",
                "score": 0.2,
                "occurrences": [span("high", 14), span("high", 9), span("high", 4)],
            },
        ]
        report = html.unescape(
            render_spacy_results(
                source, spacy_result([feature("important_terms", {"terms": terms})])
            )
        )
        self.assertIn("| C1 | 1 | low | 1 | 0.1 |", report)
        self.assertIn("| C2 | 2 | high | 3 | 0.2 |", report)
        self.assertLess(report.index("| C1"), report.index("| C2"))
        self.assertLess(report.index("high ([4, 8)"), report.index("high ([14, 18)"))
        self.assertIn("within the same article and settings", report)
        self.assertIn(
            "not percentages, confidence probabilities or editorial quality grades", report
        )

    def test_report_does_not_add_a_term_cap(self) -> None:
        words = [f"term{index}" for index in range(26)]
        source = " ".join(words)
        terms = [
            {"text": word, "score": index / 100, "occurrences": [span(word, source.index(word))]}
            for index, word in enumerate(words)
        ]
        report = html.unescape(
            render_spacy_results(
                source,
                spacy_result([feature("important_terms", {"terms": terms})]),
                spacy_settings=spacy_settings(),
            )
        )
        self.assertIn("| C26 | 26 | term25 | 1 | 0.25 |", report)
        self.assertIn("Important Terms: max_results", report)
        self.assertIn("25 (settings.json)", report)
        self.assertIn("3 (settings.json)", report)

    def test_configuration_keeps_omission_order_and_identity_provenance(self) -> None:
        source = "X"
        request: dict[str, object] = {"text": source, "language": "en", "model_profile": "md"}
        response = spacy_result(
            [feature("important_terms", {"terms": []}), feature("named_entities", {"entities": []})]
        )
        report = html.unescape(
            render_spacy_results(
                source, response, spacy_request=request, spacy_settings=spacy_settings()
            )
        )
        self.assertIn("Omitted (native defaults)", report)
        self.assertNotIn("features", request)
        request["features"] = ["important_terms", "named_entities"]
        before = json.dumps(request)
        report = html.unescape(
            render_spacy_results(
                source, response, spacy_request=request, spacy_settings=spacy_settings()
            )
        )
        self.assertIn('["important_terms", "named_entities"]', report)
        self.assertIn('"spacy_version": "3.8.18"', report)
        self.assertIn("response.json", report)
        self.assertEqual(json.dumps(request), before)
        gliner_report = html.unescape(
            render_gliner_results(
                source,
                {"entities": []},
                gliner_request={"text": source, "labels": ["person"]},
                gliner_settings={
                    "model": {"repo": "configured/model", "base_url": "https://example.test"}
                },
            )
        )
        self.assertIn("configured/model", gliner_report)
        self.assertIn("returns no model identity metadata", gliner_report)
        self.assertIn("| Classification | Not requested |", gliner_report)
        self.assertNotIn("threshold", gliner_report)

    def test_partial_failed_empty_and_not_requested_are_distinct(self) -> None:
        failed: dict[str, object] = {
            "feature": "named_entities",
            "status": "failed",
            "data": None,
            "error": {
                "feature": "named_entities",
                "code": "FEATURE_FAILED",
                "message": "Native feature failed.",
                "retryable": True,
            },
        }
        response = spacy_result([failed, feature("important_terms", {"terms": []})])
        response["status"] = "partial"
        reports = render_saved_reports(
            "X",
            NativeFiles(
                request={"text": "X", "language": "en"},
                response=response,
                settings=spacy_settings(),
            ),
            NativeFiles(
                request={"text": "X", "labels": ["organization", "location", "person"]},
                error="The native request failed.",
            ),
        )
        text = html.unescape(reports.combined)
        self.assertTrue(reports.failed)
        self.assertIn("Status: partial.", text)
        self.assertEqual(text.count("Failed: FEATURE_FAILED"), 4)
        self.assertIn("No results were returned.", text)
        self.assertIn("Failed: no successful NER result", text)
        not_requested = render_spacy_results(
            "X",
            spacy_result([feature("sentences", {"sentences": [span("X", 0)]})]),
            spacy_request={"text": "X", "language": "en", "features": ["sentences"]},
            spacy_settings=spacy_settings(),
        )
        self.assertIn("Not requested:", not_requested)
        self.assertNotIn("No results were returned", not_requested)

    def test_optional_raw_spacy_features_keep_their_native_fields(self) -> None:
        source = "A ran."
        actor, action = span("A", 0), span("ran", 2)
        features = [
            feature("entities", {"mentions": [{**actor, "label": "PERSON"}]}),
            feature("sentences", {"sentences": [span(source, 0)]}),
            feature(
                "relations",
                {
                    "relations": [
                        {
                            "sentence_index": 0,
                            "action": action,
                            "actors": [actor],
                            "objects": [],
                            "times": [],
                            "places": [],
                        }
                    ]
                },
            ),
            feature("noun_phrases", {"phrases": [actor]}),
            feature(
                "linguistic_tokens",
                {
                    "tokens": [
                        {
                            **actor,
                            "lemma": "A",
                            "part_of_speech": "PROPN",
                            "dependency": "nsubj",
                            "head_index": 1,
                            "morphology": None,
                        }
                    ]
                },
            ),
            feature(
                "document_metrics",
                {
                    "codepoint_count": len(source),
                    "utf8_byte_count": len(source.encode()),
                    "token_count": 3,
                    "sentence_count": 1,
                    "entity_count": 1,
                    "relation_count": 1,
                },
            ),
        ]
        report = html.unescape(render_spacy_results(source, spacy_result(features)))
        for title in (
            "Raw entities",
            "Sentences",
            "Relations",
            "Noun phrases",
            "Tokens",
            "Document metrics",
        ):
            self.assertIn(f"<summary>{title}</summary>", report)
        self.assertIn("| A | [0, 1) | 0 | A | PROPN | nsubj | 1 | null |", report)
        self.assertIn("ran ([2, 5), sentence 0)", report)

    def test_combined_and_standalone_sections_are_identical_and_ids_unique(self) -> None:
        source = "X"
        spacy = NativeFiles(
            request={"text": source, "language": "en"},
            response=spacy_result([feature("named_entities", {"entities": []})]),
            settings=spacy_settings(),
        )
        gliner = NativeFiles(
            request={"text": source, "labels": ["organization", "location", "person"]},
            response={"entities": []},
        )
        reports = render_saved_reports(source, spacy, gliner)
        spacy_section = render_spacy_results(
            source, spacy.response, spacy_request=spacy.request, spacy_settings=spacy.settings
        )
        gliner_section = render_gliner_results(
            source, gliner.response, gliner_request=gliner.request
        )
        self.assertFalse(reports.failed)
        self.assertEqual(reports.spacy, compose_report(source, spacy_section))
        self.assertEqual(reports.gliner, compose_report(source, gliner_section))
        self.assertEqual(
            reports.combined,
            render_report(
                source,
                spacy.response,
                gliner.response,
                spacy_request=spacy.request,
                spacy_settings=spacy.settings,
                gliner_request=gliner.request,
            ),
        )
        self.assertEqual(reports.combined.count("## Source text"), 1)
        ids = re.findall(r"^\| ([A-Z]+\d+) \|", reports.combined, re.MULTILINE)
        self.assertEqual(len(ids), len(set(ids)))

    def test_oversize_summary_links_both_complete_reports_and_counts_utf8_bytes(self) -> None:
        names = ("spacy-results-date-run-attempt", "gliner-results-date-run-attempt")
        boundary = "a" * SUMMARY_MAX_BYTES
        self.assertEqual(select_summary(boundary, names), (boundary, False))
        oversized = "a" * (SUMMARY_MAX_BYTES - 1) + "\u00e9"
        summary, failed = select_summary(oversized, names)
        self.assertTrue(failed)
        self.assertIn(names[0], html.unescape(summary))
        self.assertIn(names[1], html.unescape(summary))
        self.assertIn("neither report is truncated", summary)

    def test_invalid_evidence_fails_one_provider_without_hiding_its_sibling(self) -> None:
        invalid: dict[str, object] = {
            "entities": [
                {
                    "text": "wrong",
                    "label": "person",
                    "score": 0.9,
                    "start_char": 0,
                    "end_char": 1,
                }
            ]
        }
        with self.assertRaises(ValueError):
            render_gliner_results("X", invalid, gliner_labels=["person"])
        reports = render_saved_reports(
            "X",
            NativeFiles(response=spacy_result([feature("sentences", {"sentences": []})])),
            NativeFiles(
                request={"text": "X", "labels": ["person", "organization", "location"]},
                response=invalid,
            ),
        )
        self.assertTrue(reports.failed)
        self.assertIn("Status: complete.", reports.spacy)
        self.assertIn("invalid", reports.gliner)
        for title in ("People", "Organizations", "Locations"):
            self.assertIn(f"<summary>{title}</summary>", reports.gliner)
        with self.assertRaises(ValueError):
            render_gliner_results(
                "X", {"entities": []}, gliner_request={"text": "Y", "labels": ["person"]}
            )

    def test_pure_reports_do_not_import_provider_runtimes(self) -> None:
        self.assertFalse({"text_analysis", "gliner_api", "spacy", "gliner2"} & set(sys.modules))


if __name__ == "__main__":
    unittest.main()
