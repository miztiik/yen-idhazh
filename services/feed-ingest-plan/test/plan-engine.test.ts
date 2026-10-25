/** Do actual recorded stages produce truthful dispatch files without claiming audit completion? */
import { expect, test } from "bun:test";
import { mkdir, stat, writeFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import {
  FeedIngestEventSchema,
  CandidateRejectionContract,
  EditorialSelectionContract,
  deriveCandidateId, deriveUrlKey,
  FeedHealthContract, SOURCE_RELIABILITY_VERSION, readFeedIngestEvent,
} from "@idhazh/common-contracts";
import { persistLedger } from "@idhazh/ledger-file-writer";
import { runFeedPlan, summarizePlan } from "../src/run-feed-plan";
import { loadPlanInputs } from "../src/load-plan-inputs";
import { readLedgerParquet } from "../src/read-ledger-history/read-parquet";
import { readLedgerDay } from "../src/read-ledger-history/read-period";
import { PublishedRowSchema, PUBLISHED_ROW_SCHEMA_VERSION } from "../src/metrics/publication-evidence";
import { DispatchContract } from "../src/metrics/audit-contracts";
import { readSeenEvidence, requiredSeenDays } from "../src/read-ledger-history/read-seen-evidence";
import { SeenRowSchema } from "../src/screen-article-candidates/seen-evidence";
import { recordedPlan } from "./plan-recordings";
import { source } from "./harvest-recordings";
import { endpointKey, readFeedHistory } from "../src/read-ledger-history/read-feed-history";
import { loadHarvestInputs, sourceSnapshot } from "../src/harvest-feeds/load-harvest-inputs";
import { readDailyPublication, DailyPublicationSchema, DailyPublicationContract } from "../src/read-ledger-history/read-daily-publication";
import { ItemHealthFailureProjectionContract } from "../src/read-ledger-history/item-health-failure";
import { preparePlanningMetrics, recordPlanningMetrics } from "../src/metrics/metrics-recorder";
import { canonicalizeUrl } from "../src/harvest-feeds/url-cleaner";

async function seenWindow(recorded: Awaited<ReturnType<typeof recordedPlan>>, knownUrl: string) {
  recorded.inputs.clock_config.collect.seen_window_days = 2;
  recorded.runtime.clock = () => new Date("2026-10-21T12:00:00Z");
  const registration = recorded.inputs.registrations.seen;
  const contract = { schema: SeenRowSchema, schemaVersion: "2026-08-31" };
  const local = (path: string) => relative(recorded.directory, path).replaceAll("\\", "/");
  const write = async (day: string, first: string) => persistLedger({
    ledger: "seen", registryEntry: registration, outputRoot: recorded.inputs.outputRoot,
    ledgerSettings: recorded.inputs.ledgerSettings, rowContract: contract,
    period: { tier: "raw", covers: day },
    writerContext: {
      run_id: `${day}-1`, attempt: 1, job: "plan", shard: 0,
      pipeline_name: null, task_name: null, producer: "tests.seen-window", git_sha: "a".repeat(40),
    },
    rows: [SeenRowSchema.parse({
      version: "2026-08-31", url_key: deriveUrlKey(knownUrl),
      first_seen_at: first, first_seen_run: `${first.slice(0, 10)}-1`,
    })],
  });
  const early = await write("2026-10-19", "2026-10-19T10:00:00Z");
  const late = await write("2026-10-20", "2026-10-19T10:00:01Z");
  const original = await readLedgerParquet(join(recorded.inputs.outputRoot, early.files[0]!.path), "seen", contract);
  const compact = await persistLedger({
    ledger: "seen", registryEntry: registration, outputRoot: recorded.inputs.outputRoot,
    ledgerSettings: recorded.inputs.ledgerSettings, rowContract: contract,
    period: { tier: "compact", period: "daily", covers: "2026-10-19", builtFrom: 1 },
    writerContext: { ...original.envelope.identity, producer: "tests.compact-seen", attempt: 2 },
    rows: original.rows,
  });
  const index = join(recorded.inputs.outputRoot, "compact", "seen", "index", "daily.json");
  await mkdir(dirname(index), { recursive: true });
  const indexed = compact.files[0]!;
  const entries = [{
    covers: "2026-10-19", state: "packed", rows: indexed.row_count,
    bytes: (await stat(join(recorded.inputs.outputRoot, indexed.path))).size,
  }];
  await writeFile(index, JSON.stringify({ version: "2026-10-07", ledger: "seen", period: "daily", entries }));
  recorded.inputs.settings.inputs.seen_days = [
    { day: "2026-10-19", indexes: { daily: local(index) } },
    { day: "2026-10-20", raw_files: late.files.map(file => local(join(recorded.inputs.outputRoot, file.path))) },
    { day: "2026-10-21", raw_files: [] },
  ];
  return { index, entries, local };
}

test("real composition shares one clock and override and reads native dispatches with exact choices", async () => {
  const publisherId = "recorded-publication";
  const recorded = await recordedPlan([
    source({ publisher_id: publisherId }),
    source({ id: "resting-news", status: "draft", publisher_id: publisherId }),
    source({ id: "empty-news", url: "https://news.example/empty.xml", publisher_id: publisherId }),
  ], [{ id: publisherId, display_name: "Recorded Publication" }]);
  let clocks = 0;
  recorded.runtime.clock = () => new Date(++clocks === 1 ? "2026-10-21T23:59:59.999Z" : "2026-10-22T00:00:01Z");
  const configuredLimit = recorded.inputs.harvest.config.curate.article_limit;
  const blockedUrl = "https://fool.com/the-ascent/blocked-story";
  const innocentUrl = "https://news.example/innocent-query?next=fool.com%2Fthe-ascent%2Fstory";
  const blockedIdentity = canonicalizeUrl(blockedUrl);
  const innocentIdentity = canonicalizeUrl(innocentUrl);
  recorded.transport.recordings.bodies.rss = `<rss version="2.0"><channel><title>Structured exclusion</title>
    <item><title>Configured exclusion</title><link>${blockedUrl}</link><pubDate>Wed, 21 Oct 2026 09:15:00 GMT</pubDate></item>
    <item><title>Missing link</title></item>
    <item><title>Innocent query mention</title><link>${innocentUrl}</link><pubDate>Wed, 21 Oct 2026 10:15:00 GMT</pubDate></item>
  </channel></rss>`;
  recorded.transport.recordings.responses[innocentUrl] = [{ status: 200, fixture: "article" }];
  try {
    const day = "2026-10-21";
    const publication = await persistLedger({
      ledger: "published", registryEntry: recorded.inputs.registrations.published,
      outputRoot: recorded.inputs.outputRoot, ledgerSettings: recorded.inputs.ledgerSettings,
      rowContract: { schema: PublishedRowSchema, schemaVersion: PUBLISHED_ROW_SCHEMA_VERSION },
      period: { tier: "raw", covers: day },
      writerContext: { run_id: `${day}-1`, attempt: 1, job: "work", pipeline_name: null,
        task_name: null, shard: 0, producer: "tests.publication", git_sha: "a".repeat(40) },
      rows: [{ version: PUBLISHED_ROW_SCHEMA_VERSION, published_on: day,
        url_key: deriveUrlKey("https://news.example/historical-publication"), item_id: "recorded-item-01" }],
    });
    recorded.inputs.settings.inputs.published_days = [{
      day, raw_files: publication.files.map(file => `state/${file.path}`),
    }];
    const selectionIndex = join(recorded.inputs.outputRoot, "raw",
      ...recorded.inputs.registrations.selections.prefix, ...day.split("-"), "index.json");
    await mkdir(dirname(selectionIndex), { recursive: true });
    await writeFile(selectionIndex, JSON.stringify({
      version: "2026-10-03", ledger: "editorial-selections", date: day, files: [], bytes: [],
      content_sha256: "0".repeat(64), listed_at: `${day}T23:59:59Z`,
    }));
    await expect(readLedgerDay({
      ledger: "editorial-selections", day, contract: EditorialSelectionContract,
      rawIndex: selectionIndex,
    })).rejects.toThrow("filename digest");
    const result = await runFeedPlan({
      freshness_hours: 18, article_limit: 1, partition_strategy: "none",
    }, recorded.inputs, recorded.runtime);
    expect(clocks).toBe(1);
    expect(result.status).toBe("dispatches_persisted_audit_pending");
    expect(result.context.date).toBe("2026-10-21");
    expect(result.evidence.publisher_publication.gaps).toEqual(["invalid_publication_history"]);
    expect(result.context.writer.shard).toBe(0);
    expect(result.request.shards).toBe(1);
    expect(result.evidence.curation.rows.map(row => row.candidate_id)).toEqual([
      deriveCandidateId("2026-10-21-700", "recorded-news", 2),
    ]);
    expect(result.evidence.curation.rows[0]!.ratings.publisher_exposure).toMatchObject({
      publisher_id: publisherId, history_status: "unavailable",
      published_today: null, selected_so_far: 0, planned_slots: 1, value: 0,
    });
    expect(result.evidence.curation.rows[0]!.ratings.source).toEqual({ available: false, value: null });
    expect(result.evidence.harvest.feed_outcomes).toHaveLength(3);
    expect(result.evidence.harvest.feed_outcomes.map(row => row.source.publisher_id))
      .toEqual([publisherId, publisherId, publisherId]);
    expect(result.evidence.harvest.feed_outcomes.find(row => row.source.source_id === "resting-news"))
      .toMatchObject({ fetch_status: "not_requested", parsed_count: null, harvested_count: null });
    expect(result.evidence.harvest.feed_outcomes.find(row => row.source.source_id === "empty-news"))
      .toMatchObject({ parsed_count: 0, harvested_count: 0 });
    expect(recorded.transport.requests.some(request => request.url.href === blockedUrl)).toBe(false);
    expect(recorded.transport.requests.some(request => request.url.href === innocentUrl)).toBe(true);
    const blocked = result.evidence.harvest.articles.find(article =>
      article.rejection?.drop_reason === "BLOCKED_URL_MARKER");
    expect(blocked?.rejection).toMatchObject({
      canonical_url: blockedIdentity.canonical_url,
      url_key: deriveUrlKey(blockedIdentity.canonical_url),
      details: { matched_url_key: deriveUrlKey(blockedIdentity.canonical_url), matched_url_marker: "fool.com/the-ascent/" },
    });
    const innocent = result.evidence.harvest.candidates.find(candidate =>
      candidate.url_key === innocentIdentity.url_key);
    expect(innocent).toMatchObject({
      canonical_url: innocentIdentity.canonical_url,
      url_key: deriveUrlKey(innocentIdentity.canonical_url),
    });
    expect(result.evidence.harvest.candidates.map(candidate => candidate.url_key)).not.toContain(blockedIdentity.url_key);
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
    expect(events.flatMap(event => event.payload.kind === "feed_outcome" ? [event.payload.source.publisher_id] : []))
      .toEqual([publisherId, publisherId, publisherId]);
    const feedEvent = events.find(event => event.payload.kind === "feed_outcome");
    if (!feedEvent || feedEvent.payload.kind !== "feed_outcome") throw new Error("feed outcome event was not emitted");
    const { publisher_id: _publisherId, ...legacyEventSource } = feedEvent.payload.source;
    expect(readFeedIngestEvent({
      ...feedEvent, version: SOURCE_RELIABILITY_VERSION,
      payload: { ...feedEvent.payload, source: legacyEventSource },
    }).payload).toMatchObject({ kind: "feed_outcome", source: { publisher_id: null } });
    expect(() => readFeedIngestEvent({
      ...feedEvent, version: SOURCE_RELIABILITY_VERSION,
    })).toThrow();
    const harvestDecisions = events.filter(event => event.stage === "harvest-feeds" && event.payload.kind === "candidate_decision");
    expect(harvestDecisions).toHaveLength(3);
    const screenDecisions = events.filter(event => event.stage === "screen-article-candidates" && event.payload.kind === "candidate_decision");
    expect(screenDecisions).toHaveLength(1);
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
      const native = await readLedgerParquet(join(recorded.inputs.outputRoot, file.path), "dispatches", DispatchContract);
      rows.push(...native.rows.map(held => held.row));
      expect(native.envelope.identity.shard).toBe(0);
      expect(native.envelope.identity.git_sha).toBe(recorded.runtime.git_sha);
    }
    expect(rows).toEqual(result.evidence.partition.dispatches);
    expect(rows[0]!.content.article_text).toBe(result.evidence.curation.selected[0]!.candidate.article_text);
    expect(rows[0]!.content.source.publisher_id).toBe(publisherId);
    expect(rows[0]!.selection.source.publisher_id).toBe(publisherId);
    expect(rows[0]!.partition).toEqual({ strategy: "none", worker_assignment: 0, dispatch_count: 1 });
    expect(rows[0]!.selection.policy).toEqual(rows[0]!.content.policy);
    expect(summarizePlan(result)).toMatchObject({
      audited_complete: false, dispatch_count: 1, status: "dispatches_persisted_audit_pending",
      planning_complete: false, planning_completion: null, source_records: null,
    });
    expect(recorded.inputs.harvest.config.curate.article_limit).toBe(configuredLimit);
    expect(recorded.inputs.harvest.config.triage.max_age_hours).toBe(24);
    const nativeHealth = await readLedgerParquet(
      join(recorded.inputs.outputRoot, result.files.feed_health.files[0]!.path), "feed-health", FeedHealthContract,
    );
    expect(nativeHealth.envelope.row_schema_version).toBe(FeedHealthContract.schemaVersion);
    expect(nativeHealth.rows.find(held => held.row.feed_id === "resting-news")!.row).toMatchObject({
      outcome: "skipped", target_attempted: false, detail: "source inactive",
    });
    expect(nativeHealth.rows.find(held => held.row.feed_id === "empty-news")!.row).toMatchObject({
      outcome: "ok", items: 0, target_attempted: true,
    });
    expect(nativeHealth.rows.find(held => held.row.feed_id === "recorded-news")!.row.items).toBe(2);
    expect(nativeHealth.rows.every(held => held.row.publisher_id === publisherId)).toBe(true);
    const planningAudit = await recordPlanningMetrics(result, recorded.inputs);
    expect(planningAudit.planning_completion.status).toBe("complete");
    expect(planningAudit.source_records.every(row => row.source.publisher_id === publisherId)).toBe(true);
    const nativeRejections = await readLedgerParquet(
      join(recorded.inputs.outputRoot, result.files.harvest_rejections.files[0]!.path),
      "rejections", CandidateRejectionContract,
    );
    if (blocked === undefined || blocked.rejection === null) throw new Error("Missing actual blocked rejection");
    expect(nativeRejections.rows.map(held => held.row)).toContainEqual(blocked.rejection);
    const forged = structuredClone(result);
    const forgedBlocked = forged.evidence.harvest.articles.find(article =>
      article.rejection?.drop_reason === "BLOCKED_URL_MARKER");
    if (forgedBlocked?.rejection === null || forgedBlocked === undefined) throw new Error("Missing actual blocked rejection");
    forgedBlocked.rejection.canonical_url = innocentIdentity.canonical_url;
    expect(() => preparePlanningMetrics(forged, recorded.inputs)).toThrow("must match a configured host and path");
    const historyFixture = FeedHealthContract.schema.parse(await Bun.file(new URL(
      "../../../tests/fixtures/feed-ingest-plan/feed-health-row.json", import.meta.url,
    )).json());
    const reliability = await recordedPlan([source({ id: "alpha" }), source({ id: "gamma" })]);
    try {
      const day = "2026-10-20";
      const files = [];
      for (let index = 0; index < 4; index++) {
        const run = `${day}-${index + 1}`;
        const written = await persistLedger({
          ledger: "feed-health", registryEntry: reliability.inputs.registrations.feed_health,
          outputRoot: reliability.inputs.outputRoot, ledgerSettings: reliability.inputs.ledgerSettings,
          writerContext: {
            run_id: run, attempt: 1, job: "plan", shard: 0,
            pipeline_name: null, task_name: null, producer: "tests.reliability-history", git_sha: "a".repeat(40),
          },
          period: { tier: "raw", covers: day }, rowContract: FeedHealthContract,
          rows: ["alpha", "gamma"].map(id => FeedHealthContract.schema.parse({
            ...historyFixture, date: day, run_id: run, feed_id: id, checked_at: `${day}T12:00:0${index}Z`,
            outcome: id === "gamma" && index === 0 ? "transient" : "ok",
            status: id === "gamma" && index === 0 ? 503 : 200,
            items: id === "alpha" || index === 3 ? 1 : 0,
            endpoint_key: endpointKey(reliability.inputs.harvest.sources.find(source => source.id === id)!.url),
          })),
        });
        files.push(...written.files);
      }
      reliability.inputs.settings.inputs.feed_health_days = [{
        day, raw_files: files.map(file =>
          relative(reliability.directory, join(reliability.inputs.outputRoot, file.path)).replaceAll("\\", "/")),
      }];
      reliability.inputs.harvest.config.curate.source_reliability_penalty_enabled = false;
      const disabled = await runFeedPlan({ article_limit: 1, partition_strategy: "none" }, reliability.inputs, reliability.runtime);
      reliability.inputs.harvest.config.curate.source_reliability_penalty_enabled = true;
      const enabled = await runFeedPlan({ article_limit: 1, partition_strategy: "none" }, reliability.inputs, reliability.runtime);
      expect(disabled.evidence.curation.rows[0]!.candidate_id).toBe(deriveCandidateId(enabled.context.run_id, "gamma", 2));
      expect(enabled.evidence.curation.rows[0]!.candidate_id).toBe(deriveCandidateId(enabled.context.run_id, "alpha", 2));
      expect(enabled.evidence.curation.quality.map(row => row.components))
        .toEqual(disabled.evidence.curation.quality.map(row => row.components));
      expect(enabled.evidence.feed_history.history.reliability.availability).toBe("unavailable");
      expect(enabled.evidence.feed_history.sources.get("gamma")!.reliability).toMatchObject({
        success_fraction: 2 / 5, productive: 2, attempted: 5,
        production_factor: reliability.inputs.clock_config.collect.reliability_floor,
      });
      for (const article of enabled.evidence.curation.input) {
        expect(article.evidence.operational).toEqual({
          success_fraction: article.candidate.source_id === "gamma" ? 2 / 5 : 1,
          attempted: 5, window_days: reliability.inputs.clock_config.collect.reliability_window_days,
        });
      }
      expect(enabled.evidence.curation.carriers.groups.every(group => group.representative.candidate.source_id === "alpha")).toBe(true);
      const audit = await recordPlanningMetrics(enabled, reliability.inputs);
      expect(audit.planning_completion.status).toBe("complete");
      expect(audit.source_records.find(row => row.source_id === "gamma")).toMatchObject({
        history_success_fraction: 2 / 5, history_success_attempts: 5,
        history_window_days: reliability.inputs.clock_config.collect.reliability_window_days,
      });
      const dispatch = await readLedgerParquet(join(reliability.inputs.outputRoot, enabled.files.dispatches.files[0]!.path),
        "dispatches", DispatchContract);
      expect(dispatch.rows[0]!.row.selection.ratings).toEqual(enabled.evidence.curation.rows[0]!.ratings);
      expect(dispatch.rows[0]!.row.selection.ratings.source_reliability).toMatchObject({
        enabled: true, history: { success_fraction: 1, attempted: 5 },
        production_factor: 1, value: 0,
      });
    } finally { await reliability.close(); }
    const parity = await recordedPlan([
      source({ id: "sleeping" }), source({ id: "gone", url: "https://news.example/gone.xml" }),
      source({ id: "configured-retired", url: "https://news.example/retired.xml", status: "retired", retired_on: "2026-10-20" }),
      source({ id: "edited" }), source({ id: "inactive", status: "draft" }),
    ]);
    try {
      parity.runtime.clock = () => new Date("2026-10-24T00:00:00Z");
      parity.inputs.harvest = loadHarvestInputs({
        config: parity.inputs.harvest.config,
        taxonomy: { ...parity.inputs.harvest.taxonomy, ...parity.inputs.harvest.registry },
        sources: {
          feeds: parity.inputs.harvest.sources,
          retired: [source({ id: "curated-history-only", status: "retired", retired_on: "2026-10-20",
            vertical: "old-desk", kind: "old-kind", url: "https://news.example/curated-retired.xml" })],
        },
        extraction: { ...parity.inputs.harvest.extraction_settings, extract: parity.inputs.harvest.extraction },
      });
      const policy = parity.inputs.clock_config.collect;
      const threshold = policy.availability_strikes_before_rest;
      const day = "2026-10-23";
      const snapshot = (id: string) => sourceSnapshot(parity.inputs.harvest,
        parity.inputs.harvest.sources.find(source => source.id === id)!);
      const healthRows = Array.from({ length: threshold }, (_, index) =>
        ["sleeping", "gone"].map(id => FeedHealthContract.schema.parse({
          ...historyFixture, run_id: `${day}-${index + 1}`, feed_id: id,
          checked_at: `${day}T01:00:0${index}Z`,
          outcome: "permanent", status: id === "gone" ? 410 : 404, items: 0,
          endpoint_key: endpointKey(snapshot(id).feed_url),
        }))).flat();
      // A repeated result in one run must not become a second availability strike.
      healthRows.push(healthRows[0]!);
      const nativeWriter = {
        run_id: `${day}-99`, attempt: 1, job: "plan" as const, shard: 0,
        pipeline_name: null, task_name: null, producer: "tests.feed-history", git_sha: "a".repeat(40),
      };
      const writeHealth = async (rows: typeof healthRows, attempt = 1) => ({
        files: (await Promise.all([...new Set(rows.map(row => row.run_id))].map(run_id => persistLedger({
          ledger: "feed-health", registryEntry: parity.inputs.registrations.feed_health,
          outputRoot: parity.inputs.outputRoot, ledgerSettings: parity.inputs.ledgerSettings,
          writerContext: { ...nativeWriter, run_id, attempt }, period: { tier: "raw", covers: day },
          rowContract: FeedHealthContract, rows: rows.filter(row => row.run_id === run_id),
        })))).flatMap(result => result.files),
      });
      const health = await writeHealth(healthRows);
      const local = (files: readonly { path: string }[]) => files.map(file =>
        relative(parity.directory, join(parity.inputs.outputRoot, file.path)).replaceAll("\\", "/"));
      parity.inputs.settings.inputs.feed_health_days = [{ day, raw_files: local(health.files) }];
      const held = await runFeedPlan({}, parity.inputs, parity.runtime);
      for (const id of ["sleeping", "gone"]) {
        expect(held.evidence.harvest.feed_outcomes.find(row => row.source.source_id === id)).toMatchObject({
          fetch_status: "not_requested", parse_status: "not_attempted", rejection_reason: null,
          history: { lifecycle: "resting" },
        });
      }
      expect(parity.transport.requests.some(request => ["/gone.xml", "/retired.xml"].includes(request.url.pathname))).toBe(false);
      expect(held.evidence.harvest.feed_outcomes).toHaveLength(parity.inputs.harvest.sources.length);
      expect(held.evidence.harvest.feed_outcomes.some(row => row.source.source_id === "curated-history-only")).toBe(false);
      expect(held.evidence.harvest.feed_outcomes.find(row => row.source.source_id === "configured-retired")!.rejection_reason)
        .toBe("SOURCE_INACTIVE");
      expect(held.files).not.toHaveProperty("feed_retirements");
      expect(parity.inputs.registrations).not.toHaveProperty("feed_retirements");
      expect(held.evidence.harvest.feed_outcomes.find(row => row.source.source_id === "edited")!.fetch_status).toBe("success");
      expect(held.evidence.harvest.feed_outcomes.find(row => row.source.source_id === "inactive")!.rejection_reason).toBe("SOURCE_INACTIVE");
      expect(held.evidence.feed_history.sources.get("sleeping")!.strikes).toBe(threshold);
      expect(held.evidence.feed_history.sources.get("sleeping")!.reliability).toMatchObject({
        success_fraction: 0, attempted: threshold, productive: 0, production_factor: policy.reliability_floor,
      });
      expect(held.evidence.feed_history.history.health.availability).toBe("unavailable");
      expect(held.evidence.feed_history.sources.get("gone")!.lifecycle).toBe("resting");
      const healthAfter = await readLedgerParquet(join(parity.inputs.outputRoot, held.files.feed_health.files[0]!.path),
        "feed-health", FeedHealthContract);
      expect(healthAfter.rows.filter(({ row }) => row.outcome === "skipped").every(({ row }) =>
        row.target_attempted === false)).toBe(true);
      const read = (health_days = parity.inputs.settings.inputs.feed_health_days) => readFeedHistory({
        root: parity.directory, now: held.context.now, run_id: held.context.run_id,
        sources: parity.inputs.harvest.sources.map(source => sourceSnapshot(parity.inputs.harvest, source)),
        policy, health: parity.inputs.registrations.feed_health, health_days,
      });
      const sleepOnly = healthRows.filter(row => row.feed_id === "sleeping");
      const skips = Array.from({ length: threshold }, (_, index) => FeedHealthContract.schema.parse({
        ...sleepOnly[0]!, run_id: `${day}-${100 + index}`, outcome: "skipped", status: null, items: 0,
        target_attempted: false, checked_at: `${day}T02:00:0${index}Z`,
      }));
      const rested = await writeHealth([...sleepOnly, ...skips], 2);
      const resumed = await read([{ day, raw_files: [...local(health.files), ...local(rested.files)] }]);
      expect(resumed.sources.get("sleeping")).toMatchObject({
        lifecycle: "eligible", strikes: threshold, rested_runs: threshold, reliability: { attempted: threshold },
      });
      const permission = await writeHealth([FeedHealthContract.schema.parse({
        ...sleepOnly[0]!, run_id: `${day}-1000`, outcome: "robots_denied", status: null, items: 0,
        robots_outcome: "denied", target_attempted: false, checked_at: `${day}T03:00:00Z`,
      })]);
      const refused = await read([{ day, raw_files: [...local(health.files), ...local(permission.files)] }]);
      expect(refused.sources.get("sleeping")).toMatchObject({
        lifecycle: "resting", strikes: threshold, reliability: { attempted: threshold },
      });
      const recovery = await writeHealth([FeedHealthContract.schema.parse({
        ...healthRows.find(row => row.feed_id === "gone")!, run_id: `${day}-1000`, outcome: "ok",
        items: 1, status: 200, checked_at: `${day}T03:00:00Z`,
      })]);
      const recovered = await read([{ day, raw_files: [...local(health.files), ...local(recovery.files)] }]);
      expect(recovered.sources.get("gone")).toMatchObject({ lifecycle: "eligible", strikes: 0 });
      const unkeyed = await writeHealth(healthRows.filter(row => row.feed_id === "gone")
        .map(row => ({ ...row, endpoint_key: null })), 3);
      expect((await read([{ day, raw_files: local(unkeyed.files) }])).sources.get("gone")).toMatchObject({
        lifecycle: "resting",
      });
      const daily = await persistLedger({
        ledger: "item-health", registryEntry: parity.inputs.registrations.item_health,
        outputRoot: parity.inputs.outputRoot, ledgerSettings: parity.inputs.ledgerSettings,
        writerContext: { ...nativeWriter, run_id: `${held.context.date}-99` },
        period: { tier: "raw", covers: held.context.date },
        rowContract: { schema: DailyPublicationSchema, schemaVersion: DailyPublicationContract.schemaVersion },
        rows: [
          { date: held.context.date, url_key: deriveUrlKey("https://news.example/story"), source_id: "sleeping", outcome: "ok" },
          { date: held.context.date, url_key: deriveUrlKey("https://news.example/story"), source_id: "sleeping", outcome: "ok" },
          { date: held.context.date, url_key: deriveUrlKey("https://news.example/failed"), source_id: "sleeping", outcome: "failed" },
        ],
      });
      const published = await readDailyPublication({
        root: parity.directory, day: held.context.date, registration: parity.inputs.registrations.item_health,
        days: [{ day: held.context.date, raw_files: local(daily.files) }],
      });
      expect(published.counts.get("sleeping")).toBe(1);
      expect(published.history.availability).toBe("available");
      expect(DailyPublicationContract.schemaVersion).toBe("2026-10-20");
      expect(ItemHealthFailureProjectionContract.schemaVersion).toBe(DailyPublicationContract.schemaVersion);
      const future = await persistLedger({
        ledger: "item-health", registryEntry: parity.inputs.registrations.item_health,
        outputRoot: parity.inputs.outputRoot, ledgerSettings: parity.inputs.ledgerSettings,
        writerContext: { ...nativeWriter, run_id: `${held.context.date}-100`, producer: "tests.newer-item-health" },
        period: { tier: "raw", covers: held.context.date },
        rowContract: { schema: DailyPublicationSchema, schemaVersion: "2026-10-21" },
        rows: [{ date: held.context.date, url_key: deriveUrlKey("https://news.example/newer"),
          source_id: "sleeping", outcome: "ok" }],
      });
      await expect(readDailyPublication({
        root: parity.directory, day: held.context.date, registration: parity.inputs.registrations.item_health,
        days: [{ day: held.context.date, raw_files: local(future.files) }],
      })).rejects.toThrow("newer than its declared fields");
    } finally { await parity.close(); }
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
    expect(rejected.evidence.harvest.rejections.filter(row => row.drop_reason === "STALE_MAX_AGE_EXCEEDED").map(row => row.drop_reason))
      .toEqual(["STALE_MAX_AGE_EXCEEDED", "STALE_MAX_AGE_EXCEEDED"]);
    expect(rejected.evidence.screening.rejections).toEqual([]);
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
    expect(result.evidence.seen.evidence.availability).toBe("available");
    if (result.evidence.seen.evidence.availability !== "available") throw new Error("Seen history became unavailable");
    expect(result.evidence.seen.evidence.rows).toContainEqual(seen);
    expect(result.evidence.seen.global_absence).toBe("unavailable");
    const undated = result.evidence.screening.rejections.filter(row => row.url_key === seen.url_key);
    expect(undated.length).toBeGreaterThan(0);
    expect(undated.every(row => row.drop_reason === "STALE_MAX_AGE_EXCEEDED")).toBe(true);
    const assessment = result.events.flatMap(event => event.payload.kind === "candidate_decision"
      && event.stage === "screen-article-candidates" && event.payload.assessment.url_key === seen.url_key
      ? [event.payload.assessment] : [])[0]!;
    const expectedAge = (Date.parse("2026-10-21T23:59:59Z") - Date.parse(seen.first_seen_at)) / 3_600_000;
    expect(assessment.timing_basis).toBe("first_seen");
    expect(assessment.timing_at).toBe(seen.first_seen_at);
    expect(assessment.age_hours).toBe(expectedAge);
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
    const named = ["planning", "taxonomy", "sources", "extraction", "registrations", "watchlist"] as const;
    for (const field of named) {
      await writeFile(join(recorded.directory, paths[field]), await Bun.file(new URL(paths[field], originalRoot)).text());
    }
    await writeFile(join(configDirectory, "feed-ingest-plan-service.json"), JSON.stringify(authored));
    const loaded = await loadPlanInputs(recorded.directory);
    expect(loaded.harvest.config.version).toBe("2026-10-20");
    expect(loaded.registrations.source_runs).toEqual({
      name: "source-runs", family: "feed-ingest-plan", grain: "raw-and-compact",
      lifecycle_status: "active", prefix: ["feed-ingest-plan", "source-runs"],
    });
    expect(existsSync(join(recorded.directory, "backend"))).toBe(false);
    const registryPath = join(recorded.directory, paths.registrations);
    const registry = await Bun.file(registryPath).json();
    const familyIndex = registry.families.findIndex((family: { name: string }) => family.name === "feed-ingest-plan");
    const ledgerIndex = registry.families[familyIndex].ledgers.findIndex((ledger: { name: string }) => ledger.name === "source-runs");
    for (const invalid of ["paused", "retired", "family", "prefix", "grain", "missing", "duplicate"] as const) {
      const changed = structuredClone(registry);
      const family = changed.families[familyIndex];
      const ledger = family.ledgers[ledgerIndex];
      if (invalid === "paused" || invalid === "retired") family.lifecycle_status = invalid;
      if (invalid === "family") family.name = "other-family";
      if (invalid === "prefix") ledger.prefix = ["feed-ingest-plan", "other-ledger"];
      if (invalid === "grain") ledger.grain = "daily";
      if (invalid === "missing") family.ledgers.splice(ledgerIndex, 1);
      if (invalid === "duplicate") family.ledgers.push(structuredClone(ledger));
      await writeFile(registryPath, JSON.stringify(changed));
      await expect(loadPlanInputs(recorded.directory)).rejects.toThrow();
    }
    await writeFile(registryPath, JSON.stringify(registry));
    expect((await loadPlanInputs(recorded.directory)).registrations.source_runs).toEqual(loaded.registrations.source_runs);
  } finally { await recorded.close(); }
});

test("complete mixed native window creates real first sight; the next run retains its original clock", async () => {
  const recorded = await recordedPlan([source({ url: "https://news.example/article-failures.xml" })]);
  try {
    const window = await seenWindow(recorded, "https://news.example/earlier-story");
    const result = await runFeedPlan({}, recorded.inputs, recorded.runtime);
    expect(requiredSeenDays("2026-10-21T12:00:00Z", 90)).toHaveLength(91);
    expect(result.evidence.seen.absence_proof).toBe("within_configured_window");
    expect(result.evidence.seen.global_absence).toBe("unavailable");
    expect(result.evidence.seen.window).toMatchObject({
      from_day: "2026-10-19", through_day: "2026-10-21", required_day_count: 3,
      days: [{ status: "rows", tier: "daily" }, { status: "rows", tier: "raw" }, { status: "empty", tier: "raw" }],
    });
    const held = result.evidence.seen.evidence;
    if (held.availability !== "available") throw new Error("Real seen window was not available");
    expect(held.rows.find(row => row.url_key === deriveUrlKey("https://news.example/earlier-story"))!.first_seen_at)
      .toBe("2026-10-19T10:00:00Z");
    const key = deriveUrlKey("https://news.example/second");
    const created = result.evidence.seen.new_rows.find(row => row.url_key === key)!;
    expect(created).toMatchObject({ first_seen_at: "2026-10-21T12:00:00Z", first_seen_run: "2026-10-21-700" });
    expect(result.files.seen.status).toBe("written");
    const native = await readLedgerParquet(join(recorded.inputs.outputRoot, result.files.seen.files[0]!.path), "seen", {
      schema: SeenRowSchema, schemaVersion: "2026-08-31",
    });
    expect(native.rows.map(row => row.row)).toContainEqual(created);
    expect(result.evidence.screening.admitted.find(article => article.candidate.url_key === key)!.freshness)
      .toMatchObject({ timing_source: "first_seen", age_hours: 0, timing_at: created.first_seen_at });
    recorded.inputs.settings.inputs.seen_days[2]!.raw_files = result.files.seen.files.map(file =>
      window.local(join(recorded.inputs.outputRoot, file.path)));
    recorded.runtime.run_number = "701";
    recorded.runtime.clock = () => new Date("2026-10-21T13:00:00Z");
    const repeated = await runFeedPlan({}, recorded.inputs, recorded.runtime);
    expect(repeated.evidence.seen.new_rows).toEqual([]);
    expect(repeated.files.seen).toEqual({ status: "empty", files: [] });
    expect(repeated.evidence.screening.admitted.find(article => article.candidate.url_key === key)!.freshness)
      .toMatchObject({ timing_source: "first_seen", age_hours: 1, timing_at: created.first_seen_at });
  } finally { await recorded.close(); }
}, 30000);

test("missing or lost window days stay unavailable while current first sight preserves the earliest real row", async () => {
  const recorded = await recordedPlan([source({ url: "https://news.example/article-failures.xml" })]);
  try {
    const window = await seenWindow(recorded, "https://news.example/second");
    recorded.inputs.settings.inputs.seen_days[1] = { day: "2026-10-20" };
    let result = await runFeedPlan({}, recorded.inputs, recorded.runtime);
    expect(result.evidence.seen.absence_proof).toBe("unavailable");
    expect(result.evidence.seen.window!.days[1]!.status).toBe("missing");
    expect(result.evidence.seen.evidence.availability === "available"
      && result.evidence.seen.evidence.rows.find(row =>
        row.url_key === deriveUrlKey("https://news.example/second"))!.first_seen_at)
      .toBe("2026-10-19T10:00:00Z");
    const firstSight = result.evidence.seen.new_rows[0];
    if (firstSight === undefined) throw new Error("Missing current first-sight row");
    expect(firstSight).toMatchObject({
      first_seen_at: "2026-10-21T12:00:00Z", first_seen_run: "2026-10-21-700",
    });
    expect(result.files.seen.status).toBe("written");
    const native = await readLedgerParquet(join(recorded.inputs.outputRoot, result.files.seen.files[0]!.path), "seen", {
      schema: SeenRowSchema, schemaVersion: "2026-08-31",
    });
    expect(native.rows.map(row => row.row)).toContainEqual(firstSight);
    expect(result.evidence.seen.new_rows.map(row => row.url_key)).toContain(
      deriveUrlKey("https://news.example/not-found"),
    );
    expect(result.evidence.screening.rejections.some(row =>
      row.url_key === deriveUrlKey("https://news.example/second")
      && row.drop_reason === "STALE_MAX_AGE_EXCEEDED")).toBe(true);
    await writeFile(window.index, JSON.stringify({
      version: "2026-10-07", ledger: "seen", period: "daily",
      entries: [...window.entries, { covers: "2026-10-20", state: "lost", rows: 0, bytes: 0 }],
    }));
    recorded.inputs.settings.inputs.seen_days[1] = {
      day: "2026-10-20", indexes: { daily: window.local(window.index) },
    };
    recorded.inputs.settings.inputs.seen_days[2] = {
      day: "2026-10-21", raw_files: result.files.seen.files.map(file =>
        window.local(join(recorded.inputs.outputRoot, file.path))),
    };
    recorded.runtime.run_number = "702";
    result = await runFeedPlan({}, recorded.inputs, recorded.runtime);
    expect(result.evidence.seen.absence_proof).toBe("unavailable");
    expect(result.evidence.seen.window!.days[1]!.status).toBe("lost");
    expect(result.evidence.seen.new_rows).toEqual([]);
    expect(result.files.seen).toEqual({ status: "empty", files: [] });
  } finally { await recorded.close(); }
}, 30000);

test("window bounds, ordering and duplicate current-day inputs fail before fetching", async () => {
  const recorded = await recordedPlan();
  try {
    recorded.inputs.clock_config.collect.seen_window_days = 2;
    expect(requiredSeenDays("2026-10-21T12:00:00Z", recorded.inputs.clock_config.collect.seen_window_days))
      .toEqual(["2026-10-19", "2026-10-20", "2026-10-21"]);
    for (const days of [
      [{ day: "2026-10-22", raw_files: [] }],
      [{ day: "2026-10-18", raw_files: [] }],
      [{ day: "2026-10-21", raw_files: [] }, { day: "2026-10-21", raw_files: [] }],
      [{ day: "2026-10-21", raw_files: [] }, { day: "2026-10-20", raw_files: [] }],
    ]) {
      recorded.inputs.settings.inputs.seen_days = days;
      await expect(runFeedPlan({}, recorded.inputs, recorded.runtime)).rejects.toThrow("seen_days");
    }
    recorded.runtime.clock = () => new Date("2026-10-21T12:00:00Z");
    recorded.inputs.settings.inputs.seen_days = [];
    const future = await persistLedger({
      ledger: "seen", registryEntry: recorded.inputs.registrations.seen, outputRoot: recorded.inputs.outputRoot,
      ledgerSettings: recorded.inputs.ledgerSettings,
      rowContract: { schema: SeenRowSchema, schemaVersion: "2026-08-31" },
      writerContext: {
        run_id: "2026-10-21-1", attempt: 1, job: "plan", shard: 0,
        pipeline_name: null, task_name: null, producer: "tests.seen-window", git_sha: "a".repeat(40),
      },
      period: { tier: "raw", covers: "2026-10-21" },
      rows: [SeenRowSchema.parse({
        version: "2026-08-31", url_key: deriveUrlKey("https://news.example/future"),
        first_seen_at: "2026-10-21T12:00:01Z", first_seen_run: "2026-10-21-1",
      })],
    });
    recorded.inputs.settings.inputs.seen_files = future.files.map(file =>
      relative(recorded.directory, join(recorded.inputs.outputRoot, file.path)).replaceAll("\\", "/"));
    await expect(runFeedPlan({}, recorded.inputs, recorded.runtime)).rejects.toThrow("captured run clock");
    expect(recorded.transport.requests).toHaveLength(0);
  } finally { await recorded.close(); }
});

test("a genuine seen-write failure cannot turn an absent address into first-sight evidence", async () => {
  const recorded = await recordedPlan([source({ url: "https://news.example/article-failures.xml" })]);
  try {
    recorded.inputs.clock_config.collect.seen_window_days = 0;
    recorded.inputs.settings.inputs.seen_days = [{ day: "2026-10-21", raw_files: [] }];
    const raw = join(recorded.inputs.outputRoot, "raw");
    await mkdir(raw, { recursive: true });
    await writeFile(join(raw, "seen"), "A file cannot be a first-sight ledger directory.");
    await expect(runFeedPlan({}, recorded.inputs, recorded.runtime)).rejects.toThrow();
    expect(recorded.events.some(event => event.stage === "screen-article-candidates")).toBe(false);
  } finally { await recorded.close(); }
}, 30000);

test("retired historical source has a genuine inactive outcome without a current vertical policy", async () => {
  const recorded = await recordedPlan([
    source({ id: "historical-news", status: "retired", retired_on: "2026-10-19",
      vertical: "historical-vertical", kind: "historical-kind" }),
  ]);
  try {
    const result = await runFeedPlan({}, recorded.inputs, recorded.runtime);
    expect(recorded.transport.requests).toHaveLength(0);
    const outcome = result.events.find(event => event.payload.kind === "feed_outcome")!;
    expect(outcome.payload.kind === "feed_outcome" && outcome.payload.source.vertical).toBe("historical-vertical");
    expect(outcome.payload.kind === "feed_outcome" && outcome.payload.rejection_reason).toBe("SOURCE_INACTIVE");
    expect(outcome.policy.max_age_hours).toBe(recorded.inputs.harvest.config.triage.max_age_hours);
    expect(outcome.policy.config_sha256).toBe(result.evidence.harvest.inputs.config_sha256);
    expect(result.files.dispatches).toEqual({ status: "empty", files: [] });
  } finally { await recorded.close(); }
}, 30000);
