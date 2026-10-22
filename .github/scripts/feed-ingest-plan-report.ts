/** Which source and stage outcomes can validated planner events actually prove? */
import { appendFile, readFile } from "node:fs/promises";
import { FeedIngestConfigSchema, HarvestDiagnosticsSchema, HostFingerprintRowSchema, RunIdSchema, SourceRunRecordSchema, WriterIdentitySchema, readFeedIngestEvent } from "../../packages/common-contracts/src/index";
import type { FeedIngestEvent, HarvestDiagnostics } from "../../packages/common-contracts/src/index";
import { join } from "node:path";

export type PlannerReport = Readonly<{ annotations: readonly string[]; summary: string }>;

function escapeCommand(value: string): string {
  return value.replaceAll("%", "%25").replaceAll("\r", "%0D").replaceAll("\n", "%0A");
}

function escapeParameter(value: string): string {
  return escapeCommand(value).replaceAll(":", "%3A").replaceAll(",", "%2C");
}

function escapeMarkdown(value: string): string {
  return value.replace(/[\u0000-\u0020\u007f-\u009f\u2028\u2029]/g, " ")
    .replace(/[&<>"'\\`*_{}[\]()#+.!|:=-]/g, character => `&#${character.charCodeAt(0)};`);
}

function validateEvents(input: unknown): FeedIngestEvent[] {
  if (!Array.isArray(input)) throw new Error("events must be an array");
  const events = input.map(readFeedIngestEvent);
  const first = events[0];
  const identities = new Set<string>();
  let sequence = -1;
  for (const event of events) {
    if (event.run_id !== first?.run_id || event.attempt !== first.attempt
      || event.correlation_id !== first.correlation_id) {
      throw new Error("events.run_id, attempt and correlation_id must identify one planning attempt");
    }
    if (event.sequence <= sequence || identities.has(event.event_id)) {
      throw new Error("events.sequence and event_id must be unique and ordered");
    }
    identities.add(event.event_id);
    sequence = event.sequence;
  }
  return events;
}

export function formatPlannerReport(input: unknown): PlannerReport {
  const events = validateEvents(input);
  const first = events[0];
  const annotations: string[] = [];
  const sourceRows: string[] = [];
  const stageRows: string[] = [];
  const decisions = new Map<string, number>();
  for (const event of events) {
    const payload = event.payload;
    if (payload.kind === "feed_outcome") {
      const outcome = `${payload.fetch_status} / ${payload.parse_status}`;
      annotations.push(`::notice title=${escapeParameter("Feed ingest source outcome")}::${escapeCommand(
        `${payload.source.source_id}: ${outcome}; harvested ${payload.harvested_count ?? "unavailable"} articles`,
      )}`);
      sourceRows.push(`| A${sourceRows.length + 1} | ${escapeMarkdown(payload.source.source_id)} | ${escapeMarkdown(payload.source.title)} | ${escapeMarkdown(outcome)} | ${payload.parsed_count ?? "Unavailable"} | ${payload.harvested_count ?? "Unavailable"} | ${payload.rejection_reason ?? "None recorded"} |`);
    } else if (payload.kind === "stage_completion") {
      stageRows.push(`| B${stageRows.length + 1} | ${escapeMarkdown(payload.stage)} | ${payload.input_count} | ${payload.output_count} | ${payload.terminal_rejection_count} | ${(event.step_elapsed_ms / 1000).toFixed(3)} |`);
    } else if (payload.kind === "candidate_decision") {
      const assessment = payload.assessment;
      const key = `${assessment.stage}: ${assessment.decision} / ${assessment.reason ?? "no rejection reason"}`;
      decisions.set(key, (decisions.get(key) ?? 0) + 1);
    }
  }
  const summary = [
    "# Feed ingest plan report",
    "",
    first === undefined ? "No events supplied. Source and stage evidence is unavailable."
      : `Run: ${escapeMarkdown(first.run_id)}. Attempt: ${first.attempt}. First observation: ${escapeMarkdown(first.occurred_at)} (UTC).`,
    "",
    "**Audit completion: unavailable.** These stage events do not prove that required audit files were written. This report does not certify a complete plan or publication.",
    "",
    "## Table A - Source outcomes",
    "",
    "| Id | Source | Title | Fetch / parse | Parsed articles | Harvested articles | Rejection reason |",
    "| --- | --- | --- | --- | --- | --- | --- |",
    ...sourceRows,
    ...(sourceRows.length === 0 ? ["", "Source outcomes unavailable."] : []),
    "",
    "## Table B - Observed stage completions",
    "",
    "| Id | Stage | Input count | Output count | Terminal rejections | Step time (seconds) |",
    "| --- | --- | --- | --- | --- | --- |",
    ...stageRows,
    ...(stageRows.length === 0 ? ["", "Stage completion evidence unavailable."] : []),
    "",
    "## Candidate decisions",
    "",
    ...[...decisions].map(([decision, count]) => `- ${escapeMarkdown(decision)}: ${count} observations.`),
    ...(decisions.size === 0 ? ["Candidate decision evidence unavailable."] : []),
    "",
    "Counts describe only supplied events, not a reconciled audit. Article text, source URLs, request headers and full event payloads are not included.",
    "",
  ].join("\n");
  return { annotations, summary };
}

function object(value: unknown): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) throw new Error("Expected report evidence object");
  return value as Record<string, unknown>;
}

export function formatExecutionReport(input: Readonly<{
  response: unknown; host: unknown; progress: readonly unknown[]; historyStagingMs: unknown;
}>): string {
  const response = object(input.response);
  const runId = RunIdSchema.parse(response.run_id);
  const completion = object(response.planning_completion);
  if (typeof completion.attempt !== "number" || !Number.isSafeInteger(completion.attempt) || completion.attempt < 1
    || typeof response.correlation_id !== "string" || response.correlation_id.length === 0) {
    throw new Error("Report requires the completed planning attempt identity");
  }
  if (!Array.isArray(response.source_records)) throw new Error("Report requires actual source records");
  const sources = response.source_records.map(row => SourceRunRecordSchema.parse(row));
  const host = input.host === null ? null : HostFingerprintRowSchema.parse(object(input.host).row);
  if (sources.some(source => source.run_id !== runId || source.attempt !== completion.attempt
    || source.correlation_id !== response.correlation_id)) throw new Error("Report source evidence differs from the planning attempt");
  if (host !== null) {
    const writer = WriterIdentitySchema.parse(object(input.host).writer);
    if (writer.run_id !== runId || writer.attempt !== completion.attempt || writer.producer !== "telemetry.silicon"
      || host.run_id !== writer.run_id || host.date !== response.date
      || host.pipeline_name !== writer.pipeline_name || host.task_name !== writer.task_name || host.shard !== writer.shard) {
      throw new Error("Report host evidence differs from the planning attempt");
    }
  }
  const request = object(response.request);
  const limit = request.article_limit;
  if (limit !== null && (typeof limit !== "number" || !Number.isSafeInteger(limit) || limit <= 0)) {
    throw new Error("Report requires the resolved requested article limit");
  }
  const sum = (key: "parsed_count" | "harvested_count" | "fresh_count" | "duplicate_count" | "eligible_count" | "normalized_count" | "selected_count") => {
    const measured = sources.filter(source => source[key] !== null);
    return `${measured.reduce((total, source) => total + source[key]!, 0)} articles; ${measured.length}/${sources.length} sources measured`;
  };
  const progress = input.progress.map((value): Record<string, unknown> & { diagnostics: HarvestDiagnostics | null | undefined } => {
    const entry = object(value);
    return { ...entry, diagnostics: entry.diagnostics === undefined || entry.diagnostics === null
      ? entry.diagnostics : HarvestDiagnosticsSchema.parse(entry.diagnostics) };
  });
  for (const entry of progress) {
    if (typeof entry.eventType !== "string" || typeof entry.elapsedMs !== "number"
      || !Number.isFinite(entry.elapsedMs) || entry.elapsedMs < 0) throw new Error("Invalid progress timing evidence");
    if (entry.correlationId !== response.correlation_id) throw new Error("Report progress evidence differs from the planning attempt");
  }
  function duration(start: string, end: string): string {
    const first = progress.find(entry => entry.eventType === start);
    const last = progress.findLast(entry => entry.eventType === end);
    if (first === undefined || last === undefined) return "Unavailable";
    const milliseconds = Number(last.elapsedMs) - Number(first.elapsedMs);
    if (milliseconds < 0) throw new Error("Progress timing endpoints are reversed");
    return `${(milliseconds / 1000).toFixed(3)} seconds`;
  }
  const drops = new Map<string, number>();
  for (const source of sources) for (const drop of source.drop_reasons) {
    const key = `${drop.subject} / ${drop.stage} / ${drop.reason}`;
    drops.set(key, (drops.get(key) ?? 0) + drop.count);
  }
  const observedEntries = sources.reduce((total, source) => total + (source.parsed_count ?? 0), 0);
  const feedAttempts = sources.filter(source => source.fetch_status !== "not_requested").length;
  const feedFailures = sources.filter(source => !["success", "not_requested"].includes(source.fetch_status)).length;
  const articleStarts = progress.filter(entry => entry.eventType === "ARTICLE_HARVEST_STARTED").length;
  const articleEnds = progress.filter(entry => entry.eventType === "ARTICLE_HARVEST_COMPLETED");
  const measuredArticles = articleEnds.filter(entry => entry.diagnostics !== undefined);
  const fetchedArticles = measuredArticles.filter(entry => entry.diagnostics?.fetch_ms !== null && entry.diagnostics?.fetch_ms !== undefined);
  const extractedArticles = measuredArticles.filter(entry => entry.diagnostics?.extract_ms !== null && entry.diagnostics?.extract_ms !== undefined);
  const earlyRefusals = measuredArticles.filter(entry => entry.diagnostics === null && typeof entry.drop_reason === "string");
  const targetResponses = fetchedArticles.filter(entry => entry.diagnostics?.http_status !== null);
  const measuredFeeds = progress.filter(entry => entry.eventType === "FEED_FETCH_COMPLETED" && entry.diagnostics != null);
  const diagnosticArticles = measuredArticles.filter(entry => entry.diagnostics !== null);
  const operationFailures = new Map<string, number>();
  for (const entry of progress.filter(entry => ["FEED_FETCH_COMPLETED", "ARTICLE_HARVEST_COMPLETED"].includes(String(entry.eventType)))) {
    const diagnostics = entry.diagnostics;
    if (diagnostics === undefined || diagnostics === null) continue;
    const subject = entry.eventType === "FEED_FETCH_COMPLETED" ? "feed" : "article";
    for (const key of ["fetch_failure", "extraction_failure", "robots_failure", "error_code", "failure_code", "http_status", "robots", "robots_http_status"] as const) {
      const value = diagnostics[key];
      if (value === null) continue;
      const label = `${subject} / ${key} / ${value}`;
      operationFailures.set(label, (operationFailures.get(label) ?? 0) + 1);
    }
    for (const warning of diagnostics.warnings) {
      const label = `${subject} / warning / ${warning}`;
      operationFailures.set(label, (operationFailures.get(label) ?? 0) + 1);
    }
  }
  function operationTime(entries: typeof fetchedArticles, key: "fetch_ms" | "extract_ms"): string {
    if (entries.length === 0) return "Unavailable (no measured operations)";
    const total = entries.reduce((sum, entry) => sum + entry.diagnostics![key]!, 0);
    return `${(total / 1000).toFixed(3)} seconds summed over ${entries.length} measured operations; not elapsed wall time`;
  }
  const extraction = (outcome: string) => articleEnds.filter(entry => entry.extraction_outcome === outcome).length;
  const staging = typeof input.historyStagingMs === "number" && Number.isFinite(input.historyStagingMs) && input.historyStagingMs >= 0
    ? `${(input.historyStagingMs / 1000).toFixed(3)} seconds` : "Unavailable";
  return [
    "## Table C - Live yield",
    "",
    "| Id | Observation | Recorded result |",
    "| --- | --- | --- |",
    `| C1 | Offered feed entries | ${sum("parsed_count")} |`,
    `| C2 | Fresh entries | ${sum("fresh_count")} |`,
    `| C3 | Harvested candidates | ${sum("harvested_count")} |`,
    `| C4 | Duplicates | ${sum("duplicate_count")} |`,
    `| C5 | Screened eligible | ${sum("eligible_count")} |`,
    `| C6 | Normalized candidates | ${sum("normalized_count")} |`,
    `| C7 | Selected; requested limit ${limit ?? "uncapped"} | ${sum("selected_count")} |`,
    `| C8 | Feed fetch failures | ${feedFailures}/${feedAttempts} attempted feeds |`,
    `| C9 | Article harvest operations | ${progress.length === 0 ? "Unavailable" : `${articleEnds.length}/${articleStarts} started operations completed; not a page-request count`} |`,
    `| C10 | Extraction outcomes | ${progress.length === 0 ? "Unavailable" : `${extraction("success")} success; ${extraction("empty")} empty; ${extraction("failed")} failed; ${extraction("not-attempted")} not attempted; denominator ${articleEnds.length} completed operations`} |`,
    `| C11 | Refused before permitted fetching | ${measuredArticles.length === 0 ? "Unavailable" : `${earlyRefusals.length}/${measuredArticles.length} article completions with declared diagnostics`} |`,
    `| C12 | Permitted article fetch operations | ${measuredArticles.length === 0 ? "Unavailable" : `${fetchedArticles.length}/${measuredArticles.length} article completions with declared diagnostics; ${targetResponses.length} recorded target responses`} |`,
    `| C13 | Extraction operations | ${measuredArticles.length === 0 ? "Unavailable" : `${extractedArticles.length}/${fetchedArticles.length} measured fetch operations reached extraction`} |`,
    "",
    "A permitted fetch includes DNS, robots, retries and redirects; it is not a count of outbound HTTP requests. Target responses include recorded error or redirect statuses. Null diagnostics identify an operation that was not performed; absent historical diagnostics are unavailable. Screened eligible does not mean previously unpublished.",
    "",
    "## Table D - Refusals",
    "",
    "| Id | Subject / stage / reason | Count and denominator |",
    "| --- | --- | --- |",
    ...[...drops].map(([reason, count], index) => `| D${index + 1} | ${escapeMarkdown(reason)} | ${count}/${reason.startsWith("feed /") ? sources.length : observedEntries} ${reason.startsWith("feed /") ? "configured sources" : "observed parsed entries"} |`),
    ...(drops.size === 0 ? ["No recorded refusals."] : []),
    "",
    "Feed decisions use all configured sources, including inactive sources that were not fetched. Article reasons use observed parsed entries, not all feeds. Failed feed parses have no known entry count. Early refusals occur before article fetching; later refusals must not be subtracted again.",
    "",
    "## Table E - Measured elapsed time",
    "",
    "| Id | Work | Elapsed time |",
    "| --- | --- | --- |",
    `| E1 | Named history staging and input loading | ${staging} |`,
    `| E2 | Planner history read | ${duration("HISTORY_READ_STARTED", "HISTORY_READ_COMPLETED")} |`,
    `| E3 | Planning stages | ${duration("PIPELINE_STARTED", "PLANNING_STAGES_COMPLETED")} |`,
    `| E4 | Audit recording | ${duration("AUDIT_RECORDING_STARTED", "AUDIT_RECORDING_COMPLETED")} |`,
    `| E5 | HTTP listener through response | ${duration("HTTP_LISTENER_STARTED", "HTTP_RESPONSE_RECEIVED")} |`,
    `| E6 | Job start through host observation | ${host?.job_seconds === null || host === null ? "Unavailable" : `${host.job_seconds} seconds`} |`,
    `| E7 | Article permitted fetch work | ${operationTime(fetchedArticles, "fetch_ms")} |`,
    `| E8 | Article extraction work | ${operationTime(extractedArticles, "extract_ms")} |`,
    "",
    "Elapsed intervals overlap; do not add them. The job observation excludes the later report, commit and artifact upload.",
    "",
    "## Table F - Actual host",
    "",
    "| Id | Observation | Recorded result |",
    "| --- | --- | --- |",
    `| F1 | Hardware fingerprint | ${host?.fingerprint ?? "Unavailable"} |`,
    `| F2 | CPU | ${escapeMarkdown(host?.cpu_model ?? "Unavailable")} |`,
    `| F3 | Logical / allowed processors | ${host?.cpu_logical_processors ?? "Unavailable"} / ${host?.cpu_allowed_processors ?? "Unavailable"} |`,
    `| F4 | CPU quota | ${host?.cpu_quota_state === "finite" ? `${host.cpu_quota_cores} cores` : host?.cpu_quota_state ?? "Unavailable"} |`,
    `| F5 | L3 cache | ${host?.l3_cache_bytes === null || host === null ? "Unavailable" : `${host.l3_cache_bytes} bytes`} |`,
    `| F6 | Pipeline / task | ${escapeMarkdown(host?.pipeline_name ?? "Unavailable")} / ${escapeMarkdown(host?.task_name ?? "Unavailable")} |`,
    "",
    "## Table G - Recorded operation diagnostics",
    "",
    "| Id | Subject / observation / value | Count and denominator |",
    "| --- | --- | --- |",
    ...[...operationFailures].map(([label, count], index) => `| G${index + 1} | ${escapeMarkdown(label)} | ${count}/${label.startsWith("feed /") ? measuredFeeds.length : diagnosticArticles.length} ${label.startsWith("feed /") ? "feed" : "article"} completions with recorded operation diagnostics |`),
    ...(operationFailures.size === 0 ? ["Operation diagnostic observations unavailable."] : []),
    "",
    "Each diagnostic field is counted separately; one operation can appear in several rows. Do not add these rows as failures. Null values remain unavailable, not zero.",
    "",
    `Planning completion: ${response.planning_complete === true ? "verified" : "unavailable"}. Publication audit completion: ${response.audited_complete === true ? "verified" : "pending"}. Git commit status is reported by the separate exact-file commit step.`,
    "",
  ].join("\n");
}

export async function writePlannerReport(input: Readonly<{
  enabled: boolean; events: unknown; summaryPath?: string; annotate: (line: string) => void; executionSummary?: string;
}>): Promise<void> {
  if (!input.enabled) return;
  const report = formatPlannerReport(input.events);
  if (input.summaryPath === undefined || input.summaryPath.length === 0) {
    throw new Error("GITHUB_STEP_SUMMARY is required when workflow reporting is enabled");
  }
  await appendFile(input.summaryPath, report.summary + (input.executionSummary ?? ""), "utf8");
  for (const line of report.annotations) input.annotate(line);
}

if (import.meta.main) {
  const configPath = process.argv[2];
  if (configPath === undefined) throw new Error("config path is required");
  const config = FeedIngestConfigSchema.parse(JSON.parse(await readFile(configPath, "utf8")));
  if (config.workflow_reporting.enabled) {
    const eventsPath = process.argv[3];
    if (eventsPath === undefined) throw new Error("events path is required when workflow reporting is enabled");
    const directory = process.argv[4];
    const executionSummary = directory === undefined ? undefined : formatExecutionReport({
      response: await Bun.file(join(directory, "response.json")).json(),
      host: await Bun.file(join(directory, "host.json")).exists() ? await Bun.file(join(directory, "host.json")).json() : null,
      progress: (await readFile(join(directory, "progress.jsonl"), "utf8")).trim().split("\n").filter(Boolean).map(line => JSON.parse(line)),
      historyStagingMs: await Bun.file(join(directory, "history-staging-ms.json")).json(),
    });
    await writePlannerReport({
      enabled: true, events: JSON.parse(await readFile(eventsPath, "utf8")),
      ...(process.env.GITHUB_STEP_SUMMARY === undefined ? {} : { summaryPath: process.env.GITHUB_STEP_SUMMARY }),
      annotate: line => console.log(line),
      ...(executionSummary === undefined ? {} : { executionSummary }),
    });
  }
}
