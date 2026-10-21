/** Does real candidate screening preserve evidence and seal exact typed rejections? */
import { expect, test } from "bun:test";
import { mkdtemp, readFile, readdir, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { tableFromIPC } from "apache-arrow";
import initializeWasm, { readMetadata, readParquet } from "parquet-wasm/esm";
import { z } from "zod";
import {
  CandidateRejectionRecordSchema, DropReasonSchema, FeedIngestCandidateSchema,
  RowIdentitySchema, SourceFormSchema, WriterIdentitySchema, deriveCandidateId,
} from "@idhazh/common-contracts";
import { loadPlanningConfig } from "../src/config/resolve-policy";
import { harvestFeeds, HarvestObservationSchema } from "@idhazh/feed-ingest-plan/harvest-feeds";
import { screenArticleCandidates } from "../src/screen-article-candidates/triage-gates";
import type { RejectionLedgerContext, ScreeningInput } from "../src/screen-article-candidates/triage-gates";
import { indexSeenEvidence, SeenRowSchema } from "../src/screen-article-candidates/seen-evidence";
import {
  RecordedTransport, inputs as harvestInputs, readRecordings, source as recordedSource,
} from "./harvest-recordings";

const fixtureUrl = new URL("../../../tests/fixtures/feed-ingest-plan/screening-cases.json", import.meta.url);
const seenUrl = new URL("../../../tests/fixtures/feed-ingest-plan/seen-evidence.json", import.meta.url);
const CaseSchema = z.object({
  name: z.string(), form: SourceFormSchema.optional(), words: z.number().int().positive().optional(),
  status: z.number().nullable().optional(), paywall: z.boolean().optional(),
  categories: z.array(z.string()).optional(), published_at: z.string().nullable().optional(),
  seen: z.enum(["old", "new"]).optional(), reason: DropReasonSchema.nullable(),
  details: z.record(z.string(), z.number().nullable()).optional(),
  age: z.number().nullable().optional(), clock: z.enum(["published_at", "first_seen", "unknown"]).optional(),
  bonus: z.number().optional(),
});

async function inputs() {
  const fixture = await Bun.file(fixtureUrl).json();
  const seenFixture = await Bun.file(seenUrl).json();
  const candidate = FeedIngestCandidateSchema.parse(fixture.candidate);
  expect(candidate.word_count).toBe(candidate.article_text.trim().split(/\s+/u).length);
  const planning = loadPlanningConfig(
    await Bun.file(new URL("../../../config/feed-ingest-plan.json", import.meta.url)).json(),
    await Bun.file(new URL("../../../config/taxonomy.json", import.meta.url)).json(),
  );
  const input: ScreeningInput = {
    candidates: [candidate],
    observations: { [candidate.candidate_id]: HarvestObservationSchema.parse(fixture.observation) },
    seen: { availability: "unavailable" },
    planning,
    clock_config: await Bun.file(new URL("../../../config/idhazh.json", import.meta.url)).json(),
    run: { now: fixture.now, run_id: candidate.run_id, correlation_id: candidate.correlation_id, overrides: {} },
  };
  const observation = HarvestObservationSchema.parse(fixture.observation);
  return {
    input,
    candidate,
    observation,
    cases: CaseSchema.array().parse(fixture.cases),
    seen: { old: SeenRowSchema.parse(seenFixture.rows.old), new: SeenRowSchema.parse(seenFixture.rows.new) },
  };
}

async function withLedger(action: (ledger: RejectionLedgerContext, data: Awaited<ReturnType<typeof inputs>>) => Promise<void>) {
  const data = await inputs();
  const root = await mkdtemp(join(tmpdir(), "feed-screening-"));
  const ledger: RejectionLedgerContext = {
    outputRoot: root,
    writerContext: WriterIdentitySchema.parse({
      run_id: data.input.run.run_id, attempt: 1, job: null, pipeline_name: "plan",
      task_name: "screen-article-candidates", shard: 0, producer: "tests.feed-screening", git_sha: "b".repeat(40),
    }),
    registryEntry: {
      name: "rejections", family: "feed-ingest-plan", grain: "raw-and-compact",
      lifecycle_status: "active", prefix: data.input.planning.config.seal.rejections_prefix,
    },
    ledgerSettings: {
      format: "parquet", compression_raw: data.input.planning.config.seal.compression, compression_compact: "zstd",
    },
  };
  try {
    await action(ledger, data);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
}

test("recorded word, blocking, precedence and exact freshness boundaries", async () => {
  await withLedger(async (ledger, { input, candidate, cases, seen, observation }) => {
    for (const entry of cases) {
      const words = candidate.article_text.split(/\s+/u).slice(0, entry.words ?? candidate.word_count);
      const offered = FeedIngestCandidateSchema.parse({
        ...candidate, source: { ...candidate.source, form: entry.form ?? candidate.source.form },
        word_count: words.length, article_text: words.join(" "),
        categories: entry.categories ?? candidate.categories,
        published_at: entry.published_at === undefined ? candidate.published_at : entry.published_at,
      });
      const result = await screenArticleCandidates({
        ...input, candidates: [offered],
        observations: { [offered.candidate_id]: {
          ...observation,
          http_status: entry.status === undefined ? 200 : entry.status, paywall: entry.paywall ?? false,
        } },
        seen: entry.seen === undefined ? input.seen : { availability: "available", rows: [seen[entry.seen]] },
      }, ledger);
      expect(result.rejections[0]?.drop_reason ?? null, entry.name).toBe(entry.reason);
      expect(result.admitted.length + result.rejections.length, entry.name).toBe(1);
      if (entry.details) expect(result.rejections[0]?.details, entry.name).toMatchObject(entry.details);
      if (entry.age !== undefined) expect(result.admitted[0]?.freshness.age_hours, entry.name).toBe(entry.age);
      if (entry.clock !== undefined) expect(result.admitted[0]?.freshness.timing_source, entry.name).toBe(entry.clock);
      if (entry.bonus !== undefined) expect(result.admitted[0]?.freshness.recency_bonus, entry.name).toBe(entry.bonus);
      if (entry.reason === "STALE_MAX_AGE_EXCEEDED" && entry.name === "one second past cutoff") {
        expect(result.rejections[0]?.details.age_hours).toBeCloseTo(24 + 1 / 3600, 10);
      }
    }
  });
});

test("global, vertical and run policies change only their declared gates", async () => {
  await withLedger(async (ledger, { input, candidate }) => {
    const change = async (vertical: string, words: number, publishedAt: string, overrides = {}) => {
      const offered = FeedIngestCandidateSchema.parse({
        ...candidate, vertical, source: { ...candidate.source, vertical },
        word_count: words, article_text: candidate.article_text.split(/\s+/u).slice(0, words).join(" "),
        published_at: publishedAt,
      });
      return screenArticleCandidates({
        ...input, candidates: [offered], run: { ...input.run, overrides },
      }, ledger);
    };
    input.planning = loadPlanningConfig({
      ...input.planning.config,
      vertical_overrides: { world: { triage: { min_words_article: 190, min_words_abstract: 70, max_age_hours: 12 } } },
    }, input.planning.taxonomy);
    expect((await change("world", 180, "2026-10-21T11:00:00Z")).rejections[0]?.details.words_required).toBe(190);
    expect((await change("energy", 180, "2026-10-21T11:00:00Z")).admitted).toHaveLength(1);
    const abstract = FeedIngestCandidateSchema.parse({
      ...candidate, source: { ...candidate.source, form: "abstract" },
      word_count: 60, article_text: candidate.article_text.split(/\s+/u).slice(0, 60).join(" "),
    });
    expect((await screenArticleCandidates({ ...input, candidates: [abstract] }, ledger)).rejections[0]?.details.words_required).toBe(70);
    expect((await change("world", 200, "2026-10-20T18:00:00Z")).rejections[0]?.drop_reason).toBe("STALE_MAX_AGE_EXCEEDED");
    const admitted = await change("world", 200, "2026-10-20T18:00:00Z", { freshness_hours: 18 });
    expect(admitted.admitted[0]?.freshness.recency_bonus).toBe(0.3);
    expect(admitted.admitted[0]?.policy.triage).toMatchObject({ max_age_hours: 18, recency_half_life_hours: 18 });
    expect((await change("world", 200, "2026-10-20T18:00:00Z", { freshness_hours: 17.99 })).rejections).toHaveLength(1);
    expect(input.planning.config.vertical_overrides.world?.triage?.max_age_hours).toBe(12);
    input.planning.config.triage.min_words_article = 200;
    expect((await change("energy", 199, "2026-10-21T11:00:00Z")).rejections[0]?.details.words_required).toBe(200);
    input.planning = loadPlanningConfig({
      ...input.planning.config, vertical_overrides: { oceans: { triage: { min_words_article: 180 } } },
    }, { verticals: [...input.planning.taxonomy.verticals, { id: "oceans" }] });
    expect((await change("oceans", 180, "2026-10-21T11:00:00Z")).admitted).toHaveLength(1);
    expect((await change("world", 180, "2026-10-21T11:00:00Z")).rejections[0]?.details.words_required).toBe(200);
    expect((await change("oceans", 180, "2026-10-21T11:30:00Z", { freshness_hours: 0.5 })).admitted).toHaveLength(1);
  });
});

test("kind relabel and unavailable observations do not invent eligibility rules", async () => {
  await withLedger(async (ledger, { input, candidate, observation }) => {
    for (const kind of ["reporting", "newly-configured-kind"]) {
      const offered = FeedIngestCandidateSchema.parse({ ...candidate, source: { ...candidate.source, kind, tier: 9 } });
      const result = await screenArticleCandidates({ ...input, candidates: [offered], observations: {} }, ledger);
      expect(result.admitted[0]?.candidate).toEqual(offered);
      expect(result.admitted[0]?.observation).toBeNull();
      expect(result.admitted[0]?.seen_availability).toBe("unavailable");
    }
    const result = await screenArticleCandidates({
      ...input, observations: { [candidate.candidate_id]: {
        ...observation, http_status: null, paywall: null, paywall_evidence: "not-observed",
      } },
    }, ledger);
    expect(result.admitted[0]?.observation).toEqual({
      ...observation, http_status: null, paywall: null, paywall_evidence: "not-observed",
    });
  });
});

test("configured HTTP/category lists and future tolerance are read, not hardcoded", async () => {
  await withLedger(async (ledger, { input, candidate, seen, observation }) => {
    input.planning.config.triage.blocked_http_statuses = [418];
    input.planning.config.harvest.blocked_categories = ["science"];
    input.observations = { [candidate.candidate_id]: { ...observation, http_status: 403, paywall: false } };
    expect((await screenArticleCandidates(input, ledger)).rejections[0]?.drop_reason).toBe("CATEGORY_EXCLUDED");
    input.planning.config.harvest.blocked_categories = [];
    expect((await screenArticleCandidates(input, ledger)).admitted).toHaveLength(1);
    input.observations = { [candidate.candidate_id]: { ...observation, http_status: 418, paywall: null } };
    expect((await screenArticleCandidates(input, ledger)).rejections[0]?.details.http_status).toBe(418);
    input.observations = {};
    input.candidates = [{ ...candidate, published_at: "2026-10-21T14:00:00Z" }];
    input.seen = { availability: "available", rows: [seen.old] };
    input.clock_config = { collect: { max_future_hours: 1 } };
    expect((await screenArticleCandidates(input, ledger)).rejections[0]?.details.age_hours).toBe(50);
    input.clock_config.collect.max_future_hours = 2;
    expect((await screenArticleCandidates(input, ledger)).admitted[0]?.freshness.timing_source).toBe("published_at");
  });
});

test("repeated undated and far-future fetches keep the persisted first sight", async () => {
  await withLedger(async (ledger, { input, candidate, seen }) => {
    for (const published_at of [null, "2026-11-01T00:00:00Z"]) {
      for (const run_id of ["2026-10-21-123", "2026-10-21-124"]) {
        const candidate_id = deriveCandidateId(run_id, candidate.source_id, candidate.entry_ordinal);
        const result = await screenArticleCandidates({
          ...input, candidates: [{
            ...candidate, run_id, candidate_id, correlation_id: run_id, published_at,
            fetched_at: run_id.endsWith("-123") ? "2026-10-21T09:00:00Z" : "2026-10-21T12:00:00Z",
          }],
          observations: {},
          run: { ...input.run, run_id, correlation_id: run_id },
          seen: { availability: "available", rows: [seen.old] },
        }, { ...ledger, writerContext: { ...ledger.writerContext, run_id } });
        expect(result.rejections[0]?.details.age_hours).toBe(50);
      }
    }
    const missing = { ...input, candidates: [{ ...candidate, published_at: null }] };
    const unknown = await screenArticleCandidates(missing, ledger);
    const empty = await screenArticleCandidates({ ...missing, seen: { availability: "available", rows: [] } }, ledger);
    expect(unknown.admitted[0]?.freshness).toEqual(empty.admitted[0]?.freshness);
    expect(unknown.admitted[0]?.seen_availability).toBe("unavailable");
    expect(empty.admitted[0]?.seen_availability).toBe("available");
    const differentUrl = await screenArticleCandidates({
      ...missing, seen: { availability: "available", rows: [{ ...seen.old, url_key: "a".repeat(64) }] },
    }, ledger);
    expect(differentUrl.admitted[0]?.freshness.timing_source).toBe("unknown");
  });
});

test("the recorded existing SeenRow fields validate without assuming a new payload version", async () => {
  const fixture = await Bun.file(seenUrl).json();
  expect(Object.keys(SeenRowSchema.shape)).toEqual(fixture.fields);
  expect(SeenRowSchema.parse(fixture.rows.old)).toEqual(fixture.rows.old);
  const row = SeenRowSchema.parse(fixture.rows.old);
  expect(() => indexSeenEvidence({ availability: "available", rows: [row, { ...row, first_seen_run: "2026-10-19-2" }] })).toThrow("conflicting");
  expect(indexSeenEvidence({ availability: "available", rows: [row, row] }).size).toBe(1);
  expect(() => SeenRowSchema.parse({ ...row, first_seen_run: null })).toThrow("first_seen_run");
  expect(() => SeenRowSchema.parse({ ...row, first_seen_at: "2026-02-30T00:00:00Z" })).toThrow("first_seen_at");
  expect(() => SeenRowSchema.parse({ ...row, first_seen_at: "2026-10-19T10:00:00+02:00" })).toThrow("first_seen_at");
});

test("invalid overrides, config, observations and batch identities fail by name before writing", async () => {
  await withLedger(async (ledger, { input, candidate, observation }) => {
    for (const freshness_hours of [0, -1, NaN, Infinity, "12", null]) {
      await expect(screenArticleCandidates({
        ...input, run: { ...input.run, overrides: JSON.parse(JSON.stringify({ freshness_hours })) },
      }, ledger)).rejects.toThrow("freshness_hours");
    }
    for (const freshness_hours of [NaN, Infinity]) {
      await expect(screenArticleCandidates({
        ...input, run: { ...input.run, overrides: { freshness_hours } },
      }, ledger)).rejects.toThrow("freshness_hours");
    }
    await expect(screenArticleCandidates({
      ...input, observations: { [candidate.candidate_id]: { ...observation, http_status: 600, paywall: false } },
    }, ledger)).rejects.toThrow("http_status");
    await expect(screenArticleCandidates({
      ...input, observations: { [deriveCandidateId(candidate.run_id, candidate.source_id, 99)]: observation },
    }, ledger)).rejects.toThrow("observations.");
    await expect(screenArticleCandidates({
      ...input, candidates: [candidate, candidate],
    }, ledger)).rejects.toThrow("candidate_id");
    await expect(screenArticleCandidates({
      ...input, run: { ...input.run, correlation_id: "another-run" },
    }, ledger)).rejects.toThrow("correlation_id");
    await expect(screenArticleCandidates({
      ...input, clock_config: { collect: { max_future_hours: NaN } },
    }, ledger)).rejects.toThrow("max_future_hours");
    await expect(screenArticleCandidates({
      ...input, run: { ...input.run, now: "2026-02-30T12:00:00Z" },
    }, ledger)).rejects.toThrow("now");
    await expect(screenArticleCandidates({
      ...input, planning: {
        ...input.planning, config: {
          ...input.planning.config,
          triage: { ...input.planning.config.triage, min_words_article: 0 },
        },
      },
    }, ledger)).rejects.toThrow("min_words_article");
    expect(await readdir(ledger.outputRoot)).toEqual([]);
  });
});

function normalizeArrow(value: unknown): unknown {
  if (typeof value === "bigint") return Number(value);
  if (Array.isArray(value)) return value.map(normalizeArrow);
  if (typeof value !== "object" || value === null) return value;
  if ("toJSON" in value && typeof value.toJSON === "function") return normalizeArrow(value.toJSON());
  return Object.fromEntries(Object.entries(value).map(([key, child]) => [key, normalizeArrow(child)]));
}

test("real shared writer Parquet preserves rejection details, identity and UTC run date", async () => {
  await withLedger(async (ledger, { input, candidate, seen, observation }) => {
    const offers = [
      { ...candidate, fetched_at: "2026-10-20T23:59:59Z", date: "2026-10-20", word_count: 1, article_text: "Researchers" },
      { ...candidate, categories: ["video"] },
      { ...candidate, published_at: null },
      { ...candidate },
    ];
    input.candidates = offers.map((offer, entry_ordinal) => ({
      ...offer, entry_ordinal, candidate_id: deriveCandidateId(candidate.run_id, candidate.source_id, entry_ordinal),
    }));
    input.seen = { availability: "available", rows: [seen.old] };
    const blockedId = input.candidates[3]?.candidate_id;
    if (!blockedId) throw new Error("expected the HTTP-blocked fixture candidate");
    input.observations = {
      ...input.observations, [blockedId]: { ...observation, candidate_id: blockedId, http_status: 403, paywall: null },
    };
    const result = await screenArticleCandidates(input, ledger);
    expect(result.rejections.map(row => row.drop_reason)).toEqual([
      "STUB_CONTENT", "CATEGORY_EXCLUDED", "STALE_MAX_AGE_EXCEEDED", "PAYWALL_OR_BLOCKED",
    ]);
    expect(result.sealing.status).toBe("written");
    const file = result.sealing.files[0];
    if (!file) throw new Error("expected a sealed rejection file");
    expect(file.path).toMatch(/^raw\/feed-ingest-plan\/rejections\/2026\/10\/21\/[a-f0-9-]+\.parquet$/);
    const bytes = await readFile(join(ledger.outputRoot, ...file.path.split("/")));
    await initializeWasm();
    const metadata = readMetadata(bytes);
    const footer = metadata.fileMetadata();
    const values = new Map([...footer.keyValueMetadata()].map(([key, value]) => [String(key), String(value)]));
    expect(Number(footer.numRows())).toBe(4);
    footer.free();
    metadata.free();
    expect(values.get("writer")).toBe("idhazh_typescript.ledger.parquet");
    expect(values.get("ledger")).toBe("rejections");
    expect(values.get("covers")).toBe("2026-10-21");
    const table = tableFromIPC(readParquet(bytes).intoIPCStream());
    const stored = table.toArray().map(row => z.record(z.string(), z.unknown()).parse(normalizeArrow(row)));
    expect(stored).toHaveLength(4);
    const identityFields = new Set(Object.keys(RowIdentitySchema.shape));
    for (const [index, row] of stored.entries()) {
      const payload = Object.fromEntries(Object.entries(row).filter(([key]) => !identityFields.has(key)));
      const expected = result.rejections[index];
      if (!expected) throw new Error(`missing expected rejection at ${index}`);
      expect(CandidateRejectionRecordSchema.parse(payload)).toEqual(expected);
      const identity = RowIdentitySchema.parse(Object.fromEntries(
        Object.entries(row).filter(([key]) => identityFields.has(key)),
      ));
      expect(identity).toMatchObject({ ledger: "rejections", covers: "2026-10-21", run_id: input.run.run_id, unit_id: file.unit_id });
    }
    expect(result.rejections[0]).toMatchObject({
      candidate_id: candidate.candidate_id, url_key: candidate.url_key, canonical_url: candidate.canonical_url,
      details: { words_found: 1, words_required: 180 }, rejected_at: input.run.now,
    });
  });
});

test("public harvesting observations compose with screening without duplicating terminal harvest failures", async () => {
  await withLedger(async (ledger, { input }) => {
    const transport = new RecordedTransport(await readRecordings());
    const loaded = await harvestInputs([recordedSource()]);
    const harvested = await harvestFeeds(loaded, {
      writer: { ...ledger.writerContext, task_name: "harvest-feeds" },
      correlation_id: input.run.correlation_id,
      clock: () => new Date(input.run.now),
    }, ledger, { transport, resolve: transport.resolve });
    const observations = Object.fromEntries(harvested.articles.flatMap(article =>
      article.candidate === null ? [] : [[article.candidate.candidate_id, article.observation]],
    ));
    const screened = await screenArticleCandidates({
      ...input, candidates: harvested.candidates, observations,
      planning: loadPlanningConfig({
        ...loaded.config, triage: { ...loaded.config.triage, min_words_article: 100 },
      }, input.planning.taxonomy),
    }, ledger);
    expect(screened.admitted.length + screened.rejections.length).toBe(harvested.candidates.length);
    expect(screened.admitted.length).toBeGreaterThan(0);
    const ids = new Set(harvested.rejections.map(row => row.candidate_id));
    expect(screened.rejections.every(row => !ids.has(row.candidate_id))).toBe(true);
    for (const entry of screened.admitted) {
      const observation = observations[entry.candidate.candidate_id];
      const candidate = harvested.candidates.find(row => row.candidate_id === entry.candidate.candidate_id);
      if (!observation || !candidate) throw new Error("screening admitted an unharvested candidate");
      expect(entry.observation).toEqual(observation);
      expect(entry.candidate).toEqual(candidate);
    }
    expect(harvested.rejections.some(row => row.drop_reason === "MISSING_REQUIRED_FIELDS")).toBe(true);
  });
});

test("failed, invalid or paused rejection writes cannot report successful sealing", async () => {
  await withLedger(async (ledger, { input, candidate }) => {
    const empty = await screenArticleCandidates({ ...input, candidates: [], observations: {} }, ledger);
    expect(empty).toEqual({ admitted: [], rejections: [], sealing: { status: "empty", files: [] } });
    expect(await readdir(ledger.outputRoot)).toEqual([]);
    input.candidates = [{ ...candidate, word_count: 1, article_text: "Researchers" }];
    await expect(screenArticleCandidates(input, {
      ...ledger, registryEntry: { ...ledger.registryEntry, lifecycle_status: "paused" },
    })).rejects.toThrow("sealing did not complete");
    await expect(screenArticleCandidates(input, {
      ...ledger, ledgerSettings: { ...ledger.ledgerSettings, format: "json" },
    })).rejects.toThrow("Parquet");
    await expect(screenArticleCandidates(input, {
      ...ledger, registryEntry: { ...ledger.registryEntry, prefix: ["feed-ingest-plan", "dispatches"] },
    })).rejects.toThrow("registryEntry.prefix");
    await expect(screenArticleCandidates(input, {
      ...ledger, writerContext: { ...ledger.writerContext, run_id: "2026-10-21-999" },
    })).rejects.toThrow("writerContext.run_id");
    const blocked = join(ledger.outputRoot, "blocked-root");
    await writeFile(blocked, "not a directory");
    await expect(screenArticleCandidates(input, { ...ledger, outputRoot: blocked })).rejects.toThrow();
    expect(await Bun.file(blocked).text()).toBe("not a directory");
    expect(await readdir(ledger.outputRoot)).toEqual(["blocked-root"]);
  });
});
