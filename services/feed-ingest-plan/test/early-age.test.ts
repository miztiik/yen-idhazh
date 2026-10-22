/** Do expired feed entries stop before page I/O while preserving exact audit membership? */
import { expect, test } from "bun:test";
import { mkdir, rm } from "node:fs/promises";
import { join } from "node:path";
import { CandidateRejectionContract, deriveCandidateId } from "@idhazh/common-contracts";
import { harvestFeeds } from "../src/harvest-feeds/harvest-pool";
import { readLedgerParquet } from "../src/read-ledger-history/read-parquet";
import { derivePlanningPopulation, readPlanningHistory } from "../src/metrics/planning-populations";
import { selectCompleteAttempt } from "../src/read-ledger-history/complete-attempt";
import { main } from "../src/index";
import { runFeedPlan } from "../src/run-feed-plan";
import { preparePlanningMetrics } from "../src/metrics/metrics-recorder";
import { recordedPlan, namedPlanningFiles } from "./plan-recordings";
import { context, destination, inputs, readRecordings, RecordedTransport, source } from "./harvest-recordings";
import { tmpdir } from "node:os";
import { mkdtemp } from "node:fs/promises";

function feed(items: { title?: string; path: string; date: string | null }[]) {
  return `<rss version="2.0"><channel><title>Recorded age decisions</title>${items.map(item =>
    `<item>${item.title === undefined ? "" : `<title>${item.title}</title>`}<link>https://news.example/${item.path}</link>${
      item.date === null ? "" : `<pubDate>${item.date}</pubDate>`}</item>`).join("")}</channel></rss>`;
}

test("preflight uses the configured age override, strict boundary and future tolerance without fetching expired pages", async () => {
  const root = await mkdtemp(join(tmpdir(), "early-age-"));
  try {
    const recordings = await readRecordings();
    const run = { ...context(), clock: () => new Date("2026-10-22T12:00:00Z"), overrides: { freshness_hours: 12 } };
    run.writer = { ...run.writer, run_id: "2026-10-22-700" };
    const items = [
      { title: "Expired", path: "stale", date: "2026-10-21T23:59:59Z" },
      { title: "Boundary", path: "boundary", date: "2026-10-22T00:00:00Z" },
      { title: "Undated", path: "undated", date: null },
      { title: "Beyond future tolerance", path: "future", date: "2026-10-23T00:00:00Z" },
      { title: "Within future tolerance", path: "near-future", date: "2026-10-22T13:00:00Z" },
      { path: "untitled-old", date: "2026-10-20T00:00:00Z" },
    ];
    recordings.bodies.rss = feed(items);
    for (const item of items.slice(1)) recordings.responses[`https://news.example/${item.path}`] = [
      { status: 200, fixture: "article" },
    ];
    const transport = new RecordedTransport(recordings);
    const result = await harvestFeeds(await inputs(), run, destination(root), { transport, resolve: transport.resolve });
    expect(transport.requests.some(request => request.url.pathname === "/stale")).toBe(false);
    expect(result.rejections.map(row => row.drop_reason)).toEqual(["STALE_MAX_AGE_EXCEEDED"]);
    const early = result.articles[0]!;
    if (early.rejection === null) throw new Error("Expected expired entry rejection");
    expect(early.rejection?.details.age_hours).toBeCloseTo(12 + 1 / 3600, 8);
    expect(early.rejection?.details.max_age_hours).toBe(12);
    expect(early.observation).toMatchObject({
      extraction: "not-attempted", http_status: null, paywall: null, robots: null,
      preflight_freshness: { timing_source: "published_at", timing_at: items[0]!.date },
    });
    expect(result.candidates.map(row => row.entry_ordinal)).toEqual([1, 2, 3, 4, 5]);
    expect(result.candidates.every(row => row.candidate_id === deriveCandidateId(run.writer.run_id, row.source_id, row.entry_ordinal))).toBe(true);
    expect(result.feed_outcomes[0]).toMatchObject({ parsed_count: 6, harvested_count: 5 });
    const written = result.rejection_files.files[0]!;
    expect((await readLedgerParquet(join(root, written.path), "rejections", CandidateRejectionContract)).rows[0]?.row)
      .toEqual(early.rejection);
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("real planning records early losses once and reproduces freshness loss from native history", async () => {
  const fixture = await recordedPlan([source(), source({ id: "current", url: "https://atom.example/feed.xml" })]);
  try {
    fixture.transport.recordings.bodies.rss = feed([
      { title: "Expired first", path: "stale-one", date: "2026-10-19T10:00:00Z" },
      { title: "Expired second", path: "stale-two", date: "2026-10-19T11:00:00Z" },
    ]);
    await mkdir(fixture.inputs.outputRoot, { recursive: true });
    const summary = await main(["--cli"], { inputs: fixture.inputs, runtime: fixture.runtime, output: () => {} });
    if (!("planning_complete" in summary)) throw new Error("Expected completed recorded planning");
    expect(summary.planning_complete).toBe(true);
    expect(summary.audited_complete).toBe(false);
    expect(summary.first_sight.created_count).toBe(0);
    expect(fixture.transport.requests.some(request => request.url.pathname.startsWith("/stale-"))).toBe(false);
    const history = await readPlanningHistory(namedPlanningFiles(summary, fixture.inputs.outputRoot));
    const attempt = selectCompleteAttempt(history).selected;
    if (attempt === null) throw new Error("Missing verified recorded attempt");
    const population = derivePlanningPopulation(attempt);
    expect(population.stages.input.map(row => row.source_id).sort()).toEqual(["current", "current", "recorded-news", "recorded-news"]);
    expect(population.stages.freshness.map(row => row.source_id)).toEqual(["current", "current"]);
    const old = summary.source_records?.find(row => row.source_id === "recorded-news");
    expect(old).toMatchObject({ parsed_count: 2, harvested_count: 0, fresh_count: 0, eligible_count: 0, selected_count: 0 });
    expect(old?.drop_reasons).toEqual([{ subject: "article", stage: "harvest-feeds", reason: "STALE_MAX_AGE_EXCEEDED", count: 2 }]);
    const assessments = attempt.rows["article-assessments"].filter(row =>
      "source_id" in row.row && row.row.source_id === "recorded-news").map(row => row.row);
    expect(assessments).toHaveLength(2);
    expect(assessments.every(row => "extraction_outcome" in row && row.extraction_outcome === "not_attempted"
      && "timing_basis" in row && row.timing_basis === "published_at"
      && "extracted_word_count" in row && row.extracted_word_count === null)).toBe(true);
    const loss = attempt.rows.diversity.map(row => row.row).find(row =>
      "metric" in row && row.metric === "lost_diversity_by_stage" && "stage" in row && row.stage === "freshness");
    expect(loss).toMatchObject({ before_value: 2, after_value: 1, value: 1, item_count: 2 });
  } finally { await fixture.close(); }
});

test("audit refuses missing or changed pre-download timing and invented extraction evidence", async () => {
  const fixture = await recordedPlan();
  try {
    fixture.transport.recordings.bodies.rss = feed([
      { title: "Expired", path: "stale", date: "2026-10-19T10:00:00Z" },
    ]);
    const result = await runFeedPlan({}, fixture.inputs, fixture.runtime);
    expect(() => preparePlanningMetrics(result, fixture.inputs)).not.toThrow();
    const missing = structuredClone(result);
    delete missing.evidence.harvest.articles[0]!.observation.preflight_freshness;
    expect(() => preparePlanningMetrics(missing, fixture.inputs)).toThrow("preflight_freshness");
    const changed = structuredClone(result);
    changed.evidence.harvest.articles[0]!.observation.preflight_freshness!.age_hours += 1;
    expect(() => preparePlanningMetrics(changed, fixture.inputs)).toThrow("preflight_clock");
    const invented = structuredClone(result);
    invented.evidence.harvest.articles[0]!.observation.http_status = 200;
    expect(() => preparePlanningMetrics(invented, fixture.inputs)).toThrow("preflight_observation");
    const assessment = structuredClone(result);
    const event = assessment.events.find(event => event.payload.kind === "candidate_decision");
    if (event?.payload.kind !== "candidate_decision") throw new Error("Missing actual assessment");
    event.payload.assessment.author_present = true;
    event.payload.assessment.attribution_status = "available";
    expect(() => preparePlanningMetrics(assessment, fixture.inputs)).toThrow("preflight_unperformed");
  } finally { await fixture.close(); }
});
