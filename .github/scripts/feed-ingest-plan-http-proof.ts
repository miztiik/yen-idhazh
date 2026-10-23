/** Prove separate live feed fetch, parse and durable replay without publishing the private journal. */
import { Database } from "bun:sqlite";
import { randomUUID } from "node:crypto";
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
function readParseReceipt(value: unknown) {
  const receipt = record(value);
  const fields = ["fetch_request_id", "kind", "observation", "parsed", "failure"];
  if (Object.keys(receipt).some(key => !fields.includes(key)) || receipt.kind !== "feed"
    || (receipt.parsed !== null && !Array.isArray(receipt.parsed))
    || (receipt.failure !== null && typeof receipt.failure !== "string")) throw new Error("Invalid feed parse response");
  return {
    fetch_request_id: RequestIdSchema.parse(receipt.fetch_request_id),
    observation: PlannerObservationSchema.parse(receipt.observation),
    parsed: receipt.parsed, failure: receipt.failure,
  };
}
type Call = {
  stage: string; endpoint: "fetch" | "parse"; request: Record<string, string>;
  http_status: number; response_json: string | null; response_sha256: string;
  network: { dns: number; http: number };
};

export async function verifyLiveDocumentHttp(
  inputs: PlanInputs, runtime: PlanRuntime, progress: readonly ProgressRecord[],
  runnerTemp: string, artifactRoot: string,
) {
  const proof = {
    scope: "live_configured_feed", status: "running", stage: "select_source",
    git_sha: runtime.git_sha, source_id: null as string | null,
    article_id: null as string | null, run_id: null as string | null,
    correlation_id: randomUUID(), calls: [] as Call[],
    pending_request: null as null | Pick<Call, "stage" | "endpoint" | "request">,
    journal_records_sha256: null as null | { before_restart: string; after_checks: string },
    error: null as string | null,
  };
  const persist = () => writeFile(join(artifactRoot, "stage-api-proof.json"), JSON.stringify(proof));
  await persist();
  let privateRoot: string | undefined;
  let server: ReturnType<typeof servePlan> | undefined;
  try {
    const completed = progress.find(event => event.eventType === "FEED_FETCH_COMPLETED"
      && event.fetch_status === "success" && event.parse_status === "success"
      && inputs.harvest.sources.some(source => source.id === event.source_id && source.status === "active"));
    const source = inputs.harvest.sources.find(source => source.id === completed?.source_id);
    if (!source) throw new Error("No active configured feed successfully fetched and parsed in the actual plan");
    proof.source_id = source.id;
    proof.article_id = canonicalizeUrl(source.url).url_key;
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
      request_id: randomUUID(), correlation_id: proof.correlation_id, source_id: source.id, kind: "feed",
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
      const response_json = await response.text();
      const call = {
        stage, endpoint, request, http_status: response.status, response_json,
        response_sha256: sha256(response_json),
        network: { dns: counts.dns - before.dns, http: counts.http - before.http },
      };
      try {
        const value: unknown = JSON.parse(response_json);
        // Refuse unexpected private fields before they can enter the public artifact.
        if (response.status === 200) {
          if (endpoint === "fetch") readFetchReceipt(value);
          else readParseReceipt(value);
        } else {
          const error = record(value);
          if (Object.keys(error).some(key => !["code", "issues"].includes(key))
            || typeof error.code !== "string" || !Array.isArray(error.issues)) throw new Error("Unexpected error response");
          for (const issue of error.issues) {
            const fields = record(issue);
            if (Object.keys(fields).some(key => !["field", "message"].includes(key))
              || (fields.field !== null && typeof fields.field !== "string")
              || typeof fields.message !== "string") throw new Error("Unexpected error issue");
          }
        }
      } catch (error) {
        proof.calls.push({ ...call, response_json: null });
        await persist();
        throw error;
      }
      proof.calls.push(call);
      proof.pending_request = null;
      await persist();
      return call;
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
    const receipt = readFetchReceipt(JSON.parse(fetched.response_json));
    proof.run_id = receipt.observation.run_id;
    requireIdentity(receipt.observation, "fetch");
    if (receipt.fetch_request_id !== fetchRequest.request_id || receipt.kind !== "feed"
      || receipt.article_id !== proof.article_id || receipt.canonical_url !== canonicalizeUrl(source.url).canonical_url
      || receipt.failure !== null || receipt.body_sha256 === null || fetched.network.http === 0
      || receipt.observation.caused_by_event_id !== null) throw new Error("Fetch did not supply successful live feed evidence");
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
    const result = readParseReceipt(JSON.parse(parsed.response_json));
    requireIdentity(result.observation, "parse");
    if (result.fetch_request_id !== receipt.fetch_request_id || result.failure !== null || result.parsed === null
      || result.observation.caused_by_event_id !== receipt.observation.event_id
      || eventIds.has(result.observation.event_id)) throw new Error("Parse result or causal identity differs");
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
      if (replay.response_json !== original.response_json) throw new Error(`${endpoint}: restart replay changed exact response bytes`);
    }
    for (const [stage, endpoint, request] of [
      ["changed_input_conflict", "fetch", { ...fetchRequest, correlation_id: randomUUID() }],
      ["changed_operation_conflict", "parse", { ...parseRequest, request_id: fetchRequest.request_id }],
    ] as const) {
      const conflict = await post(stage, endpoint, request);
      requireStatus(conflict, 409);
      requireOffline(conflict);
      if (JSON.parse(conflict.response_json).code !== "REQUEST_CONFLICT") throw new Error(`${stage}: wrong refusal`);
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
    if (JSON.parse(conflict.response_json).code !== "REQUEST_CONFLICT") throw new Error("Changed configuration: wrong refusal");
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
    // Do not serialize arbitrary exception messages, fetched bodies or private paths.
    proof.error = `Stage ${proof.stage} failed; inspect its recorded HTTP status and body-free response`;
    throw error;
  } finally {
    let cleanupStage = "stop_listener";
    try {
      if (server) await server.stop(true);
      cleanupStage = "remove_private_directory";
      // Every operation closes its database before responding; stop the listener before removing this one private root.
      if (privateRoot) await rm(privateRoot, { recursive: true, force: true });
    } catch (error) {
      proof.status = "failed";
      proof.stage = cleanupStage;
      proof.error = `Stage ${cleanupStage} failed; the private directory remains outside uploaded evidence`;
      throw error;
    } finally { await persist(); }
  }
}
