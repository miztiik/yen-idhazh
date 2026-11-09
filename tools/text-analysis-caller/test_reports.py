"""Which pure report behaviors preserve native evidence and independent delivery?"""

import asyncio
import copy
import html
import json
import re
import sys
import unittest
from html.parser import HTMLParser
from urllib.parse import urljoin

import test_capture_stream
from collect_operations import Outcome, collect_gliner_operations
from prepare_default_tasks import default_classification_tasks
from render_classifications import (
    read_classification_selections,
    read_classification_tasks,
    render_classifications,
)
from render_configuration import render_settings_link
from render_entities import project_gliner_groups, project_spacy_groups
from render_report import (
    compose_report,
    render_gliner_results,
    render_report,
    render_source,
    render_spacy_results,
)
from render_tables import read_object
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


def classification_taxonomy() -> dict[str, object]:
    return {
        "verticals": [
            {"id": "second", "display_name": "Saved <desk>", "definition": "Second desk."},
            {"id": "first", "display_name": "First", "definition": "First desk."},
            {"id": "draft", "status": "draft", "definition": ""},
        ],
        "lenses": [
            {"id": "lens-a", "display_name": "Lens A", "definition": "First lens."},
            {"id": "lens-b", "display_name": "Lens B", "definition": "Second lens."},
            {"id": "retired", "status": "retired", "definition": ""},
        ],
        "events": [{"id": "event", "display_name": "Event", "definition": "An event."}],
        "source_kinds": [
            {"id": "reporting", "display_name": "Reporting"},
            {"id": "research", "display_name": "Research"},
            {"id": "old", "display_name": "Old kind", "status": "retired"},
        ],
    }


def historical_classification_request(source: str) -> dict[str, object]:
    return {
        "text": source,
        "tasks": {
            "desk": {
                "labels": {"second": "Second <desk>.", "first": "First desk."},
                "multi_label": False,
            },
            "lenses": {
                "labels": {"lens-a": "First lens.", "lens-b": "Second lens."},
                "multi_label": True,
            },
            "events": {"labels": {"event": "An event."}, "multi_label": True},
        },
    }


def classification_result() -> dict[str, object]:
    return {
        "classifications": {
            "desk": [{"id": "second", "score": 0.8}],
            "lenses": [{"id": "lens-b", "score": 0.25}, {"id": "lens-a", "score": 0.95}],
            "events": [],
        }
    }


class SourceText(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_prose = False
        self.value = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "p":
            self.in_prose = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "p":
            self.in_prose = False

    def handle_data(self, data: str) -> None:
        if self.in_prose:
            self.value += data


class ReportTests(unittest.TestCase):
    def test_source_preserves_literal_prose_in_a_collapsed_native_disclosure(self) -> None:
        source = "  alpha  beta\r\n<tag> *line* | `name`\r\t\u0ba4\u0bae\u0bbf\u0bb4\u0bcd\n\n"
        source += "longword" * 100
        markdown = render_source(source)
        parsed = SourceText()
        parsed.feed(markdown)
        self.assertEqual(parsed.value, source)
        self.assertTrue(markdown.startswith("<details><summary><h2>Source text</h2></summary>"))
        self.assertNotIn("<details open", markdown)
        self.assertNotIn("<code", markdown)
        self.assertNotIn("<pre", markdown)
        self.assertNotIn("style=", markdown)
        self.assertNotIn("<tag>", markdown)
        self.assertIn("&#13;&#10;<br>", markdown)
        self.assertEqual(markdown.count("<br>"), 4)
        self.assertEqual(markdown.count("\n"), 4)

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
        self.assertIn("| Important Terms: max_results | 25 |", report)
        self.assertIn("| Important Terms: max_phrase_words | 3 |", report)

    def test_configuration_shows_only_effective_values_without_changing_requests(self) -> None:
        source = "X"
        repository = "fixture/repository"
        request: dict[str, object] = {"text": source, "language": "en", "model_profile": "md"}
        response = spacy_result(
            [feature("important_terms", {"terms": []}), feature("named_entities", {"entities": []})]
        )
        report = html.unescape(
            render_spacy_results(
                source,
                response,
                spacy_request=request,
                spacy_settings=spacy_settings(),
                repository=repository,
            )
        )
        self.assertIn("| Id | Setting | Effective value |", report)
        self.assertNotIn("Requested value", report)
        self.assertEqual(report.count("[settings.json]("), 1)
        self.assertNotIn("(settings.json)", report)
        self.assertLess(
            report.index("Status: complete."), report.index("<summary>spaCy configuration")
        )
        self.assertIn(
            '| A4 | Features (ordered) | ["important_terms", "named_entities"] (response.json) |',
            report,
        )
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
                repository=repository,
            )
        )
        self.assertIn("configured/model", gliner_report)
        self.assertIn('| J2 | Entity labels (ordered) | ["person"] (request.json) |', gliner_report)
        self.assertIn(
            '| J3 | Configured model identity | {"repo": "configured/model", '
            '"base_url": "https://example.test"} |',
            gliner_report,
        )
        self.assertIn("not NER response metadata", gliner_report)
        self.assertEqual(gliner_report.count("[settings.json]("), 1)
        self.assertNotIn("(settings.json)", gliner_report)
        self.assertLess(
            gliner_report.index("Status: complete."),
            gliner_report.index("<summary>GLiNER configuration"),
        )
        self.assertIn("| Id | Setting | Effective value |", gliner_report)
        self.assertNotIn("Requested value", gliner_report)
        self.assertIn("| J6 | Classification | Not requested |", gliner_report)
        self.assertNotIn("threshold", gliner_report)
        unavailable = html.unescape(
            render_gliner_results(
                source, None, gliner_request={"text": source, "labels": ["person"]}
            )
        )
        self.assertIn("run-ner-gliner (request.json; no successful response)", unavailable)
        self.assertIn("Not recorded; no saved model settings", unavailable)
        for gliner in (False, True):
            reference = render_settings_link(repository, gliner=gliner)
            path = "config/text-analysis/" + ("gliner/" if gliner else "") + "settings.json"
            href = f"/{repository}/blob/main/{path}"
            self.assertIn(f"[settings.json]({href})", reference)
            for page in ("actions/runs/42", "actions/runs/42/job/7"):
                base = f"https://example.test/{repository}/{page}"
                self.assertEqual(urljoin(base, href), f"https://example.test{href}")
        for invalid in ("../repository", "fixture/../repository", "fixture/repository?query"):
            with self.subTest(repository=invalid), self.assertRaises(ValueError):
                render_settings_link(invalid)

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
        self.assertLess(
            reports.spacy.index("Status: partial."),
            reports.spacy.index("<summary>spaCy configuration"),
        )
        self.assertLess(
            reports.gliner.index("Provider error:"),
            reports.gliner.index("<summary>GLiNER configuration"),
        )
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
        repository = "fixture/repository"
        spacy = NativeFiles(
            request={"text": source, "language": "en"},
            response=spacy_result([feature("named_entities", {"entities": []})]),
            settings=spacy_settings(),
        )
        gliner = NativeFiles(
            request={"text": source, "labels": ["organization", "location", "person"]},
            response={"entities": []},
        )
        reports = render_saved_reports(source, spacy, gliner, repository=repository)
        spacy_section = render_spacy_results(
            source,
            spacy.response,
            spacy_request=spacy.request,
            spacy_settings=spacy.settings,
            repository=repository,
        )
        gliner_section = render_gliner_results(
            source, gliner.response, gliner_request=gliner.request, repository=repository
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
                repository=repository,
            ),
        )
        self.assertEqual(reports.combined.count("<h2>Source text</h2>"), 1)
        self.assertNotIn("Entity groups are sorted", reports.combined)
        self.assertNotIn(
            "spaCy sentence indexes and native case groups are retained", reports.combined
        )
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


class ClassificationTests(unittest.TestCase):
    def test_default_request_uses_active_configured_labels_and_native_modes(self) -> None:
        taxonomy = classification_taxonomy()
        before = json.dumps(taxonomy)
        tasks = read_classification_tasks(default_classification_tasks(taxonomy))
        self.assertEqual(list(tasks), ["vertical", "desk", "lenses", "source_kind"])
        self.assertEqual(
            tasks["desk"],
            {"labels": {"second": "Second desk.", "first": "First desk."}, "multi_label": False},
        )
        self.assertEqual(tasks["vertical"], tasks["desk"])
        self.assertEqual(list(read_object(tasks["lenses"]["labels"])), ["lens-a", "lens-b"])
        self.assertTrue(tasks["lenses"]["multi_label"])
        self.assertEqual(
            tasks["source_kind"],
            {
                "labels": {"reporting": "Reporting", "research": "Research"},
                "multi_label": False,
            },
        )
        self.assertEqual(json.dumps(taxonomy), before)
        for field in ("verticals", "lenses", "source_kinds"):
            empty = {**taxonomy, field: []}
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "no active labels"):
                default_classification_tasks(empty)
            undefined = {
                **taxonomy,
                field: [{"id": "undefined", "definition": " ", "display_name": " "}],
            }
            with self.subTest(field=field), self.assertRaises(ValueError):
                default_classification_tasks(undefined)

    def test_arbitrary_single_and_multiple_tasks_need_no_taxonomy_or_default_names(self) -> None:
        source = "  X\r\n"
        for count in (1, 5):
            tasks = {
                f"custom task {index}/<choice>": {
                    "labels": {"label / 1": "First <kind>", "label / 2": "Second"},
                    "multi_label": index % 2 == 0,
                }
                for index in reversed(range(count))
            }
            selections = {
                name: [{"id": "label / 2", "score": 0.25}]
                + ([{"id": "label / 1", "score": 0.95}] if task["multi_label"] else [])
                for name, task in reversed(list(tasks.items()))
            }
            request: dict[str, object] = {"text": source, "tasks": tasks}
            response: dict[str, object] = {"classifications": selections}
            before = json.dumps((request, response))
            with self.subTest(count=count):
                classification = render_classifications(source, response, request=request)
                rows = [
                    line
                    for line in html.unescape(classification.content).splitlines()
                    if line.startswith("| L")
                ]
                expected: list[str] = []
                for name, task in tasks.items():
                    labels = read_object(task["labels"])
                    for selected in selections[name]:
                        expected.append(
                            f"| L{len(expected) + 1} | {name} | {selected['id']} | "
                            f"{labels[str(selected['id'])]} | {selected['score']} |"
                        )
                self.assertEqual(rows, expected)
                self.assertNotIn("<choice>", classification.content)
                self.assertNotIn("<kind>", classification.content)
                self.assertEqual(json.dumps((request, response)), before)
                self.assertIs(classification.request, request)
                self.assertIs(classification.result, response)

    def test_historical_tasks_preserve_source_labels_selections_and_scores_without_taxonomy(
        self,
    ) -> None:
        source = "  X\r\n"
        request = historical_classification_request(source)
        response = classification_result()
        before = json.dumps((request, response))
        classification = render_classifications(source, response, request=request)
        report = html.unescape(classification.content)
        self.assertIn("| L1 | desk | second | Second <desk>. | 0.8 |", report)
        self.assertIn("| L2 | lenses | lens-b | Second lens. | 0.25 |", report)
        self.assertIn("| L3 | lenses | lens-a | First lens. | 0.95 |", report)
        self.assertIn("| L4 | events | No label selected | - | - |", report)
        self.assertLess(report.index("| L2"), report.index("| L3"))
        self.assertNotIn("<desk>", classification.content)
        self.assertIn("higher means stronger model confidence", report)
        self.assertIn("not calibrated correctness percentages", report)
        self.assertIn("can aggregate chunks", report)
        self.assertIn("does not guarantee abstention", report)
        self.assertNotIn("YAKE", report)
        self.assertEqual(json.dumps((request, response)), before)
        with self.assertRaises(ValueError):
            render_classifications("X\n", response, request=request)

    def test_classification_refuses_missing_tasks_wrong_ids_cardinality_and_invalid_scores(
        self,
    ) -> None:
        tasks = read_classification_tasks(historical_classification_request("X")["tasks"])
        invalid: list[dict[str, object]] = [
            {"desk": [], "lenses": []},
            {"desk": [], "lenses": [], "events": [], "invented": []},
            {"desk": [{"id": "event", "score": 0.5}], "lenses": [], "events": []},
            {
                "desk": [{"id": "second", "score": 0.5}, {"id": "first", "score": 0.4}],
                "lenses": [],
                "events": [],
            },
            {
                "desk": [],
                "lenses": [{"id": "lens-a", "score": 0.5}, {"id": "lens-a", "score": 0.4}],
                "events": [],
            },
        ]
        invalid.extend(
            {"desk": [{"id": "second", "score": score}], "lenses": [], "events": []}
            for score in (float("nan"), float("inf"), -0.1, 1.1, True, "0.5")
        )
        for classifications in invalid:
            with self.subTest(result=classifications), self.assertRaises(ValueError):
                read_classification_selections({"classifications": classifications}, tasks)
        empty: dict[str, object] = {"classifications": {name: [] for name in tasks}}
        self.assertEqual(read_classification_selections(empty, tasks), {name: [] for name in tasks})

    def test_classification_composes_identically_and_failure_does_not_hide_ner(self) -> None:
        source = "X"
        request = historical_classification_request(source)
        response = classification_result()
        spacy = NativeFiles(
            request={"text": source, "language": "en"},
            response=spacy_result([feature("named_entities", {"entities": []})]),
        )
        gliner = NativeFiles(
            request={"text": source, "labels": ["person"]}, response={"entities": []}
        )
        files = NativeFiles(request=request, response=response)
        reports = render_saved_reports(source, spacy, gliner, classification=files)
        section = render_classifications(source, response, request=request)
        self.assertFalse(reports.failed)
        self.assertIn(section.content, reports.gliner)
        self.assertIn(section.content, reports.combined)
        self.assertNotIn(section.content, reports.spacy)
        self.assertIn("classify&#45;text&#45;gliner", reports.gliner)
        self.assertIn("single&#45;label", reports.gliner)
        self.assertIn("Second <desk>", html.unescape(reports.gliner))
        for name, task in read_classification_tasks(request["tasks"]).items():
            mode = "multi-label" if task["multi_label"] else "single-label"
            self.assertIn(
                f"| Classification task: {name} | {mode}; "
                f"{json.dumps(task['labels'])} (classification/request.json) |",
                html.unescape(reports.gliner),
            )
        self.assertEqual(
            reports.combined,
            render_report(
                source,
                spacy.response,
                gliner.response,
                spacy_request=spacy.request,
                gliner_request=gliner.request,
                classification=section,
            ),
        )
        ids = re.findall(r"^\| ([A-Z]+\d+) \|", reports.combined, re.MULTILINE)
        self.assertEqual(len(ids), len(set(ids)))
        for failed in (
            NativeFiles(request=request, error="Classification transport failed."),
            NativeFiles(request=request, response={"classifications": {"desk": []}}),
            NativeFiles(
                request=request,
                response={
                    "error": {
                        "code": "INPUT_UNSUPPORTED",
                        "message": "The native model cannot process this input.",
                        "retryable": False,
                    }
                },
            ),
        ):
            with self.subTest(failed=failed):
                reports = render_saved_reports(source, spacy, gliner, classification=failed)
                self.assertTrue(reports.failed)
                self.assertIn("Status: complete.", reports.spacy)
                self.assertIn("Status: complete.", reports.gliner)
                self.assertIn("Classification error:", reports.gliner)
        reports = render_saved_reports(
            source,
            spacy,
            NativeFiles(request=gliner.request, error="NER transport failed."),
            classification=files,
        )
        self.assertTrue(reports.failed)
        self.assertIn(section.content, reports.gliner)
        self.assertIn("Provider error:", reports.gliner)


class OperationSchedulingTests(unittest.IsolatedAsyncioTestCase):
    async def test_both_operations_start_before_either_response_and_keep_independent_outcomes(
        self,
    ) -> None:
        ner_started, classification_started = asyncio.Event(), asyncio.Event()
        ner = Outcome(error="NER failed.")
        classification = Outcome(result=classification_result())

        async def receive(
            started: asyncio.Event, sibling: asyncio.Event, outcome: Outcome
        ) -> Outcome:
            started.set()
            await sibling.wait()
            return outcome

        results = await asyncio.wait_for(
            collect_gliner_operations(
                receive(ner_started, classification_started, ner),
                receive(classification_started, ner_started, classification),
            ),
            timeout=1,
        )
        self.assertEqual(results, (ner, classification))

    async def test_unexpected_error_is_raised_only_after_sibling_finishes(self) -> None:
        finished = asyncio.Event()

        async def fail() -> Outcome:
            raise ValueError("Unexpected operation failure.")

        async def finish() -> Outcome:
            await asyncio.sleep(0)
            finished.set()
            return Outcome(result=classification_result())

        with self.assertRaises(ValueError):
            await collect_gliner_operations(fail(), finish())
        self.assertTrue(finished.is_set())


def load_tests(
    loader: unittest.TestLoader, tests: unittest.TestSuite, pattern: str | None
) -> unittest.TestSuite:
    tests.addTests(loader.loadTestsFromModule(test_capture_stream))
    return tests


if __name__ == "__main__":
    unittest.main()
