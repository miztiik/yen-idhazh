/** Produce or verify native attempt evidence for the existing production gardener CI case. */
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { isDeepStrictEqual } from "node:util";
import { main } from "../src/index";
import { runFeedPlan } from "../src/run-feed-plan";
import { readPlanningHistory } from "../src/metrics/planning-populations";
import type { NamedPlanningHistory } from "../src/metrics/planning-populations";
import { selectCompleteAttempt } from "../src/read-ledger-history/complete-attempt";
import { PLANNING_RECORD_KEYS } from "../src/read-ledger-history/logical-records";
import { recordedPlan } from "./plan-recordings";
import { source } from "./harvest-recordings";

const [mode, root, tier] = Bun.argv.slice(2);
if (root === undefined || !["produce", "verify"].includes(mode ?? "")) throw new Error("Name produce/verify and one generated directory");
const manifest = join(root, "attempts.json");
if (mode === "produce") {
  await mkdir(root, { recursive: true });
  const expected = [];
  for (const attempt of [1, 2, 3]) {
    const fixture = await recordedPlan(attempt === 3 ? [source({ url: "https://news.example/empty.xml" })] : undefined);
    try {
      fixture.inputs.outputRoot = join(root, "state");
      fixture.inputs.settings.run.attempt = attempt;
      if (attempt === 2) {
        await runFeedPlan({}, fixture.inputs, fixture.runtime);
        continue; // A partial retry has no source completion.
      }
      const summary = await main(["--cli"], { inputs: fixture.inputs, runtime: fixture.runtime, output: () => {} });
      if (!("files" in summary) || summary.source_records === null) throw new Error("Missing actual completion");
      expected.push({ attempt, sources: summary.source_records, date: summary.date, run_id: summary.run_id });
    } finally { await fixture.close(); }
  }
  await writeFile(manifest, JSON.stringify({ keys: PLANNING_RECORD_KEYS, attempts: expected }));
} else {
  if (!["daily", "monthly", "yearly"].includes(tier ?? "")) throw new Error("Name the production packed tier");
  const recorded: { attempts: { attempt: number; sources: object[]; date: string; run_id: string }[] } = JSON.parse(await readFile(manifest, "utf8"));
  const expected = recorded.attempts;
  const first = expected[0]!;
  const named = (ledger: string) => ({
    day: first.date, indexes: { [tier!]: join(root, "state", "compact", "feed-ingest-plan", ledger, "index", `${tier}.json`) },
  });
  const missing = { day: first.date };
  const input: NamedPlanningHistory = {
    sources: missing, feed_runs: named("feed-runs"), ledgers: {
      "article-assessments": named("article-assessments"), diversity: missing,
      "editorial-selections": named("editorial-selections"), dispatches: missing, rejections: missing,
    }, renamed: {
      "article-selection-diversity": named("article-selection-diversity"),
      "article-dispatches": named("article-dispatches"),
      "ingest-rejections": named("ingest-rejections"),
    },
  };
  const history = await readPlanningHistory(input);
  for (const record of expected) {
    const resolution = selectCompleteAttempt({
      ...history, sources: { ...history.sources, rows: history.sources.rows.filter(held => held.identity.attempt === record.attempt) },
    }, record.run_id);
    const complete = resolution.selected;
    if (complete === null || complete.attempt !== record.attempt || !isDeepStrictEqual(complete.sources, record.sources)) {
      throw new Error(`Production ${tier} packing did not preserve attempt ${record.attempt}: ${JSON.stringify(resolution.findings)}`);
    }
  }
  if (selectCompleteAttempt(history, first.run_id).selected?.attempt !== 3) throw new Error("A zero-selection completion did not win over the partial retry");
}
console.log(JSON.stringify({ status: "verified", mode, tier: tier ?? "raw" }));
