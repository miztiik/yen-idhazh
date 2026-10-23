/** Prove live feed and selected article HTTP operations without publishing private bodies. */
import { Database } from "bun:sqlite";
import { createHash, randomUUID } from "node:crypto";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { FetchedDocumentSchema, PlannerObservationSchema, RequestIdSchema } from "../../services/feed-ingest-plan/src/api/operation-contracts";
import { sha256 } from "../../services/feed-ingest-plan/src/api/operation-store";
import { servePlan } from "../../services/feed-ingest-plan/src/api/server";
import { ServiceSettingsSchema } from "../../services/feed-ingest-plan/src/config/service-settings";
import { resolveAddresses } from "../../services/feed-ingest-plan/src/harvest-feeds/safe-target";
import { networkTransport } from "../../services/feed-ingest-plan/src/harvest-feeds/transport";
import { canonicalizeUrl } from "../../services/feed-ingest-plan/src/harvest-feeds/url-cleaner";
import type { PlanInputs } from "../../services/feed-ingest-plan/src/load-plan-inputs";
import type { ProgressRecord } from "../../services/feed-ingest-plan/src/logging/progress-logger";
import type { PlanRuntime } from "../../services/feed-ingest-plan/src/run-feed-plan";
import type { summarizePlan } from "../../services/feed-ingest-plan/src/run-feed-plan";
import { ExtractionQualitySchema } from "../../packages/common-contracts/src/index";
import { EXTRACTOR_VERSION, SANITIZER_FINGERPRINT } from "../../services/feed-ingest-plan/src/harvest-feeds/extraction-provenance";
import { DispatchContract as nativeDispatchContract } from "../../services/feed-ingest-plan/src/metrics/audit-contracts";
import { readLedgerParquet } from "../../services/feed-ingest-plan/src/read-ledger-history/read-parquet";
import { verifyParquetFiles } from "./feed-ingest-plan-verification";

class ProofUnavailable extends Error {
  constructor(readonly reason: "NO_SUCCESSFUL_CONFIGURED_FEED" | "INVALID_PLANNING_COMPLETION"
    | "DISPATCH_MEMBERSHIP_MISMATCH" | "NO_READABLE_SELECTED_ARTICLE" | "HTML_EXTRACTION_UNAVAILABLE") {
    super(reason);
  }
}

function record(value: unknown): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) throw new Error("Expected an HTTP response object");
  return value as Record<string, unknown>;
}
function readFetchReceipt(value: unknown) {
  const { fetch_request_id, ...artifact } = record(value);
  if ("body" in artifact) throw new Error("HTTP fetch response contains a private body");
  const body_sha256 = FetchedDocumentSchema.shape.body_sha256.parse(artifact.body_sha256);
  // HTTP omits the body. Validate the shared public fields with absent body evidence, then retain its checked digest.
  const { body: _body, ...receipt } = FetchedDocumentSchema.parse({ ...artifact, body: null, body_sha256: null });
  return { ...receipt, body_sha256, fetch_request_id: RequestIdSchema.parse(fetch_request_id) };
}
function readParseReceipt(value: unknown, kind: "feed" | "article") {
  const receipt = record(value);
  const fields = ["fetch_request_id", "kind", "observation", "parsed", "failure"];
  if (Object.keys(receipt).some(key => !fields.includes(key))
    || (kind === "feed" && receipt.parsed !== null && !Array.isArray(receipt.parsed))
    || (receipt.failure !== null && !["malformed-feed", "missing-document-root", "dom-depth-exceeded"].includes(String(receipt.failure)))
    || receipt.kind !== kind) throw new Error("Invalid document parse response");
  return {
    fetch_request_id: RequestIdSchema.parse(receipt.fetch_request_id),
    observation: PlannerObservationSchema.parse(receipt.observation),
    parsed: receipt.parsed, failure: receipt.failure,
  };
}
export function redactProofResponse(endpoint: "fetch" | "parse", kind: "feed" | "article", bytes: Uint8Array, status: number) {
  const text = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  const value: unknown = JSON.parse(text);
  const response_sha256 = createHash("sha256").update(bytes).digest("hex");
  if (status !== 200) {
    const error = record(value);
    return { response_sha256, response_json: null, response_metadata: {
      code: error.code === "REQUEST_CONFLICT" ? "REQUEST_CONFLICT" : "HTTP_FAILURE",
    } };
  }
  if (endpoint === "fetch") {
    const receipt = readFetchReceipt(value);
    if (receipt.kind !== kind) throw new Error("Fetch document kind differs");
    return { response_sha256, response_json: kind === "feed" ? text : null, response_metadata: receipt };
  }
  const receipt = readParseReceipt(value, kind);
  if (kind === "feed") return { response_sha256, response_json: text, response_metadata: null };
  const parsed = receipt.parsed === null ? null : record(receipt.parsed);
  let metadata = null;
  if (parsed !== null) {
    if (typeof parsed.article_text !== "string" || !Number.isSafeInteger(parsed.word_count)
      || typeof parsed.word_count !== "number" || parsed.word_count < 0
      || typeof parsed.paywall !== "boolean"
      || !["none", "json-ld", "configured-marker"].includes(String(parsed.paywall_evidence))
      || !Array.isArray(parsed.warnings) || parsed.warnings.some(warning => warning !== "malformed-json-ld")) {
      throw new Error("Invalid article extraction metadata");
    }
    const quality = parsed.quality === null ? null : ExtractionQualitySchema.parse(parsed.quality);
    if (quality !== null && (quality.word_count !== parsed.word_count || quality.source_word_count !== parsed.word_count
      || quality.extractor_version !== EXTRACTOR_VERSION || quality.sanitizer_version !== SANITIZER_FINGERPRINT
      || quality.token_count !== null || quality.truncated !== null || quality.truncated_at_tokens !== null)) {
      throw new Error("Article extraction quality or provenance differs");
    }
    metadata = {
      word_count: parsed.word_count, article_text_sha256: sha256(parsed.article_text),
      article_text_length: parsed.article_text.length, paywall: parsed.paywall,
      paywall_evidence: parsed.paywall_evidence, warnings: parsed.warnings, quality,
    };
  }
  return { response_sha256, response_json: null, response_metadata: {
    fetch_request_id: receipt.fetch_request_id, observation: receipt.observation,
    kind, failure: receipt.failure, parsed: metadata,
  } };
}
export function requireExactReplay(original: Uint8Array, replay: Uint8Array) {
  if (!Buffer.from(original).equals(replay)) throw new Error("Restart replay changed exact private response bytes");
}
export function requireReadableArticle(value: unknown) {
  const article = record(value);
  if (typeof article.paywall !== "boolean" || typeof article.article_text !== "string") {
    throw new Error("Invalid article extraction metadata");
  }
  const quality = article.quality === null ? null : ExtractionQualitySchema.parse(article.quality);
  if (article.paywall || !article.article_text.trim() || quality === null || quality.rejected || quality.word_count === 0) {
    throw new ProofUnavailable("HTML_EXTRACTION_UNAVAILABLE");
  }
}

export async function selectVerifiedArticle(inputs: PlanInputs, summary: ReturnType<typeof summarizePlan>, stateRoot: string) {
  if (!summary.planning_complete || summary.planning_completion?.status !== "complete"
    || summary.planning_completion.run_id !== summary.run_id
    || summary.planning_completion.correlation_id !== summary.correlation_id) {
    throw new ProofUnavailable("INVALID_PLANNING_COMPLETION");
  }
  const verified = await verifyParquetFiles(stateRoot, "dispatches", summary.files.dispatches, inputs.registrations.dispatches);
  const candidates = new Set(summary.selected_candidate_ids);
  if (candidates.size !== summary.selected_candidate_ids.length || verified.row_count !== candidates.size) {
    throw new ProofUnavailable("DISPATCH_MEMBERSHIP_MISMATCH");
  }
  let selected: null | {
    source_id: string; canonical_url: string; article_id: string;
    selection: { candidate_id: string; run_id: string; correlation_id: string; file_id: string; content_sha256: string };
  } = null;
  for (const file of summary.files.dispatches.files) {
    const native = await readLedgerParquet(join(stateRoot, ...file.path.split("/")), "dispatches", nativeDispatchContract);
    for (const { row: dispatch, identity } of native.rows) {
      const { content, selection } = dispatch;
      if (content.run_id !== summary.run_id || identity.run_id !== summary.run_id
        || identity.attempt !== summary.planning_completion.attempt
        || content.correlation_id !== summary.correlation_id || selection.correlation_id !== summary.correlation_id
        || content.date !== summary.date || selection.date !== summary.date
        || !candidates.delete(content.candidate_id)) throw new ProofUnavailable("DISPATCH_MEMBERSHIP_MISMATCH");
      const source = inputs.harvest.sources.find(source => source.id === content.source_id && source.status === "active");
      if (selected === null && source && content.word_count > 0 && content.article_text.trim()) {
        selected = {
          source_id: source.id, canonical_url: content.canonical_url, article_id: content.url_key,
          selection: { candidate_id: content.candidate_id, run_id: content.run_id,
            correlation_id: content.correlation_id, file_id: file.file_id, content_sha256: file.content_sha256 },
        };
      }
    }
  }
  if (selected === null || candidates.size !== 0) throw new ProofUnavailable("NO_READABLE_SELECTED_ARTICLE");
  return selected;
}
type Call = {
  stage: string; endpoint: "fetch" | "parse"; request: Record<string, string>;
  http_status: number; response_json: string | null; response_sha256: string;
  response_metadata: unknown;
  network: { dns: number; http: number };
};

export async function verifyLiveDocumentHttp(
  inputs: PlanInputs, runtime: PlanRuntime, progress: readonly ProgressRecord[],
  runnerTemp: string, artifactRoot: string, summary: ReturnType<typeof summarizePlan>,
) {
  const evidence = {
    scope: "live_configured_feed_and_selected_article", status: "running", stage: "select_source",
    git_sha: runtime.git_sha, documents: [] as object[], error: null as string | null, reason: null as string | null,
  };
  const persist = () => writeFile(join(artifactRoot, "stage-api-proof.json"), JSON.stringify(evidence));
  await persist();
  try {
    const completed = progress.find(event => event.eventType === "FEED_FETCH_COMPLETED"
      && event.correlationId === summary.correlation_id
      && event.fetch_status === "success" && event.parse_status === "success"
      && inputs.harvest.sources.some(source => source.id === event.source_id && source.status === "active"));
    const source = inputs.harvest.sources.find(source => source.id === completed?.source_id);
    if (!source) throw new ProofUnavailable("NO_SUCCESSFUL_CONFIGURED_FEED");
    await verifyTarget({ kind: "feed", source_id: source.id, ...canonicalizeUrl(source.url), selection: null });
    evidence.stage = "select_verified_article";
    await persist();
    const article = await selectVerifiedArticle(inputs, summary, join(artifactRoot, "state"));
    await verifyTarget({ kind: "article", ...article, url_key: article.article_id });
    evidence.status = "complete";
    evidence.stage = "complete";
  } catch (error) {
    evidence.status = "failed";
    evidence.reason = error instanceof ProofUnavailable ? error.reason : "PROOF_CHECK_FAILED";
    evidence.error = `Stage ${evidence.stage} failed; HTML verification is not complete unless its document proof is complete`;
    throw new Error(evidence.error);
  } finally { await persist(); }

  async function verifyTarget(target: {
    kind: "feed" | "article"; source_id: string; canonical_url: string; url_key: string;
    selection: Awaited<ReturnType<typeof selectVerifiedArticle>>["selection"] | null;
  }) {
    const proof = {
      kind: target.kind, status: "running", stage: "create_private_directory",
      git_sha: runtime.git_sha, source_id: null as string | null,
      article_id: null as string | null, run_id: summary.run_id,
      correlation_id: summary.correlation_id, calls: [] as Call[],
      pending_request: null as null | Pick<Call, "stage" | "endpoint" | "request">,
      journal_records_sha256: null as null | { before_restart: string; after_checks: string },
      selection: target.selection, reason: null as string | null,
      error: null as string | null,
    };
    evidence.documents.push(proof);
    const persist = () => {
      evidence.stage = `${target.kind}:${proof.stage}`;
      return writeFile(join(artifactRoot, "stage-api-proof.json"), JSON.stringify(evidence));
    };
    let privateRoot: string | undefined;
    let server: ReturnType<typeof servePlan> | undefined;
    try {
      const source = inputs.harvest.sources.find(source => source.id === target.source_id && source.status === "active");
      if (!source) throw new Error("Active configured source is unavailable");
      proof.source_id = source.id;
      proof.article_id = target.url_key;
      proof.stage = "create_private_directory";
      await persist();
      // This sibling directory is outside the workflow's only artifact upload root.
      const outputRoot = await mkdtemp(join(runnerTemp, "feed-stage-api-private-"));
      privateRoot = outputRoot;
      const counts = { dns: 0, http: 0 };
      const apiInputs = { ...inputs, outputRoot };
      const apiRuntime: PlanRuntime = {
        ...runtime,
        boundary: {
          resolve: hostname => { counts.dns++; return resolveAddresses(hostname); },
          transport: { request: request => { counts.http++; return networkTransport.request(request); } },
        },
      };
      const fetchRequest = {
        request_id: randomUUID(), correlation_id: proof.correlation_id, source_id: source.id, kind: target.kind,
        ...(target.kind === "article" ? { url: target.canonical_url } : {}),
      };
      async function post(stage: string, endpoint: Call["endpoint"], request: Record<string, string>) {
        proof.stage = stage;
        proof.pending_request = { stage, endpoint, request };
        await persist();
        if (!server) throw new Error("Actual HTTP listener is not running");
        const before = { ...counts };
        const response = await fetch(new URL(`/api/2026-10-20/${endpoint}`, server.url), {
          method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(request),
          // The enclosing workflow deadline supervises the configured operation budget.
          timeout: false,
        });
        const response_bytes = Buffer.from(await response.arrayBuffer());
        const call: Call = {
          stage, endpoint, request, http_status: response.status, response_json: null, response_metadata: null,
          response_sha256: createHash("sha256").update(response_bytes).digest("hex"),
          network: { dns: counts.dns - before.dns, http: counts.http - before.http },
        };
        try {
          Object.assign(call, redactProofResponse(endpoint, target.kind, response_bytes, response.status));
        } catch (error) {
          proof.calls.push({ ...call, response_json: null });
          await persist();
          throw error;
        }
        proof.calls.push(call);
        proof.pending_request = null;
        await persist();
        // Full bytes never enter the object serialized by persist().
        return { ...call, private_response_bytes: response_bytes };
      }
      function requireStatus(call: Call, expected: number) {
        if (call.http_status !== expected) throw new Error(`${call.stage}: expected HTTP ${expected}, got ${call.http_status}`);
      }
      function requireOffline(call: Call) {
        if (call.network.dns !== 0 || call.network.http !== 0) throw new Error(`${call.stage}: unexpected outbound network work`);
      }
      function requireIdentity(observation: ReturnType<typeof PlannerObservationSchema.parse>, operation: "fetch" | "parse") {
        if (observation.article_id !== proof.article_id || observation.source_id !== source!.id
          || observation.correlation_id !== proof.correlation_id || observation.operation !== operation
          || observation.run_id !== proof.run_id) throw new Error(`${operation}: document identity differs`);
      }
      function journalDigest(parseRequestId: string) {
        const database = new Database(join(outputRoot, "planner-operations.sqlite"), { readonly: true });
        try {
          const rows = database.query<{ request_id: string; record: string }, [string, string]>(
            "SELECT request_id, record FROM operations WHERE request_id IN (?, ?) ORDER BY request_id",
          ).all(fetchRequest.request_id, parseRequestId);
          if (rows.length !== 2) throw new Error("Expected both completed operation receipts");
          return sha256(JSON.stringify(rows));
        } finally { database.close(); }
      }
      proof.stage = "start_listener";
      await persist();
      server = servePlan(apiInputs, apiRuntime);
      const fetched = await post("fetch", "fetch", fetchRequest);
      requireStatus(fetched, 200);
      const receipt = readFetchReceipt(JSON.parse(fetched.private_response_bytes.toString("utf8")));
      requireIdentity(receipt.observation, "fetch");
      if (receipt.fetch_request_id !== fetchRequest.request_id || receipt.kind !== target.kind
        || receipt.article_id !== proof.article_id || receipt.canonical_url !== target.canonical_url
        || receipt.failure !== null || receipt.body_sha256 === null || fetched.network.http === 0
        || receipt.observation.caused_by_event_id !== null) throw new Error("Fetch did not supply successful live document evidence");
      if (receipt.attempts.length === 0 || receipt.attempts.length !== receipt.attempt_observations.length) {
        throw new Error("Fetch attempt evidence is absent or mismatched");
      }
      const eventIds = new Set([receipt.observation.event_id]);
      for (const observation of receipt.attempt_observations) {
        if (observation.operation !== "attempt" || observation.caused_by_event_id !== receipt.observation.event_id
          || observation.article_id !== proof.article_id || observation.source_id !== source.id
          || observation.run_id !== proof.run_id || observation.correlation_id !== proof.correlation_id
          || eventIds.has(observation.event_id)) throw new Error("Fetch attempt identity or cause differs");
        eventIds.add(observation.event_id);
      }
      const parseRequest = {
        request_id: randomUUID(), fetch_request_id: receipt.fetch_request_id,
        article_id: receipt.article_id, correlation_id: proof.correlation_id,
      };
      const parsed = await post("parse", "parse", parseRequest);
      requireStatus(parsed, 200);
      requireOffline(parsed);
      const result = readParseReceipt(JSON.parse(parsed.private_response_bytes.toString("utf8")), target.kind);
      requireIdentity(result.observation, "parse");
      if (result.fetch_request_id !== receipt.fetch_request_id || result.failure !== null || result.parsed === null
        || result.observation.caused_by_event_id !== receipt.observation.event_id
        || eventIds.has(result.observation.event_id)) throw new Error("Parse result or causal identity differs");
      if (target.kind === "article") {
        requireReadableArticle(result.parsed);
      }
      const beforeRestart = journalDigest(parseRequest.request_id);
      proof.stage = "restart";
      await persist();
      await server.stop(true);
      server = undefined;
      server = servePlan(apiInputs, apiRuntime);
      for (const [endpoint, request, original] of [
        ["fetch", fetchRequest, fetched], ["parse", parseRequest, parsed],
      ] as const) {
        const replay = await post(`${endpoint}_replay_after_restart`, endpoint, request);
        requireStatus(replay, original.http_status);
        requireOffline(replay);
        requireExactReplay(original.private_response_bytes, replay.private_response_bytes);
      }
      for (const [stage, endpoint, request] of [
        ["changed_input_conflict", "fetch", { ...fetchRequest, correlation_id: randomUUID() }],
        ["changed_operation_conflict", "parse", { ...parseRequest, request_id: fetchRequest.request_id }],
      ] as const) {
        const conflict = await post(stage, endpoint, request);
        requireStatus(conflict, 409);
        requireOffline(conflict);
        if (JSON.parse(conflict.private_response_bytes.toString("utf8")).code !== "REQUEST_CONFLICT") throw new Error(`${stage}: wrong refusal`);
      }
      proof.stage = "restart_with_changed_config";
      await persist();
      await server.stop(true);
      server = undefined;
      const changedInputs = {
        ...apiInputs, settings: ServiceSettingsSchema.parse({
          ...inputs.settings, run: { ...inputs.settings.run, attempt: inputs.settings.run.attempt + 1 },
        }),
      };
      server = servePlan(changedInputs, apiRuntime);
      const conflict = await post("changed_config_conflict", "fetch", fetchRequest);
      requireStatus(conflict, 409);
      requireOffline(conflict);
      if (JSON.parse(conflict.private_response_bytes.toString("utf8")).code !== "REQUEST_CONFLICT") throw new Error("Changed configuration: wrong refusal");
      const afterChecks = journalDigest(parseRequest.request_id);
      proof.journal_records_sha256 = { before_restart: beforeRestart, after_checks: afterChecks };
      if (beforeRestart !== afterChecks) throw new Error("Replay or refusal changed completed journal records");
      proof.stage = "stop_listener";
      await server.stop(true);
      server = undefined;
      proof.stage = "complete";
      proof.status = "complete";
    } catch (error) {
      proof.status = "failed";
      proof.reason = error instanceof ProofUnavailable ? error.reason : "PROOF_CHECK_FAILED";
      // Do not serialize arbitrary exception messages, fetched bodies or private paths.
      proof.error = `Stage ${proof.stage} failed; inspect its recorded HTTP status and body-free response`;
      if (error instanceof ProofUnavailable) throw error;
      throw new Error(proof.error);
    } finally {
      let cleanupStage = "stop_listener";
      try {
        if (server) await server.stop(true);
        cleanupStage = "remove_private_directory";
        // Every operation closes its database before responding; stop the listener before removing this one private root.
        if (privateRoot) await rm(privateRoot, { recursive: true, force: true });
      } catch {
        proof.status = "failed";
        proof.stage = cleanupStage;
        proof.reason = "PRIVATE_CLEANUP_FAILED";
        proof.error = `Stage ${cleanupStage} failed; the private directory remains outside uploaded evidence`;
        throw new Error(proof.error);
      } finally { await persist(); }
    }
  }
}
