/** Execute fetch and parse requests against identity-checked durable documents. */
import { z } from "zod";
import { WriterIdentitySchema } from "@idhazh/common-contracts";
import type { PlanInputs } from "../load-plan-inputs";
import type { PlanRuntime } from "../run-feed-plan";
import { resolveRunContext } from "../resolve-run-context";
import { createPermittedFetcher } from "../harvest-feeds/robots-policy";
import { canonicalizeUrl } from "../harvest-feeds/url-cleaner";
import { validateTargetName } from "../harvest-feeds/safe-target";
import { parseDocument } from "../harvest-feeds/parse-document";
import { documentWork, describeArticleParse, describeFeedParse } from "../harvest-feeds/document-work";
import { createIngestObservations } from "../ingest-observations";
import type { IngestObservations } from "../ingest-observations";
import { PlanError } from "./plan-request";
import { FetchRequestSchema, FetchedDocumentSchema, ParseRequestSchema, PlannerOperationSchema } from "./operation-contracts";
import type { FetchedDocument, PlannerOperation } from "./operation-contracts";
import { openOperationStore, sha256 } from "./operation-store";
import type { PreparedOperation } from "./operation-store";
import { profileTask } from "../../../host-probes/src/task-profile/task-profiler";

export function operationConfigFingerprint(inputs: PlanInputs, runtime: PlanRuntime) {
  return sha256(JSON.stringify({
    harvest: inputs.harvest.config_sha256, settings: inputs.settings, clock: inputs.clock_config,
    ledger: inputs.ledgerSettings, registrations: inputs.registrations, git_sha: runtime.git_sha,
  }));
}
export function proposedOperation(
  operation: PlannerOperation["operation"], request_id: string, request: unknown,
  correlation_id: string, inputs: PlanInputs, runtime: PlanRuntime,
) {
  const now = runtime.clock?.() ?? new Date();
  const context = resolveRunContext(inputs.settings, runtime.git_sha, now,
    runtime.run_number ?? BigInt(`0x${correlation_id.replaceAll("-", "")}`).toString(), correlation_id, runtime.captured_at);
  return PlannerOperationSchema.parse({
    request_id, operation, input_sha256: sha256(JSON.stringify(request)),
    config_sha256: operationConfigFingerprint(inputs, runtime), run_id: context.run_id,
    correlation_id, created_at: context.captured_at, state: "started", response_json: null, artifact: null,
  });
}

export function prepareOperation(
  operation: PlannerOperation["operation"], request_id: string, request: unknown,
  correlation_id: string, inputs: PlanInputs, runtime: PlanRuntime, runId?: string,
): PreparedOperation {
  return {
    request_id, operation, input_sha256: sha256(JSON.stringify(request)),
    config_sha256: operationConfigFingerprint(inputs, runtime),
    capture: () => {
      const record = proposedOperation(operation, request_id, request, correlation_id, inputs, runtime);
      return runId === undefined ? record : { ...record, run_id: runId };
    },
  };
}
function checkArtifact(record: PlannerOperation, inputs: PlanInputs): FetchedDocument {
  const artifact = FetchedDocumentSchema.parse(record.artifact);
  const identity = canonicalizeUrl(artifact.canonical_url);
  if (record.operation !== "fetch" || record.state !== "complete"
    || artifact.article_id !== identity.url_key || artifact.canonical_url !== identity.canonical_url
    || artifact.observation.article_id !== artifact.article_id
    || artifact.observation.source_id !== artifact.source_id
    || artifact.observation.correlation_id !== record.correlation_id || artifact.observation.run_id !== record.run_id
    || artifact.body_sha256 !== (artifact.body === null ? null : sha256(artifact.body))
    || (artifact.body !== null && Buffer.byteLength(artifact.body, "utf8") > inputs.harvest.extraction.max_body_bytes)) {
    throw new PlanError("ARTIFACT_INVALID", "Fetched document identity, body digest or bounds differ from its receipt", "fetch_request_id");
  }
  return artifact;
}
export async function executeDocumentOperation(
  operation: "fetch" | "parse", raw: unknown, inputs: PlanInputs, runtime: PlanRuntime, signal?: AbortSignal,
) {
  const request = operation === "fetch" ? FetchRequestSchema.parse(raw) : ParseRequestSchema.parse(raw);
  if (!inputs.settings.enabled) throw new PlanError("PLANNER_DISABLED", "Planner is disabled by service settings", "enabled");
  const store = await openOperationStore(inputs.outputRoot);
  let observations: IngestObservations | undefined;
  try {
    let runId: string | undefined;
    if ("fetch_request_id" in request) {
      const fetched = store.get(request.fetch_request_id);
      if (fetched !== null) runId = fetched.run_id;
    }
    const proposed = prepareOperation(operation, request.request_id, request, request.correlation_id, inputs, runtime, runId);
    const completed = await store.execute(proposed, async record => {
      observations = createIngestObservations({
        writer: WriterIdentitySchema.parse({
          run_id: record.run_id, attempt: inputs.settings.run.attempt, job: null,
          pipeline_name: "feed-ingest-plan", task_name: operation, shard: 0,
          producer: inputs.settings.run.producer, git_sha: runtime.git_sha,
        }),
        outputRoot: inputs.outputRoot, registration: inputs.registrations.document_observations, settings: inputs.ledgerSettings,
        ...(runtime.on_document_observations_persisted === undefined ? {} : { on_persisted: runtime.on_document_observations_persisted }),
      });
      const taskIdentity = {
        pipeline_name: "feed-ingest-plan", task_name: operation, run_id: record.run_id,
        correlation_id: record.correlation_id, request_id: record.request_id,
      };
      const controls = signal === undefined ? {} : { signal };
      if ("source_id" in request) {
        const source = inputs.harvest.sources.find(source => source.id === request.source_id);
        if (!source || source.status !== "active") throw new PlanError("INVALID_REQUEST", "Fetch requires an active configured source", "source_id");
        const url = request.kind === "feed" ? source.url : request.url!;
        try { validateTargetName(url); }
        catch { throw new PlanError("INVALID_REQUEST", "Fetch requires a public HTTP URL without credentials", "url"); }
        const identity = canonicalizeUrl(url);
        const eventIdentity = {
          run_id: record.run_id, correlation_id: record.correlation_id,
          article_id: identity.url_key, source_id: request.source_id,
        };
        const work = documentWork({
          observations, observation_clock: runtime.observation_clock ?? (() => new Date()),
        }, eventIdentity, record.request_id, {
          document_kind: request.kind, source_id: source.id, publisher_id: source.publisher_id,
          observed_run_id: null, observed_attempt: null, candidate_id: null,
        });
        const { fetched, observation, attempt_observations } = await profileTask(runtime.task_profiling, taskIdentity, () => work.fetch(
          createPermittedFetcher(inputs.harvest.config.harvest, inputs.harvest.extraction, runtime.boundary, runtime.observation_clock),
          url, request.caused_by_event_id ?? null,
        ), { ...controls, outcome: result => result.fetched.failure === null ? "success" : "error" });
        const attempts = fetched.attempts ?? [];
        const artifact = FetchedDocumentSchema.parse({
          ...fetched, kind: request.kind, canonical_url: identity.canonical_url,
          article_id: identity.url_key, source_id: request.source_id,
          error_code: fetched.error_code ?? null, robots_failure: fetched.robots_failure ?? null,
          robots_http_status: fetched.robots_http_status ?? null,
          body_sha256: fetched.body === null ? null : sha256(fetched.body), attempts, observation,
          attempt_observations,
        });
        const { body, ...receipt } = artifact;
        return {
          artifact,
          response_json: JSON.stringify(z.json().parse({ fetch_request_id: record.request_id, ...receipt })),
        };
      }
      const fetchedRecord = store.get(request.fetch_request_id);
      if (!fetchedRecord) throw new PlanError("ARTIFACT_NOT_FOUND", "No completed fetch exists for this request identity", "fetch_request_id");
      if (fetchedRecord.config_sha256 !== record.config_sha256) {
        throw new PlanError("REQUEST_CONFLICT", "Fetched document configuration differs from current configuration", "fetch_request_id");
      }
      const artifact = checkArtifact(fetchedRecord, inputs);
      if (artifact.article_id !== request.article_id || fetchedRecord.correlation_id !== request.correlation_id) {
        throw new PlanError("INVALID_REQUEST", "Parse identity must match its fetched document", "article_id");
      }
      if (artifact.body === null || artifact.failure !== null) throw new PlanError("FETCH_UNAVAILABLE", "Fetch has no successful body to parse", "fetch_request_id");
      const source = inputs.harvest.sources.find(source => source.id === artifact.source_id);
      if (!source) throw new PlanError("ARTIFACT_INVALID", "Fetched source is absent from current configuration", "source_id");
      const body = artifact.body;
      const work = documentWork({
        observations, observation_clock: runtime.observation_clock ?? (() => new Date()),
      }, {
        run_id: fetchedRecord.run_id, correlation_id: fetchedRecord.correlation_id,
        article_id: artifact.article_id, source_id: artifact.source_id,
      }, record.request_id, {
        document_kind: artifact.kind, source_id: source.id, publisher_id: source.publisher_id,
        observed_run_id: null, observed_attempt: null, candidate_id: null,
      });
      const { parsed, failure, observation } = await profileTask(runtime.task_profiling, taskIdentity, async () => {
        return artifact.kind === "feed"
          ? work.parse(() => parseDocument("feed", body, artifact.canonical_url), artifact.observation.event_id, describeFeedParse)
          : work.parse(() => parseDocument("article", body, artifact.canonical_url, inputs.harvest.extraction, source.form),
            artifact.observation.event_id, describeArticleParse);
      }, { ...controls, outcome: result => result.failure === null ? "success" : "error" });
      return { artifact: null, response_json: JSON.stringify(z.json().parse({
        fetch_request_id: request.fetch_request_id, observation, kind: artifact.kind, parsed, failure,
      })) };
    });
    observations?.assertSaved();
    return completed.response_json!;
  } finally { store.close(); }
}
