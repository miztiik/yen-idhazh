/** How does the manual workflow verify the live API through shared trace and event contracts? */
import {
  CloudEventSchema,
  createRootContext,
  readTraceContext,
  writeTraceContext,
} from "../../../packages/common-contracts/src/index.ts";

type JsonRecord = Record<string, unknown>;
type Language = "en" | "zh";
type Profile = "sm" | "md" | "lg";
type Feature =
  | "entities"
  | "sentences"
  | "relations"
  | "noun_phrases"
  | "linguistic_tokens"
  | "document_metrics";
type FeatureStatus = "complete" | "failed";
type ResultStatus = "complete" | "partial" | "failed";

type ExpectedEvent = {
  label: string;
  type:
    | "text-analysis.request.completed"
    | "text-analysis.request.partial"
    | "text-analysis.request.failed";
  traceparent: string;
  result_status: ResultStatus;
  error_code?: string;
  feature_statuses: Array<{
    feature: Feature;
    status: FeatureStatus;
    error_code?: "FEATURE_UNAVAILABLE" | "FEATURE_FAILED";
  }>;
  require_zero_model_load?: boolean;
};

type ExerciseInput = {
  mode: "exercise";
  base_url: string;
  language: Language;
  profile: Profile;
  feature_mode: "default" | "all" | "custom";
  custom_features: string;
  text: string;
};

type ValidateEventsInput = {
  mode: "validate_events";
  events_path: string;
  text: string;
  exercise: JsonRecord;
};

type TraceCall = {
  status: number;
  body: unknown;
  traceparent: string;
  tracestate?: string;
};

type ExpectedModelIdentity = {
  package: string;
  model_version: string;
  spacy_version: string;
};

const API_PREFIX = "/api/2026-11-07";
const ANALYZE_PATH = `${API_PREFIX}/analyze-text`;
const HEALTH_PATH = `${API_PREFIX}/get-text-analysis-health`;
const SCHEMA_PATH = `${API_PREFIX}/get-text-analysis-schema`;
const FEATURES: readonly Feature[] = [
  "entities",
  "sentences",
  "relations",
  "noun_phrases",
  "linguistic_tokens",
  "document_metrics",
];
const DEFAULT_FEATURES: readonly Feature[] = [
  "relations",
  "entities",
  "sentences",
  "document_metrics",
];
const EVENT_TRACE_STATE = "workflow=spacy";
const CONCURRENCY_TEXT_BYTES = 750_000;
const SERVICE_FAILURE_CODES = new Set([
  "ANALYSIS_FAILED",
  "INVALID_SERVER_SETTINGS",
  "LISTENER_BIND_FAILED",
  "LOGGING_FAILED",
  "STARTUP_FAILED",
  "SHUTDOWN_FAILED",
]);
const REQUEST_ERROR_CODES = new Set([
  "INVALID_REQUEST",
  "BODY_TOO_LARGE",
  "HOST_FORBIDDEN",
  "ORIGIN_FORBIDDEN",
  "SERVICE_DISABLED",
  "BUSY",
  "LANGUAGE_UNAVAILABLE",
  "UNSUPPORTED_MODEL_PROFILE",
  "UNSUPPORTED_FEATURE",
  "MODEL_UNAVAILABLE",
  "FEATURE_UNAVAILABLE",
  "FEATURE_FAILED",
  "ANALYSIS_FAILED",
]);

function fail(message: string): never {
  throw new Error(message);
}

function expect(condition: unknown, message: string): asserts condition {
  if (!condition) fail(message);
}

function record(value: unknown, message: string): JsonRecord {
  expect(typeof value === "object" && value !== null && !Array.isArray(value), message);
  return value as JsonRecord;
}

function array(value: unknown, message: string): unknown[] {
  expect(Array.isArray(value), message);
  return value;
}

function text(value: unknown, message: string): string {
  expect(typeof value === "string", message);
  return value;
}

function integer(value: unknown, message: string): number {
  expect(typeof value === "number" && Number.isInteger(value), message);
  return value;
}

function finiteNonnegative(value: unknown, message: string): number {
  expect(typeof value === "number" && Number.isFinite(value) && value >= 0, message);
  return value;
}

function exactKeys(value: JsonRecord, required: readonly string[], optional: readonly string[] = []): void {
  const allowed = new Set([...required, ...optional]);
  expect(required.every(key => Object.hasOwn(value, key)), "Response is missing a required field");
  expect(Object.keys(value).every(key => allowed.has(key)), "Response contains an undeclared field");
}

function distinctFeatures(value: unknown, message: string): Feature[] {
  const values = array(value, message).map(item => {
    expect(typeof item === "string" && FEATURES.includes(item as Feature), message);
    return item as Feature;
  });
  expect(values.length > 0 && new Set(values).size === values.length, message);
  return values;
}

function selectFeatures(
  input: ExerciseInput,
  supportedFeatures: readonly Feature[],
): Feature[] {
  if (input.feature_mode === "default") {
    expect(input.custom_features === "", "Custom features must be blank in default mode");
    return [...DEFAULT_FEATURES];
  }
  if (input.feature_mode === "all") {
    expect(input.custom_features === "", "Custom features must be blank in all mode");
    return [...supportedFeatures];
  }
  const selected = input.custom_features.split(",").map(item => item.trim());
  expect(selected.every(item => item.length > 0), "Custom feature names are invalid");
  return distinctFeatures(selected, "Custom feature names are invalid");
}

function responseTrace(response: Response, parentTraceId: string, parentSpanId: string): {
  traceparent: string;
  tracestate?: string;
} {
  const traceparent = response.headers.get("traceparent");
  expect(traceparent !== null, "Response is missing traceparent");
  const tracestate = response.headers.get("tracestate");
  const operation = readTraceContext({
    traceparent,
    ...(tracestate === null ? {} : { tracestate }),
  });
  expect(operation !== undefined, "Response traceparent is invalid");
  expect(operation.traceId === parentTraceId, "Response changed the trace id");
  expect(operation.spanId !== parentSpanId, "Response reused the caller span id");
  expect(tracestate === EVENT_TRACE_STATE, "Response did not retain canonical tracestate");
  return {
    traceparent,
    ...(tracestate === null ? {} : { tracestate }),
  };
}

async function callApi(
  input: ExerciseInput,
  path: string,
  method: "GET" | "POST",
  body?: JsonRecord,
): Promise<TraceCall> {
  const context = createRootContext({ traceState: EVENT_TRACE_STATE });
  const carrier = writeTraceContext(context);
  const response = await fetch(new URL(path, input.base_url), {
    method,
    headers: {
      ...carrier,
      ...(body === undefined ? {} : { "content-type": "application/json" }),
    },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  const traced = responseTrace(response, context.traceId, context.spanId);
  let parsed: unknown;
  try {
    parsed = await response.json();
  } catch {
    fail("API response is not JSON");
  }
  return { status: response.status, body: parsed, ...traced };
}

function validateProfile(value: unknown): JsonRecord {
  const profile = record(value, "Health profile capability is invalid");
  exactKeys(profile, ["profile", "package", "model_version"]);
  expect(["sm", "md", "lg"].includes(text(profile.profile, "Profile name is invalid")), "Profile name is invalid");
  text(profile.package, "Profile package is invalid");
  text(profile.model_version, "Profile version is invalid");
  return profile;
}

function validateHealth(value: unknown): JsonRecord {
  const health = record(value, "Health response is invalid");
  exactKeys(health, [
    "enabled",
    "status",
    "active_requests",
    "max_concurrent_requests",
    "pool_ready",
    "spacy_version",
    "default_features",
    "allowed_features",
    "languages",
  ]);
  expect(typeof health.enabled === "boolean", "Health enabled is invalid");
  expect(["ready", "disabled", "failed", "stopping"].includes(text(health.status, "Health status is invalid")), "Health status is invalid");
  integer(health.active_requests, "Health active request count is invalid");
  integer(health.max_concurrent_requests, "Health capacity is invalid");
  expect(typeof health.pool_ready === "boolean", "Health pool state is invalid");
  text(health.spacy_version, "Health spaCy version is invalid");
  distinctFeatures(health.default_features, "Health default features are invalid");
  distinctFeatures(health.allowed_features, "Health allowed features are invalid");
  const languages = array(health.languages, "Health language capabilities are invalid");
  expect(languages.length === 3, "Health language capabilities are incomplete");
  for (const rawLanguage of languages) {
    const language = record(rawLanguage, "Health language capability is invalid");
    exactKeys(language, [
      "language",
      "enabled",
      "default_profile",
      "supported_features",
      "profiles",
    ]);
    expect(["en", "zh", "ta"].includes(text(language.language, "Health language is invalid")), "Health language is invalid");
    expect(typeof language.enabled === "boolean", "Health language enablement is invalid");
    expect(language.default_profile === null || ["sm", "md", "lg"].includes(text(language.default_profile, "Health default profile is invalid")), "Health default profile is invalid");
    const supported = array(language.supported_features, "Health supported features are invalid");
    expect(supported.every(item => typeof item === "string" && FEATURES.includes(item as Feature)), "Health supported features are invalid");
    array(language.profiles, "Health profiles are invalid").forEach(validateProfile);
  }
  return health;
}

function configuredModel(
  health: JsonRecord,
  language: Language,
  profile: Profile,
): { supported_features: Feature[]; identity: ExpectedModelIdentity } {
  const capability = array(health.languages, "Health languages are invalid")
    .map(item => record(item, "Health language capability is invalid"))
    .find(item => item.language === language);
  expect(capability !== undefined && capability.enabled === true, "Selected language is not enabled");
  const supported = array(capability.supported_features, "Supported features are invalid")
    .map(item => text(item, "Supported feature is invalid") as Feature);
  const configuredProfile = array(capability.profiles, "Configured profiles are invalid")
    .map(item => record(item, "Configured profile is invalid"))
    .find(item => item.profile === profile);
  expect(configuredProfile !== undefined, "Selected profile is not configured");
  return {
    supported_features: supported,
    identity: {
      package: text(configuredProfile.package, "Configured package is invalid"),
      model_version: text(configuredProfile.model_version, "Configured model version is invalid"),
      spacy_version: text(health.spacy_version, "Configured spaCy version is invalid"),
    },
  };
}

function validateError(value: unknown, expectedCode: string): JsonRecord {
  const result = record(value, "Error response is invalid");
  exactKeys(result, ["error"]);
  const error = record(result.error, "Error detail is invalid");
  exactKeys(error, ["code", "message", "retryable", "feature"]);
  expect(error.code === expectedCode, "Error response code is unexpected");
  text(error.message, "Error response message is invalid");
  expect(typeof error.retryable === "boolean", "Error retryable value is invalid");
  expect(error.feature === null, "Request-level error must not name a feature");
  return result;
}

function validateEvidenceSpan(value: unknown, source: string, evidence: Set<string>): JsonRecord {
  const span = record(value, "Evidence span is invalid");
  exactKeys(span, ["text", "start_char", "end_char", "sentence_index"]);
  const spanText = text(span.text, "Evidence text is invalid");
  const start = integer(span.start_char, "Evidence start is invalid");
  const end = integer(span.end_char, "Evidence end is invalid");
  integer(span.sentence_index, "Evidence sentence index is invalid");
  expect(start >= 0 && end > start && source.slice(start, end) === spanText, "Evidence offsets do not reproduce the source");
  evidence.add(spanText);
  return span;
}

function validateFeatureData(
  feature: Feature,
  value: unknown,
  source: string,
  evidence: Set<string>,
): void {
  const data = record(value, "Feature data is invalid");
  if (feature === "entities") {
    exactKeys(data, ["mentions"]);
    for (const rawMention of array(data.mentions, "Entity mentions are invalid")) {
      const mention = record(rawMention, "Entity mention is invalid");
      exactKeys(mention, ["text", "start_char", "end_char", "sentence_index", "label"]);
      validateEvidenceSpan({
        text: mention.text,
        start_char: mention.start_char,
        end_char: mention.end_char,
        sentence_index: mention.sentence_index,
      }, source, evidence);
      text(mention.label, "Entity label is invalid");
    }
    return;
  }
  if (feature === "sentences") {
    exactKeys(data, ["sentences"]);
    array(data.sentences, "Sentence spans are invalid").forEach(item => validateEvidenceSpan(item, source, evidence));
    return;
  }
  if (feature === "relations") {
    exactKeys(data, ["relations"]);
    for (const rawRelation of array(data.relations, "Relation records are invalid")) {
      const relation = record(rawRelation, "Relation record is invalid");
      exactKeys(relation, ["sentence_index", "action", "actors", "objects", "times", "places"]);
      integer(relation.sentence_index, "Relation sentence index is invalid");
      validateEvidenceSpan(relation.action, source, evidence);
      const actors = array(relation.actors, "Relation actors are invalid");
      expect(actors.length > 0, "Relation must retain an actor");
      actors.forEach(item => validateEvidenceSpan(item, source, evidence));
      for (const key of ["objects", "times", "places"] as const) {
        array(relation[key], "Relation evidence list is invalid").forEach(item => validateEvidenceSpan(item, source, evidence));
      }
    }
    return;
  }
  if (feature === "noun_phrases") {
    exactKeys(data, ["phrases"]);
    array(data.phrases, "Noun phrase spans are invalid").forEach(item => validateEvidenceSpan(item, source, evidence));
    return;
  }
  if (feature === "linguistic_tokens") {
    exactKeys(data, ["tokens"]);
    for (const rawToken of array(data.tokens, "Linguistic tokens are invalid")) {
      const token = record(rawToken, "Linguistic token is invalid");
      exactKeys(token, [
        "text",
        "start_char",
        "end_char",
        "sentence_index",
        "lemma",
        "part_of_speech",
        "dependency",
        "head_index",
        "morphology",
      ]);
      validateEvidenceSpan({
        text: token.text,
        start_char: token.start_char,
        end_char: token.end_char,
        sentence_index: token.sentence_index,
      }, source, evidence);
      for (const key of ["lemma", "part_of_speech", "dependency", "morphology"] as const) {
        expect(token[key] === null || typeof token[key] === "string", "Nullable token annotation is invalid");
      }
      expect(token.head_index === null || Number.isInteger(token.head_index), "Nullable token head is invalid");
    }
    return;
  }
  exactKeys(data, [
    "codepoint_count",
    "utf8_byte_count",
    "token_count",
    "sentence_count",
    "entity_count",
    "relation_count",
  ]);
  for (const key of ["codepoint_count", "utf8_byte_count", "token_count", "sentence_count", "entity_count"] as const) {
    expect(integer(data[key], "Document metric is invalid") >= 0, "Document metric is invalid");
  }
  expect(data.relation_count === null || (Number.isInteger(data.relation_count) && (data.relation_count as number) >= 0), "Relation count is invalid");
}

function validateAnalysisResult(
  value: unknown,
  language: Language,
  profile: Profile,
  expectedFeatures: readonly Feature[],
  expectedModel: ExpectedModelIdentity,
  source: string,
): { result: JsonRecord; evidence: string[]; featureStatuses: ExpectedEvent["feature_statuses"] } {
  const result = record(value, "Analysis result is invalid");
  exactKeys(result, ["status", "language", "model", "features"]);
  expect(result.language === language, "Analysis result language is unexpected");
  expect(["complete", "partial", "failed"].includes(text(result.status, "Analysis result status is invalid")), "Analysis result status is invalid");
  const model = record(result.model, "Model identity is invalid");
  exactKeys(model, ["profile", "package", "model_version", "spacy_version"]);
  expect(model.profile === profile, "Model profile is unexpected");
  expect(model.package === expectedModel.package, "Model package does not match configuration");
  expect(model.model_version === expectedModel.model_version, "Model version does not match configuration");
  expect(model.spacy_version === expectedModel.spacy_version, "spaCy version does not match configuration");
  const rawFeatures = array(result.features, "Feature results are invalid");
  expect(rawFeatures.length === expectedFeatures.length, "Feature result count is unexpected");
  const evidence = new Set<string>();
  const featureStatuses: ExpectedEvent["feature_statuses"] = [];
  rawFeatures.forEach((rawFeature, index) => {
    const featureResult = record(rawFeature, "Feature result is invalid");
    exactKeys(featureResult, ["feature", "status", "data", "error"]);
    const feature = text(featureResult.feature, "Feature name is invalid") as Feature;
    expect(feature === expectedFeatures[index], "Feature order changed");
    const status = text(featureResult.status, "Feature status is invalid") as FeatureStatus;
    expect(status === "complete" || status === "failed", "Feature status is invalid");
    if (status === "complete") {
      expect(featureResult.error === null, "Complete feature retained an error");
      expect(featureResult.data !== null, "Complete feature omitted data");
      validateFeatureData(feature, featureResult.data, source, evidence);
      featureStatuses.push({ feature, status });
    } else {
      expect(featureResult.data === null, "Failed feature retained data");
      const error = record(featureResult.error, "Feature error is invalid");
      exactKeys(error, ["code", "message", "retryable", "feature"]);
      expect(error.feature === feature, "Feature error names another feature");
      const errorCode = text(error.code, "Feature error code is invalid");
      expect(errorCode === "FEATURE_UNAVAILABLE" || errorCode === "FEATURE_FAILED", "Feature error code is invalid");
      text(error.message, "Feature error message is invalid");
      expect(typeof error.retryable === "boolean", "Feature retryable value is invalid");
      featureStatuses.push({
        feature,
        status,
        error_code: errorCode,
      });
    }
  });
  const completeCount = featureStatuses.filter(item => item.status === "complete").length;
  const aggregate: ResultStatus =
    completeCount === featureStatuses.length ? "complete" : completeCount === 0 ? "failed" : "partial";
  expect(result.status === aggregate, "Analysis status does not aggregate feature outcomes");
  return { result, evidence: [...evidence], featureStatuses };
}

function expectedRequestEvent(
  label: string,
  call: TraceCall,
  resultStatus: ResultStatus,
  featureStatuses: ExpectedEvent["feature_statuses"],
  errorCode?: string,
  requireZeroModelLoad = false,
): ExpectedEvent {
  return {
    label,
    type:
      resultStatus === "complete"
        ? "text-analysis.request.completed"
        : resultStatus === "partial"
          ? "text-analysis.request.partial"
          : "text-analysis.request.failed",
    traceparent: call.traceparent,
    result_status: resultStatus,
    feature_statuses: featureStatuses,
    ...(errorCode === undefined ? {} : { error_code: errorCode }),
    ...(requireZeroModelLoad ? { require_zero_model_load: true } : {}),
  };
}

function generatedConcurrencyText(): string {
  const unit = `${"analysis".repeat(9)} `;
  const complete = unit.repeat(Math.floor(CONCURRENCY_TEXT_BYTES / unit.length));
  const remainder = "x".repeat(CONCURRENCY_TEXT_BYTES - complete.length);
  const value = complete + remainder;
  expect(new TextEncoder().encode(value).length === CONCURRENCY_TEXT_BYTES, "Concurrency text size is invalid");
  return value;
}

async function waitForActiveRequests(input: ExerciseInput, count: number): Promise<void> {
  const deadline = Date.now() + 120_000;
  while (Date.now() < deadline) {
    const call = await callApi(input, HEALTH_PATH, "GET");
    const health = validateHealth(call.body);
    if (health.active_requests === count) return;
    await Bun.sleep(100);
  }
  fail("Concurrent analyses did not become active");
}

function inspectSchema(value: unknown): { paths: string[]; feature_failed_declared: boolean } {
  const schema = record(value, "OpenAPI response is invalid");
  const paths = record(schema.paths, "OpenAPI paths are invalid");
  expect(Object.hasOwn(paths, ANALYZE_PATH), "OpenAPI omitted analyze-text");
  expect(Object.hasOwn(paths, HEALTH_PATH), "OpenAPI omitted text-analysis health");
  expect(!Object.hasOwn(paths, "/docs") && !Object.hasOwn(paths, "/redoc"), "Interactive documentation is enabled");
  const components = record(schema.components, "OpenAPI components are invalid");
  const schemas = record(components.schemas, "OpenAPI schemas are invalid");
  expect(Object.hasOwn(schemas, "AnalyzeTextRequest"), "OpenAPI omitted the request contract");
  const serialized = JSON.stringify(schemas);
  expect(serialized.includes("\"FEATURE_FAILED\""), "OpenAPI omitted FEATURE_FAILED");
  return {
    paths: Object.keys(paths).sort(),
    feature_failed_declared: true,
  };
}

async function exercise(input: ExerciseInput): Promise<JsonRecord> {
  expect(input.base_url === "http://127.0.0.1:3020", "Probe base URL is unexpected");
  expect(input.text.trim().length > 0, "Probe text must be nonblank");
  const expectedEvents: ExpectedEvent[] = [];
  const noEventTraceparents: string[] = [];

  const healthCall = await callApi(input, HEALTH_PATH, "GET");
  expect(healthCall.status === 200, "Health route is not ready");
  const health = validateHealth(healthCall.body);
  expect(health.status === "ready" && health.pool_ready === true, "Health route did not report a ready pool");
  expect(health.active_requests === 0 && health.max_concurrent_requests === 2, "Health capacity is unexpected");
  expect(
    JSON.stringify(health.default_features) === JSON.stringify(DEFAULT_FEATURES),
    "Configured default feature order is unexpected",
  );
  const configured = configuredModel(health, input.language, input.profile);
  const selectedFeatures = selectFeatures(input, configured.supported_features);
  noEventTraceparents.push(healthCall.traceparent);

  const schemaCall = await callApi(input, SCHEMA_PATH, "GET");
  expect(schemaCall.status === 200, "Schema route failed");
  const schema = inspectSchema(schemaCall.body);
  noEventTraceparents.push(schemaCall.traceparent);

  const selectedCall = await callApi(input, ANALYZE_PATH, "POST", {
    text: input.text,
    language: input.language,
    model_profile: input.profile,
    features: selectedFeatures,
  });
  const selectedSupportedCount = selectedFeatures.filter(feature =>
    configured.supported_features.includes(feature)
  ).length;
  const expectedSelectedStatus: ResultStatus =
    selectedSupportedCount === selectedFeatures.length
      ? "complete"
      : selectedSupportedCount === 0
        ? "failed"
        : "partial";
  expect(
    selectedCall.status === (expectedSelectedStatus === "failed" ? 422 : 200),
    "Selected analysis status code is unexpected",
  );
  const selected = validateAnalysisResult(
    selectedCall.body,
    input.language,
    input.profile,
    selectedFeatures,
    configured.identity,
    input.text,
  );
  expect(selected.result.status === expectedSelectedStatus, "Selected analysis status is unexpected");
  expectedEvents.push(expectedRequestEvent(
    "selected-analysis",
    selectedCall,
    expectedSelectedStatus,
    selected.featureStatuses,
    expectedSelectedStatus === "partial" ? "FEATURE_UNAVAILABLE" : undefined,
  ));

  const tamilCall = await callApi(input, ANALYZE_PATH, "POST", {
    text: input.text,
    language: "ta",
    model_profile: input.profile,
    features: selectedFeatures,
  });
  expect(tamilCall.status === 422, "Tamil request did not fail before executor admission");
  validateError(tamilCall.body, "LANGUAGE_UNAVAILABLE");
  expectedEvents.push(expectedRequestEvent(
    "tamil-unavailable",
    tamilCall,
    "failed",
    [],
    "LANGUAGE_UNAVAILABLE",
  ));

  if (input.language === "zh") {
    const nounFeatures: Feature[] = ["sentences", "noun_phrases", "document_metrics"];
    const nounCall = await callApi(input, ANALYZE_PATH, "POST", {
      text: input.text,
      language: input.language,
      model_profile: input.profile,
      features: nounFeatures,
    });
    expect(nounCall.status === 200, "Chinese noun phrase failure did not preserve siblings");
    const nounResult = validateAnalysisResult(
      nounCall.body,
      input.language,
      input.profile,
      nounFeatures,
      configured.identity,
      input.text,
    );
    expect(nounResult.result.status === "partial", "Chinese noun phrase result is not partial");
    const nounStatus = nounResult.featureStatuses.find(item => item.feature === "noun_phrases");
    expect(nounStatus?.error_code === "FEATURE_UNAVAILABLE", "Chinese noun phrases did not fail locally");
    expectedEvents.push(expectedRequestEvent(
      "chinese-noun-phrases",
      nounCall,
      "partial",
      nounResult.featureStatuses,
      "FEATURE_UNAVAILABLE",
    ));
    selected.evidence.push(...nounResult.evidence);
  }

  const largeText = generatedConcurrencyText();
  const metricsFeatures: Feature[] = ["document_metrics"];
  const firstPromise = callApi(input, ANALYZE_PATH, "POST", {
    text: largeText,
    language: input.language,
    model_profile: input.profile,
    features: metricsFeatures,
  });
  const secondPromise = callApi(input, ANALYZE_PATH, "POST", {
    text: largeText,
    language: input.language,
    model_profile: input.profile,
    features: metricsFeatures,
  });
  await waitForActiveRequests(input, 2);
  const busyCall = await callApi(input, ANALYZE_PATH, "POST", {
    text: input.text,
    language: input.language,
    model_profile: input.profile,
    features: metricsFeatures,
  });
  expect(busyCall.status === 429, "Third concurrent request was not refused immediately");
  validateError(busyCall.body, "BUSY");
  expectedEvents.push(expectedRequestEvent(
    "busy-refusal",
    busyCall,
    "failed",
    [],
    "BUSY",
  ));

  const [firstCall, secondCall] = await Promise.all([firstPromise, secondPromise]);
  for (const [label, call] of [["concurrency-first", firstCall], ["concurrency-second", secondCall]] as const) {
    expect(call.status === 200, "Concurrent analysis failed");
    const result = validateAnalysisResult(
      call.body,
      input.language,
      input.profile,
      metricsFeatures,
      configured.identity,
      largeText,
    );
    const metrics = record(record(array(result.result.features, "Metrics result is invalid")[0], "Metrics feature is invalid").data, "Metrics data is invalid");
    expect(metrics.codepoint_count === CONCURRENCY_TEXT_BYTES, "Concurrency code-point count is unexpected");
    expect(metrics.utf8_byte_count === CONCURRENCY_TEXT_BYTES, "Concurrency byte count is unexpected");
    expectedEvents.push(expectedRequestEvent(label, call, "complete", result.featureStatuses));
  }

  const warmCall = await callApi(input, ANALYZE_PATH, "POST", {
    text: input.text,
    language: input.language,
    model_profile: input.profile,
    features: selectedFeatures,
  });
  expect(
    warmCall.status === (expectedSelectedStatus === "failed" ? 422 : 200),
    "Warm repeated analysis status code is unexpected",
  );
  const warm = validateAnalysisResult(
    warmCall.body,
    input.language,
    input.profile,
    selectedFeatures,
    configured.identity,
    input.text,
  );
  expectedEvents.push(expectedRequestEvent(
    "warm-repeat",
    warmCall,
    warm.result.status as ResultStatus,
    warm.featureStatuses,
    warm.result.status === "partial" ? "FEATURE_UNAVAILABLE" : undefined,
    true,
  ));
  selected.evidence.push(...warm.evidence);

  return {
    selected_result: selected.result,
    health,
    schema,
    expected_events: expectedEvents,
    no_event_traceparents: noEventTraceparents,
    evidence_texts: [...new Set(selected.evidence)],
    checks: {
      selected_features: selectedFeatures,
      tamil_unavailable: true,
      chinese_noun_phrase_partial: input.language === "zh",
      concurrent_active_requests: 2,
      busy_refused: true,
      concurrency_text_bytes: CONCURRENCY_TEXT_BYTES,
      warm_repeat_requested: true,
    },
  };
}

function validateServiceData(value: unknown): void {
  const data = record(value, "Service event data is invalid");
  exactKeys(
    data,
    ["level", "enabled", "status", "active_requests", "max_concurrent_requests", "pool_ready"],
    ["error_code"],
  );
  expect(data.level === "INFO" || data.level === "ERROR", "Service event level is invalid");
  expect(typeof data.enabled === "boolean", "Service event enablement is invalid");
  expect(["starting", "ready", "disabled", "failed", "stopping", "stopped"].includes(text(data.status, "Service event status is invalid")), "Service event status is invalid");
  expect(integer(data.active_requests, "Service event active count is invalid") >= 0, "Service event active count is invalid");
  expect(integer(data.max_concurrent_requests, "Service event capacity is invalid") > 0, "Service event capacity is invalid");
  expect(typeof data.pool_ready === "boolean", "Service event pool state is invalid");
  if (Object.hasOwn(data, "error_code")) {
    expect(
      SERVICE_FAILURE_CODES.has(text(data.error_code, "Service event error code is invalid")),
      "Service event error code is invalid",
    );
  }
  expect(
    (data.status === "failed") === Object.hasOwn(data, "error_code"),
    "Service failure state and error code disagree",
  );
}

function validateRequestData(value: unknown): JsonRecord {
  const data = record(value, "Request event data is invalid");
  exactKeys(
    data,
    [
      "level",
      "requested_features",
      "feature_statuses",
      "active_requests",
      "max_concurrent_requests",
      "model_load_ms",
      "analysis_ms",
      "total_ms",
      "result_status",
    ],
    ["language", "model_profile", "package", "model_version", "spacy_version", "error_code"],
  );
  expect(data.level === "INFO" || data.level === "ERROR", "Request event level is invalid");
  const requested = array(data.requested_features, "Request event features are invalid");
  expect(requested.every(item => typeof item === "string" && FEATURES.includes(item as Feature)), "Request event features are invalid");
  const featureStatuses = array(data.feature_statuses, "Request feature statuses are invalid");
  for (const rawStatus of featureStatuses) {
    const status = record(rawStatus, "Request feature status is invalid");
    exactKeys(status, ["feature", "status", "error_code"]);
    expect(typeof status.feature === "string" && FEATURES.includes(status.feature as Feature), "Request feature name is invalid");
    expect(status.status === "complete" || status.status === "failed", "Request feature status is invalid");
    expect(status.error_code === null || status.error_code === "FEATURE_UNAVAILABLE" || status.error_code === "FEATURE_FAILED", "Request feature error code is invalid");
  }
  expect(integer(data.active_requests, "Request event active count is invalid") >= 0, "Request event active count is invalid");
  expect(integer(data.max_concurrent_requests, "Request event capacity is invalid") > 0, "Request event capacity is invalid");
  finiteNonnegative(data.model_load_ms, "Request event model load timing is invalid");
  finiteNonnegative(data.analysis_ms, "Request event analysis timing is invalid");
  finiteNonnegative(data.total_ms, "Request event total timing is invalid");
  expect(data.result_status === "complete" || data.result_status === "partial" || data.result_status === "failed", "Request event result status is invalid");
  if (featureStatuses.length > 0) {
    for (const key of ["language", "model_profile", "package", "model_version", "spacy_version"] as const) {
      expect(Object.hasOwn(data, key), "Feature outcome event omitted model identity");
    }
  }
  for (const key of ["language", "model_profile", "package", "model_version", "spacy_version", "error_code"] as const) {
    if (Object.hasOwn(data, key)) text(data[key], "Optional request event field is invalid");
  }
  if (Object.hasOwn(data, "error_code")) {
    expect(
      REQUEST_ERROR_CODES.has(data.error_code as string),
      "Request event error code is invalid",
    );
  }
  expect(
    (data.result_status !== "complete") === Object.hasOwn(data, "error_code"),
    "Request result status and error code disagree",
  );
  return data;
}

function collectStrings(value: unknown, output: string[]): void {
  if (typeof value === "string") {
    output.push(value);
    return;
  }
  if (Array.isArray(value)) {
    value.forEach(item => collectStrings(item, output));
    return;
  }
  if (typeof value === "object" && value !== null) {
    Object.values(value as JsonRecord).forEach(item => collectStrings(item, output));
  }
}

async function validateEvents(input: ValidateEventsInput): Promise<JsonRecord> {
  const exerciseReport = record(input.exercise, "Exercise report is invalid");
  const expectedEvents = array(exerciseReport.expected_events, "Expected event list is invalid") as ExpectedEvent[];
  const noEventTraceparents = array(exerciseReport.no_event_traceparents, "No-event trace list is invalid").map(item => text(item, "No-event trace is invalid"));
  const evidenceTexts = array(exerciseReport.evidence_texts, "Evidence text list is invalid").map(item => text(item, "Evidence text is invalid"));
  const content = await Bun.file(input.events_path).text();
  const lines = content.split(/\r?\n/).filter(line => line.length > 0);
  expect(lines.length > 0, "No text-analysis events were captured");
  const events = lines.map(line => CloudEventSchema.parse(JSON.parse(line)));
  const sensitive = new Set([input.text, ...evidenceTexts].filter(value => value.length > 0));
  for (const event of events) {
    if (event.type.startsWith("text-analysis.service.")) {
      validateServiceData(event.data);
    } else if (event.type.startsWith("text-analysis.request.")) {
      validateRequestData(event.data);
    } else {
      fail("Captured event type is outside text analysis");
    }
    const values: string[] = [];
    collectStrings(event, values);
    expect(values.every(value => !sensitive.has(value)), "Event retained request or evidence text");
  }

  const serviceTypes = events
    .filter(event => event.type.startsWith("text-analysis.service."))
    .map(event => event.type);
  for (const expected of [
    "text-analysis.service.started",
    "text-analysis.service.ready",
    "text-analysis.service.stopped",
  ]) {
    expect(serviceTypes.filter(value => value === expected).length === 1, "Service lifecycle event is missing or duplicated");
  }
  expect(!serviceTypes.includes("text-analysis.service.failed"), "Service emitted a failure event");

  const requestEvents = events.filter(event => event.type.startsWith("text-analysis.request."));
  expect(requestEvents.length === expectedEvents.length, "Request event count is unexpected");
  for (const expected of expectedEvents) {
    const matching = requestEvents.filter(
      event => event.type === expected.type && event.traceparent === expected.traceparent,
    );
    expect(matching.length === 1, "Terminal request event is missing or duplicated");
    const data = validateRequestData(matching[0]!.data);
    expect(data.result_status === expected.result_status, "Request event result status is unexpected");
    expect(
      expected.error_code === undefined
        ? !Object.hasOwn(data, "error_code")
        : data.error_code === expected.error_code,
      "Request event error code is unexpected",
    );
    const statuses = array(data.feature_statuses, "Request feature statuses are invalid");
    expect(JSON.stringify(statuses) === JSON.stringify(expected.feature_statuses.map(item => ({
      feature: item.feature,
      status: item.status,
      error_code: item.error_code ?? null,
    }))), "Request event feature statuses are unexpected");
    if (expected.require_zero_model_load) {
      expect(data.model_load_ms === 0, "Warm repeated analysis reloaded the model");
    }
  }
  for (const traceparent of noEventTraceparents) {
    expect(!requestEvents.some(event => event.traceparent === traceparent), "Health or schema emitted a request event");
  }
  return {
    event_count: events.length,
    request_event_count: requestEvents.length,
    service_event_types: serviceTypes,
    zero_model_load_verified: expectedEvents.some(item => item.require_zero_model_load),
  };
}

async function main(): Promise<void> {
  const rawInput = await Bun.stdin.text();
  const parsed = record(JSON.parse(rawInput), "Probe input is invalid");
  if (parsed.mode === "exercise") {
    const language = text(parsed.language, "Probe language is invalid");
    const profile = text(parsed.profile, "Probe profile is invalid");
    const featureMode = text(parsed.feature_mode, "Probe feature mode is invalid");
    expect(language === "en" || language === "zh", "Probe language is invalid");
    expect(profile === "sm" || profile === "md" || profile === "lg", "Probe profile is invalid");
    expect(
      featureMode === "default" || featureMode === "all" || featureMode === "custom",
      "Probe feature mode is invalid",
    );
    const input: ExerciseInput = {
      mode: "exercise",
      base_url: text(parsed.base_url, "Probe base URL is invalid"),
      language,
      profile,
      feature_mode: featureMode,
      custom_features: text(parsed.custom_features, "Probe custom features are invalid"),
      text: text(parsed.text, "Probe text is invalid"),
    };
    process.stdout.write(JSON.stringify(await exercise(input)));
    return;
  }
  if (parsed.mode === "validate_events") {
    const input: ValidateEventsInput = {
      mode: "validate_events",
      events_path: text(parsed.events_path, "Event path is invalid"),
      text: text(parsed.text, "Event validation text is invalid"),
      exercise: record(parsed.exercise, "Exercise report is invalid"),
    };
    process.stdout.write(JSON.stringify(await validateEvents(input)));
    return;
  }
  fail("Probe mode is invalid");
}

try {
  await main();
} catch (error) {
  const message = error instanceof Error ? error.message : "Text-analysis probe failed";
  process.stderr.write(`${message}\n`);
  process.exitCode = 1;
}
