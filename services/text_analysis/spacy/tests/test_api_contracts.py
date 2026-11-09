"""Which native API boundaries preserve old reads, language defaults and local failures?"""

import json
import unittest
from pathlib import Path

import spacy
from fastapi.testclient import TestClient
from pydantic import ValidationError
from text_analysis.create_api_component import _health_capabilities, create_app
from text_analysis.declare_api_contracts import (
    ANALYZE_TEXT_PATH,
    API_SCHEMA_VERSION,
    HEALTH_PATH,
    SCHEMA_PATH,
    AnalysisCommand,
    AnalysisResult,
    DocumentMetricsData,
    EvidenceSpan,
    FeatureResult,
    ImportantTermRecord,
    ImportantTermsData,
    ModelIdentity,
    NamedEntitiesData,
    NamedEntityRecord,
    SentencesData,
    TextAnalysisEvent,
)
from text_analysis.declare_service_settings import (
    ALL_FEATURES,
    ImportantTermsSettings,
    NamedEntitiesSettings,
    ServiceSettings,
    SettingsVersion,
)
from text_analysis.extract_features import extract_feature_results
from text_analysis.load_service_settings import load_service_settings
from text_analysis.manage_models import LoadedModel, _unavailable_features

GLOBAL_DEFAULTS = ("relations", "entities", "sentences", "document_metrics")


def _settings(version: SettingsVersion = "2026-11-09") -> ServiceSettings:
    """Use the one named configuration contract, altering old-shape inputs in memory."""
    current = load_service_settings(Path(__file__).resolve().parents[4])
    if version == current.version:
        return current
    previous = current.model_dump(mode="json")
    previous["version"] = version
    previous["changelog"] = [{"version": version, "change": "Declare test settings."}]
    previous["default_features"] = list(GLOBAL_DEFAULTS)
    previous["allowed_features"] = [
        feature for feature in ALL_FEATURES if feature not in ("named_entities", "important_terms")
    ]
    for language in previous["languages"].values():
        language.pop("default_features", None)
        language["supported_features"] = [
            feature
            for feature in language["supported_features"]
            if feature not in ("named_entities", "important_terms")
        ]
    del previous["named_entities"]
    del previous["important_terms"]
    return ServiceSettings.model_validate_json(json.dumps(previous))


class NativeContractsTests(unittest.TestCase):
    def test_compact_records_require_nonempty_occurrences_and_finite_ranks(self) -> None:
        span = EvidenceSpan(text="River", start_char=0, end_char=5, sentence_index=0)
        entity = NamedEntityRecord(text="River", type="location", occurrences=(span,))
        term = ImportantTermRecord(text="River", score=0.0, occurrences=(span,))
        result = FeatureResult(
            feature="named_entities",
            status="complete",
            data=NamedEntitiesData(entities=(entity,)),
            error=None,
        )
        assert isinstance(result.data, NamedEntitiesData)
        self.assertEqual(result.data.entities, (entity,))
        with self.assertRaises(ValidationError):
            NamedEntityRecord(text="River", type="location", occurrences=())
        for score in (-1.0, float("inf"), float("nan"), "0.1", True):
            with self.subTest(score=score), self.assertRaises(ValidationError):
                ImportantTermRecord(text="River", score=score, occurrences=(span,))
        with self.assertRaises(ValidationError):
            FeatureResult(
                feature="entities",
                status="complete",
                data=ImportantTermsData(terms=(term,)),
                error=None,
            )

    def test_schema_versions_preserve_raw_and_receipt_independence(self) -> None:
        self.assertEqual(ImportantTermsData.model_json_schema()["version"], API_SCHEMA_VERSION)
        self.assertEqual(FeatureResult.model_json_schema()["version"], API_SCHEMA_VERSION)
        for contract in (EvidenceSpan, AnalysisResult, TextAnalysisEvent):
            self.assertEqual(contract.model_json_schema()["version"], "2026-11-07")


class LanguageSettingsTests(unittest.TestCase):
    def test_english_override_and_chinese_inheritance_are_visible_in_health(self) -> None:
        settings = _settings()
        capabilities = {item.language: item for item in _health_capabilities(settings)}
        self.assertEqual(
            settings.resolve_default_features("en"),
            ("named_entities", "important_terms", "relations"),
        )
        self.assertEqual(settings.resolve_default_features("zh"), GLOBAL_DEFAULTS)
        self.assertEqual(
            capabilities["en"].default_features, settings.resolve_default_features("en")
        )
        self.assertEqual(
            capabilities["en"].important_terms_limit, settings.important_terms.max_results
        )
        self.assertEqual(capabilities["zh"].default_features, GLOBAL_DEFAULTS)
        self.assertIsNone(capabilities["zh"].important_terms_limit)
        self.assertNotIn("named_entities", capabilities["zh"].supported_features)
        self.assertNotIn("important_terms", capabilities["zh"].supported_features)

    def test_previous_settings_keep_their_version_and_feature_selection(self) -> None:
        settings = _settings("2026-11-07")
        reread = ServiceSettings.model_validate_json(settings.model_dump_json())
        self.assertEqual(reread.version, "2026-11-07")
        self.assertEqual(reread.resolve_default_features("en"), GLOBAL_DEFAULTS)
        self.assertEqual(reread.resolve_default_features("zh"), GLOBAL_DEFAULTS)
        self.assertEqual(reread.named_entities, NamedEntitiesSettings())
        self.assertEqual(reread.important_terms, ImportantTermsSettings())
        self.assertTrue(
            all(item.important_terms_limit is None for item in _health_capabilities(reread))
        )

    def test_feature_settings_reject_coercion_and_invalid_ranges(self) -> None:
        for field, value in (
            ("max_results", -1),
            ("max_results", True),
            ("max_results", "25"),
            ("max_phrase_words", 0),
            ("window_size", 0),
            ("deduplication_threshold", 1.1),
            ("deduplication_threshold", float("nan")),
            ("deduplication_method", "unknown"),
            ("stopwords", ()),
        ):
            with self.subTest(field=field, value=value), self.assertRaises(ValidationError):
                ImportantTermsSettings.model_validate({field: value})
        with self.assertRaises(ValidationError):
            NamedEntitiesSettings(ignore_case=1)
        with self.assertRaises(ValidationError):
            NamedEntitiesSettings(label_map={"PERSON": " "})


class ApiBoundaryTests(unittest.TestCase):
    def test_native_factory_preserves_components_guards_and_exact_dated_routes(self) -> None:
        settings = _settings().model_copy(update={"enabled": False})
        app = create_app(settings)
        self.assertIs(app.state.component.state, app.state.text_analysis_runtime)
        self.assertIsNotNone(app.state.text_analysis_events)
        self.assertTrue(callable(app.router.lifespan_context))
        with TestClient(app, base_url="http://127.0.0.1:3020") as client:
            schema = client.get(SCHEMA_PATH)
            self.assertEqual(schema.status_code, 200)
            self.assertEqual(schema.json()["info"]["version"], API_SCHEMA_VERSION)
            self.assertIn(ANALYZE_TEXT_PATH, schema.json()["paths"])
            for path in (
                "/api/2026-11-07/analyze-text",
                "/api/2026-11-07/get-text-analysis-health",
                "/api/2026-11-07/get-text-analysis-schema",
                ANALYZE_TEXT_PATH + "/",
            ):
                with self.subTest(path=path):
                    self.assertEqual(client.get(path).status_code, 404)
            for path, method, allowed in (
                (ANALYZE_TEXT_PATH, "GET", "POST"),
                (HEALTH_PATH, "POST", "GET"),
                (SCHEMA_PATH, "POST", "GET"),
            ):
                response = client.request(method, path)
                self.assertEqual(response.status_code, 405)
                self.assertIn(allowed, response.headers["allow"])
            health = client.get(HEALTH_PATH)
            self.assertEqual(health.status_code, 503)
            self.assertIn("traceparent", health.headers)
            self.assertEqual(
                client.post(
                    ANALYZE_TEXT_PATH, headers={"origin": "https://invalid.example"}
                ).status_code,
                403,
            )


class FeatureExecutionTests(unittest.TestCase):
    def test_real_unanchored_yake_phrase_fails_only_important_terms(self) -> None:
        settings = _settings()
        nlp = spacy.blank("en")
        nlp.add_pipe("sentencizer")
        source = "River\nmapping improves flood planning. River\nmapping improves flood planning."
        doc = nlp(source)
        command = AnalysisCommand(
            text=source,
            language="en",
            profile="md",
            features=("sentences", "important_terms", "document_metrics"),
        )
        loaded = LoadedModel(
            nlp=nlp,
            identity=ModelIdentity(
                profile="md",
                package="in_memory_document",
                model_version="3.8.0",
                spacy_version="3.8.18",
            ),
            unavailable_features=frozenset(),
            relation_policy=settings.relation_rules.resolve("en"),
        )
        results = extract_feature_results(doc, command, loaded, settings)
        self.assertEqual([item.status for item in results], ["complete", "failed", "complete"])
        assert results[1].error is not None
        self.assertEqual(results[1].error.code, "FEATURE_FAILED")
        self.assertIsNone(results[1].data)
        assert isinstance(results[0].data, SentencesData)
        assert isinstance(results[2].data, DocumentMetricsData)
        self.assertEqual(results[2].data.codepoint_count, len(source))
        zero_settings = settings.model_copy(
            update={"important_terms": ImportantTermsSettings(max_results=0)}
        )
        zero_results = extract_feature_results(doc, command, loaded, zero_settings)
        self.assertEqual(
            [item.status for item in zero_results], ["complete", "complete", "complete"]
        )
        assert isinstance(zero_results[1].data, ImportantTermsData)
        self.assertEqual(zero_results[1].data.terms, ())

    def test_missing_capabilities_and_chinese_refuse_only_unavailable_features(self) -> None:
        settings = _settings()
        nlp = spacy.blank("en")
        nlp.add_pipe("sentencizer")
        policy = settings.relation_rules.resolve("en")
        unavailable = _unavailable_features(nlp, settings.languages.en.supported_features, policy)
        self.assertIn("named_entities", unavailable)
        self.assertNotIn("important_terms", unavailable)
        nlp.remove_pipe("sentencizer")
        self.assertIn(
            "important_terms",
            _unavailable_features(nlp, settings.languages.en.supported_features, policy),
        )
        chinese = spacy.blank("zh")
        chinese.add_pipe("sentencizer")
        unavailable = _unavailable_features(
            chinese, settings.languages.zh.supported_features, policy
        )
        self.assertIn("named_entities", unavailable)
        self.assertIn("important_terms", unavailable)
        self.assertIn("noun_phrases", unavailable)


if __name__ == "__main__":
    unittest.main()
