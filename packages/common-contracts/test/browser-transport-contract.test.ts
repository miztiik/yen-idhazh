/** Do current browser source evidence and retained historical measurements share one contract? */
import { expect, test } from "bun:test";
import { z } from "zod";
import {
  BodyLimitEvidenceSchema, DocumentWorkFactSchema, FEED_INGEST_CONFIG_VERSION,
  FEED_INGEST_EVENT_VERSION, FEED_OUTCOME_PAYLOAD_VERSION, FEED_PROBE_VERSION,
  FeedBrowserConfigSchema, FeedIngestConfigSchema, FeedProbeResultSchema,
  FeedProbeRequestSchema, FeedProbeArticleSampleSchema, FeedOutcomePayloadSchema,
  FeedRequestHeadersSchema, FetchAttemptSchema, FetchFailureSchema,
  ArticleFetchEvidenceSchema, HARVEST_DIAGNOSTICS_VERSION, HarvestDiagnosticsSchema,
  HttpResponseEvidenceSchema,
  HTTP_RESPONSE_EVIDENCE_VERSION, OPERATION_VERSION, ParsedFeedBatchSchema,
  PARSED_FEED_BATCH_VERSION, PlannerHarvestObservationSchema, RequestProfileSchema,
} from "../src";

const day = "2026-11-02";
const at = `${day}T12:00:00Z`;
const digest = "a".repeat(64);

test("browser config replaces fingerprint profiles with defaults and flat allowlisted headers", async () => {
  expect(FEED_INGEST_CONFIG_VERSION).toBe(day);
  expect(FeedBrowserConfigSchema.parse({})).toEqual({
    headless: true,
    document_timeout_ms: 30000,
    challenge_selectors: ["#challenge-form", "#challenge-running", "#cf-challenge-running"],
  });
  expect(FeedRequestHeadersSchema.parse(undefined)).toEqual({});
  expect(FeedRequestHeadersSchema.parse({ accept: "application/xml" })).toEqual({ accept: "application/xml" });

  const config = await Bun.file(new URL("../../../config/feed-ingest-plan.json", import.meta.url)).json();
  expect(FeedIngestConfigSchema.parse(config).harvest.request_headers).toEqual({});
  expect(FeedIngestConfigSchema.safeParse({
    ...config,
    harvest: {
      ...config.harvest,
      request_headers: {
        primary: { browser: "firefox", headers: {} },
        secondary: { browser: "chrome", headers: {} },
        recoverable_http_statuses: [403],
        recovery_min_body_bytes: 200,
      },
    },
  }).success).toBe(false);
});

test("response evidence accepts Chromium writes and old browser labels without changing byte meaning", () => {
  expect(RequestProfileSchema.parse("chromium")).toBe("chromium");
  for (const request_profile of ["firefox", "chrome"] as const) {
    expect(RequestProfileSchema.parse(request_profile)).toBe(request_profile);
  }
  const evidence = HttpResponseEvidenceSchema.parse({
    content_type: "text/html", decoded_bytes: null, declared_content_length: null,
    selected_headers: {}, headers_truncated: [], request_profile: "chromium",
  });
  expect(evidence.decoded_bytes).toBeNull();
  expect(HTTP_RESPONSE_EVIDENCE_VERSION).toBe(day);
  expect(z.toJSONSchema(HttpResponseEvidenceSchema).version).toBe(day);
});

test("body limit stage defaults historical evidence and supports completed and parser measurements", () => {
  const historical = BodyLimitEvidenceSchema.parse({
    configured_limit_bytes: 100, observed_at_least_bytes: 101,
  });
  expect(historical.limit_stage).toBe("decoded-stream");
  for (const limit_stage of ["decoded-stream", "completed-response", "parser-input"] as const) {
    expect(BodyLimitEvidenceSchema.parse({
      configured_limit_bytes: 100, observed_at_least_bytes: 101, limit_stage,
    }).limit_stage).toBe(limit_stage);
  }
  expect(BodyLimitEvidenceSchema.safeParse({
    configured_limit_bytes: 100, observed_at_least_bytes: 101, limit_stage: "transfer-aborted",
  }).success).toBe(false);
  expect(HARVEST_DIAGNOSTICS_VERSION).toBe(day);
  expect(z.toJSONSchema(HarvestDiagnosticsSchema).version).toBe(day);
});

test("challenge failures share one enum through diagnostics, stage observations and probe results", () => {
  expect(FetchFailureSchema.parse("challenge-unresolved")).toBe("challenge-unresolved");
  expect(HarvestDiagnosticsSchema.parse({
    http_status: 200, fetch_failure: "challenge-unresolved",
    failure_code: "unknown", detail: "challenge-unresolved",
  }).detail).toBe("challenge-unresolved");
  expect(ArticleFetchEvidenceSchema.parse({
    http_status: 200, fetch_failure: "challenge-unresolved",
  }).fetch_failure).toBe("challenge-unresolved");
  const observation = PlannerHarvestObservationSchema.parse({
    candidate_id: digest, http_status: 200, robots: "allowed",
    fetch_failure: "challenge-unresolved", paywall: null,
    paywall_evidence: "not-observed", extraction: "not-attempted", observed_at: at,
    diagnostics: { http_status: 200, fetch_failure: "challenge-unresolved", detail: "challenge-unresolved" },
  });
  expect(observation.fetch_failure).toBe("challenge-unresolved");
  expect(FeedProbeResultSchema.parse({
    verdict: "feed_failure", passed: false, paywall_confirmed: false,
    sample_count: 0, readable_count: 0, paywall_sample_count: 0,
    paywall_evidence: "none", failure_code: "unknown",
    diagnostics: { http_status: 200, fetch_failure: "challenge-unresolved", detail: "challenge-unresolved" },
  }).diagnostics?.detail).toBe("challenge-unresolved");

  const outcome = FeedOutcomePayloadSchema.parse({
    kind: "feed_outcome",
    source: {
      feed_id: "example", feed_url: "https://example.org/feed", title: "Example",
      tier: 1, status: "active", weight: 1, applied_tier_weight: 1,
    },
    fetch_status: "network_failure", parse_status: "failure",
    parsed_count: null, harvested_count: null, fetch_duration_ms: 0,
    parse_duration_ms: null, rejection_reason: "challenge-unresolved",
    diagnostics: { http_status: 200, fetch_failure: "challenge-unresolved", detail: "challenge-unresolved" },
  });
  expect(outcome.version).toBe(FEED_OUTCOME_PAYLOAD_VERSION);
  expect(outcome.diagnostics?.http_status).toBe(200);
});

test("attempt and work facts carry nullable document or resource roles", () => {
  const commonAttempt = {
    phase: "target" as const, sequence: 0, retry: 0, duration_ms: 0,
    http_status: 200, failure: "challenge-unresolved" as const, error_code: null,
  };
  expect(FetchAttemptSchema.parse(commonAttempt).request_role).toBeNull();
  for (const request_role of ["document", "resource"] as const) {
    expect(FetchAttemptSchema.parse({ ...commonAttempt, request_role }).request_role).toBe(request_role);
  }
  expect(FetchAttemptSchema.safeParse({ ...commonAttempt, request_role: "robots" }).success).toBe(false);
  const fact = {
    run_id: `${day}-1`, attempt: 1, feed_id: "example",
    document_kind: "article" as const, operation: "attempt" as const,
    outcome: "failed" as const, occurred_at: at, duration_ms: 0, http_status: 200,
    attribution: "unresolved" as const, failure_code: "challenge-unresolved" as const,
    request_phase: "target" as const, dispatched_request_count: 1,
    request_coverage: "complete" as const,
  };
  expect(DocumentWorkFactSchema.parse(fact).request_role).toBeNull();
  expect(DocumentWorkFactSchema.parse({ ...fact, request_role: "resource" }).request_role).toBe("resource");
});

test("operation, event, probe and stage wrappers use the browser contract stamps", () => {
  expect(OPERATION_VERSION).toBe(day);
  expect(FEED_INGEST_EVENT_VERSION).toBe(day);
  expect(FEED_OUTCOME_PAYLOAD_VERSION).toBe(day);
  expect(FEED_PROBE_VERSION).toBe(day);
  expect(PARSED_FEED_BATCH_VERSION).toBe(day);
  expect(z.toJSONSchema(FeedProbeRequestSchema).version).toBe(day);
  expect(z.toJSONSchema(FeedProbeArticleSampleSchema).version).toBe(day);
  expect(z.toJSONSchema(FeedProbeResultSchema).version).toBe(day);
  expect(ParsedFeedBatchSchema.meta()?.version).toBe(day);
  const stageJsonSchema = z.toJSONSchema(ParsedFeedBatchSchema);
  expect(stageJsonSchema.version).toBe(day);
  expect((stageJsonSchema.changelog as { version: string }[])[0]?.version).toBe(day);
});
