/** Do actual recorded stages produce truthful dispatch files without claiming audit completion? */
import { expect, test } from "bun:test";
import { mkdir, writeFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { join, relative } from "node:path";
import {
  CONTRACT_VERSION, FeedIngestDispatchSchema, FeedIngestEventSchema,
  deriveCandidateId, deriveUrlKey,
} from "@idhazh/common-contracts";
import { persistLedger } from "@idhazh/ledger-file-writer";
import { runFeedPlan, summarizePlan } from "../src/run-feed-plan";
import { loadPlanInputs } from "../src/load-plan-inputs";
import { readLedgerParquet } from "../src/read-ledger-history/read-parquet";
import { readSeenEvidence } from "../src/read-ledger-history/read-seen-evidence";
import { SeenRowSchema } from "../src/screen-article-candidates/seen-evidence";
import { recordedPlan } from "./plan-recordings";
import { source } from "./harvest-recordings";

test("real composition shares one clock and override and reads native dispatches with exact choices", async () => {
  const recorded = await recordedPlan([
    source(), source({ id: "resting-news", status: "draft" }),
    source({ id: "empty-news", url: "https://news.example/empty.xml" }),
  ]);
  let clocks = 0;
  recorded.runtime.clock = () => new Date(++clocks === 1 ? "2026-10-21T23:59:59.999Z" : "2026-10-22T00:00:01Z");
  try {
    const result = await runFeedPlan({
      freshness_hours: 18, article_limit: 1, partition_strategy: "none",
    }, recorded.inputs, recorded.runtime);
    expect(clocks).toBe(1);
    expect(result.status).toBe("dispatches_persisted_audit_pending");
    expect(result.context.date).toBe("2026-10-21");
    expect(result.context.writer.shard).toBe(0);
    expect(result.request.shards).toBe(1);
    expect(result.evidence.curation.rows.map(row => row.candidate_id)).toEqual([
      deriveCandidateId("2026-10-21-700", "recorded-news", 2),
    ]);
    expect(result.evidence.harvest.feed_outcomes).toHaveLength(3);
    expect(result.evidence.harvest.feed_outcomes.find(row => row.source.source_id === "resting-news"))
      .toMatchObject({ fetch_status: "not_requested", parsed_count: null, harvested_count: null });
    expect(result.evidence.harvest.feed_outcomes.find(row => row.source.source_id === "empty-news"))
      .toMatchObject({ parsed_count: 0, harvested_count: 0 });
    for (const candidate of result.evidence.harvest.candidates) {
      expect(candidate.date).toBe(result.context.date);
      expect(candidate.fetched_at).toBe(result.context.now);
      expect(candidate.policy.max_age_hours).toBe(18);
      expect(candidate.policy.recency_half_life_hours).toBe(18);
    }
    const events = result.events;
    expect(recorded.events).toEqual(events);
    events.forEach((event, sequence) => {
      expect(FeedIngestEventSchema.safeParse(event).success).toBe(true);
      expect(event.sequence).toBe(sequence);
      expect(event.occurred_at).toBe(result.context.now);
      expect(event.elapsed_ms).toBeGreaterThanOrEqual(event.step_elapsed_ms);
      expect(event.policy.max_age_hours).toBe(18);
    });
    expect(new Set(events.map(event => event.event_id)).size).toBe(events.length);
    expect(events.filter(event => event.payload.kind === "feed_outcome")).toHaveLength(3);
    const harvestDecisions = events.filter(event => event.stage === "harvest-feeds" && event.payload.kind === "candidate_decision");
    expect(harvestDecisions).toHaveLength(3);
    const screenDecisions = events.filter(event => event.stage === "screen-article-candidates" && event.payload.kind === "candidate_decision");
    expect(screenDecisions).toHaveLength(2);
    const choices = events.flatMap(event => event.payload.kind === "portfolio_choice" ? [event.payload] : []);
    expect(choices).toEqual(result.evidence.curation.trace.flatMap(step => step.choice === null ? [] : [step.choice]));
    for (const event of events) if (event.payload.kind === "stage_completion") {
      expect(event.payload.input_count).toBe(event.payload.output_count + event.payload.terminal_rejection_count);
    }
    expect(result.evidence.curation.normalization).toBeDefined();
    expect(JSON.stringify(events)).not.toContain(result.evidence.harvest.candidates[0]!.article_text);
    expect(JSON.stringify(events)).not.toContain("plan_complete");
    expect(result.files.dispatches.status).toBe("written");
    const rows = [];
    for (const file of result.files.dispatches.files) {
      expect(file.path).not.toMatch(/^[A-Za-z]:|\\/);
      const native = await readLedgerParquet(join(recorded.inputs.outputRoot, file.path), "dispatches", {
        schema: FeedIngestDispatchSchema, schemaVersion: CONTRACT_VERSION,
      });
      rows.push(...native.rows.map(held => held.row));
      expect(native.envelope.identity.shard).toBe(0);
      expect(native.envelope.identity.git_sha).toBe(recorded.runtime.git_sha);
    }
    expect(rows).toEqual(result.evidence.partition.dispatches);
    expect(rows[0]!.content.article_text).toBe(result.evidence.curation.selected[0]!.candidate.article_text);
    expect(rows[0]!.partition).toEqual({ strategy: "none", worker_assignment: 0, dispatch_count: 1 });
    expect(rows[0]!.selection.policy).toEqual(rows[0]!.content.policy);
    expect(summarizePlan(result)).toMatchObject({
      audited_complete: false, dispatch_count: 1, status: "dispatches_persisted_audit_pending",
    });
    expect(recorded.inputs.harvest.config.curate.article_limit).toBeNull();
    expect(recorded.inputs.harvest.config.triage.max_age_hours).toBe(24);
  } finally { await recorded.close(); }
}, 30000);

test("freshness equality is admitted; a smaller override really rejects; empty is not complete", async () => {
  const equal = await recordedPlan();
  const stale = await recordedPlan();
  const empty = await recordedPlan([source({ url: "https://news.example/empty.xml" })]);
  try {
    const exactHours = (Date.parse("2026-10-21T23:59:59Z") - Date.parse("2026-10-21T09:15:00Z")) / 3_600_000;
    const boundary = await runFeedPlan({ freshness_hours: exactHours }, equal.inputs, equal.runtime);
    expect(boundary.evidence.screening.admitted).toHaveLength(2);
    const rejected = await runFeedPlan({ freshness_hours: 12 }, stale.inputs, stale.runtime);
    expect(rejected.evidence.screening.admitted).toHaveLength(0);
    expect(rejected.evidence.screening.rejections.map(row => row.drop_reason))
      .toEqual(["STALE_MAX_AGE_EXCEEDED", "STALE_MAX_AGE_EXCEEDED"]);
    expect(rejected.files.dispatches).toEqual({ status: "empty", files: [] });
    const noArticles = await runFeedPlan({}, empty.inputs, empty.runtime);
    expect(noArticles.evidence.partition.dispatches).toEqual([]);
    expect(noArticles.files.selections).toEqual({ status: "empty", files: [] });
    expect(summarizePlan(noArticles).audited_complete).toBe(false);
  } finally { await Promise.all([equal.close(), stale.close(), empty.close()]); }
}, 30000);

test("named native first sight wins for undated articles; arbitrary empty history proves no absence", async () => {
  const recorded = await recordedPlan([source({ url: "https://news.example/article-failures.xml" })]);
  try {
    const noHistory = await readSeenEvidence(recorded.directory, []);
    expect(noHistory).toMatchObject({ evidence: { availability: "unavailable" }, global_absence: "unavailable" });
    const seen = SeenRowSchema.parse({
      version: "2026-08-31", url_key: deriveUrlKey("https://news.example/second"),
      first_seen_at: "2026-10-19T10:00:00Z", first_seen_run: "2026-10-19-1",
    });
    const stored = await persistLedger({
      ledger: "seen", rowContract: { schema: SeenRowSchema, schemaVersion: "2026-08-31" },
      outputRoot: recorded.inputs.outputRoot,
      writerContext: {
        run_id: "2026-10-19-1", attempt: 1, job: "plan", shard: 0,
        pipeline_name: null, task_name: null,
        producer: "tests.plan-seen", git_sha: "a".repeat(40),
      },
      registryEntry: {
        name: "seen", family: "seen", lifecycle_status: "active", grain: "raw-and-compact", prefix: ["seen"],
      },
      ledgerSettings: recorded.inputs.ledgerSettings, period: { tier: "raw", covers: "2026-10-19" }, rows: [seen],
    });
    recorded.inputs.settings.inputs.seen_files = stored.files.map(file =>
      relative(recorded.directory, join(recorded.inputs.outputRoot, file.path)).replaceAll("\\", "/"));
    const result = await runFeedPlan({}, recorded.inputs, recorded.runtime);
    expect(result.evidence.seen.evidence).toEqual({ availability: "available", rows: [seen] });
    expect(result.evidence.seen.global_absence).toBe("unavailable");
    const undated = result.evidence.screening.rejections.filter(row => row.url_key === seen.url_key);
    expect(undated.length).toBeGreaterThan(0);
    expect(undated.every(row => row.drop_reason === "STALE_MAX_AGE_EXCEEDED")).toBe(true);
    const assessment = result.events.flatMap(event => event.payload.kind === "candidate_decision"
      && event.stage === "screen-article-candidates" && event.payload.assessment.url_key === seen.url_key
      ? [event.payload.assessment] : [])[0]!;
    expect(assessment.publication_clock).toBe("unavailable");
    expect(assessment.effective_published_at).toBeNull();
    expect(assessment.age_hours).toBeNull();
    const freshUnknown = result.evidence.screening.admitted.filter(article => article.candidate.published_at === null);
    for (const article of freshUnknown) expect(article.freshness).toMatchObject({ timing_source: "unknown", recency_bonus: 0 });
  } finally { await recorded.close(); }
}, 30000);

test("invalid controls, disabled runs, inactive ledgers and unavailable named history fail before fetching", async () => {
  const recorded = await recordedPlan();
  try {
    for (const raw of [
      { freshness_hours: 0 }, { freshness_hours: "18" }, { shards: 0 },
      { article_limit: 1.1 }, { partition_strategy: "none", shards: 2 }, { partition_strategy: "unknown" },
    ]) await expect(runFeedPlan(raw, recorded.inputs, recorded.runtime)).rejects.toThrow();
    recorded.inputs.settings.enabled = false;
    await expect(runFeedPlan({}, recorded.inputs, recorded.runtime)).rejects.toThrow("disabled");
    recorded.inputs.settings.enabled = true;
    recorded.inputs.registrations.dispatches.lifecycle_status = "paused";
    await expect(runFeedPlan({}, recorded.inputs, recorded.runtime)).rejects.toThrow("dispatches");
    recorded.inputs.registrations.dispatches.lifecycle_status = "active";
    recorded.inputs.settings.inputs.seen_files = ["state/raw/seen/missing.parquet"];
    await expect(runFeedPlan({}, recorded.inputs, recorded.runtime)).rejects.toThrow();
    expect(recorded.transport.requests).toHaveLength(0);
    expect(recorded.events).toHaveLength(0);
  } finally { await recorded.close(); }
});

test("real dispatch persistence failure leaves earlier files but emits no storage completion", async () => {
  const recorded = await recordedPlan();
  try {
    const blocker = join(recorded.inputs.outputRoot, "raw", "feed-ingest-plan", "dispatches");
    await mkdir(join(recorded.inputs.outputRoot, "raw", "feed-ingest-plan"), { recursive: true });
    await writeFile(blocker, "A file cannot be a ledger directory.");
    await expect(runFeedPlan({}, recorded.inputs, recorded.runtime)).rejects.toThrow();
    expect(recorded.events.some(event => event.stage === "curate-article-portfolio" && event.payload.kind === "stage_completion")).toBe(true);
    expect(recorded.events.some(event => event.stage === "seal-article-ledger")).toBe(false);
    expect(recorded.events.some(event => "status" in event.payload)).toBe(false);
  } finally { await recorded.close(); }
}, 30000);

test("named input loader works from a generated configuration root without any backend directory", async () => {
  const recorded = await recordedPlan();
  try {
    const authored = recorded.inputs.settings;
    const paths = authored.inputs;
    const configDirectory = join(recorded.directory, "config");
    await mkdir(configDirectory);
    const originalRoot = new URL("../../../", import.meta.url);
    const named = ["planning", "taxonomy", "sources", "extraction", "registrations"] as const;
    for (const field of named) {
      await writeFile(join(recorded.directory, paths[field]), await Bun.file(new URL(paths[field], originalRoot)).text());
    }
    await writeFile(join(configDirectory, "feed-ingest-plan-service.json"), JSON.stringify(authored));
    const loaded = await loadPlanInputs(recorded.directory);
    expect(loaded.harvest.config.version).toBe("2026-10-20");
    expect(existsSync(join(recorded.directory, "backend"))).toBe(false);
  } finally { await recorded.close(); }
});
