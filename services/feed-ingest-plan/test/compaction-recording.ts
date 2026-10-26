/** Produce real four-ledger attempts, then reopen the exact gardener outputs in the native CI case. */
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { isDeepStrictEqual } from "node:util";
import {
  DiscoveredArticleRowContract, FeedHealthStateRowContract, PlanRunRowContract, SelectedArticleRowContract,
} from "@idhazh/common-contracts";
import { persistLedger } from "@idhazh/ledger-file-writer";
import type { LedgerRowContract } from "@idhazh/ledger-file-writer";
import { main } from "../src/index";
import { readPlannerDay } from "../src/read-ledger-history/read-planner-history";
import { readPlannerParquet } from "../src/read-ledger-history/read-planner-parquet";
import { recordedPlan } from "./plan-recordings";
import { source } from "./harvest-recordings";

const day = "2026-10-20";
const contracts = {
  "discovered-articles": DiscoveredArticleRowContract, "selected-articles": SelectedArticleRowContract,
  "feed-health-state": FeedHealthStateRowContract, "plan-runs": PlanRunRowContract,
} satisfies Record<string, LedgerRowContract<object>>;
type Name = keyof typeof contracts;
type Row = Record<string, unknown>;
const keys: Record<Name, string[]> = {
  "discovered-articles": ["url_key"], "selected-articles": ["run_id", "attempt", "url_key"],
  "feed-health-state": ["run_id", "attempt", "feed_id", "endpoint_key", "date"],
  "plan-runs": ["run_id", "attempt"],
};
type Manifest = { keys: typeof keys; expected: Record<Name, Row[]> };
const names = Object.keys(contracts) as Name[];
function emptyRows(): Record<Name, Row[]> {
  return { "discovered-articles": [], "selected-articles": [], "feed-health-state": [], "plan-runs": [] };
}
const [mode, root, tier] = Bun.argv.slice(2);
if (root === undefined || !["produce", "late", "verify"].includes(mode ?? "")) {
  throw new Error("Name produce/late/verify and one generated directory");
}
const manifestPath = join(root, "attempts.json");
const registration = (name: Name) => ({
  name, family: "feed-ingest-plan", grain: "raw-and-compact" as const,
  lifecycle_status: "active" as const, prefix: ["feed-ingest-plan", name],
});
function settle(name: Name, rows: readonly Row[]) {
  const facts = new Map<string, Row>();
  for (const recorded of rows) {
    // The manifest is JSON: a numeric no-op is zero, including native Arrow's -0.
    const row = JSON.parse(JSON.stringify(recorded)) as Row;
    const key = JSON.stringify(keys[name].map(field => row[field]));
    const previous = facts.get(key);
    if (previous === undefined) facts.set(key, row);
    else if (name === "discovered-articles") {
      if (String(row.first_seen_at) < String(previous.first_seen_at)) facts.set(key, row);
    } else if (!isDeepStrictEqual(previous, row)) throw new Error(`Conflicting fixture copies of ${name}: ${key}`);
  }
  return [...facts.entries()].sort(([left], [right]) => left.localeCompare(right)).map(([, row]) => row);
}
async function produce(attempt: number, zero = false, partial = false) {
  const fixture = await recordedPlan(zero ? [source({ url: "https://news.example/empty.xml" })] : undefined);
  try {
    fixture.inputs.root = root!;
    fixture.inputs.outputRoot = join(root!, "state");
    fixture.inputs.settings.inputs.artifact_root = "artifacts";
    fixture.inputs.settings.run.attempt = attempt;
    fixture.runtime.clock = () => new Date(`${day}T12:00:00Z`);
    fixture.runtime.observation_clock = () => new Date(`${day}T12:00:00Z`);
    if (partial) fixture.runtime.progress = event => {
      if (event.eventType === "ARTICLE_HARVEST_COMPLETED" && event.output_count === 1) {
        throw new Error("Recorded progress destination failed after actual article work");
      }
    };
    const result = await main(["--cli", "--partition-strategy=none", "--article-limit=1"], {
      inputs: fixture.inputs, runtime: fixture.runtime, output: () => {},
    });
    if (!("files" in result) || result.date !== day) throw new Error("Missing actual run outcome on the native fixture day");
    if (result.status !== (partial ? "partial" : "completed")) throw new Error(`Unexpected attempt ${attempt} outcome`);
    if ((zero || partial) && result.selected_count !== 0) throw new Error("The fixture needs an explicit zero run result");
    const files = {
      "discovered-articles": result.files.discovered_articles, "selected-articles": result.files.selected_articles,
      "feed-health-state": result.files.feed_health_state, "plan-runs": result.files.plan_runs,
    };
    const rows = emptyRows();
    for (const name of names) for (const file of files[name]?.files ?? []) {
      const held = await readPlannerParquet(join(root!, "state", file.path), name, contracts[name] as LedgerRowContract<Row>);
      rows[name].push(...held.rows);
    }
    if (!zero && rows["feed-health-state"].reduce((total, row) => total + Number(row.article_requests ?? 0), 0) <= 0) {
      throw new Error("The nonempty attempts must retain actual dispatched article requests");
    }
    return rows;
  } finally { await fixture.close(); }
}
if (mode === "produce" || mode === "late") {
  await mkdir(root, { recursive: true });
  const recorded: Manifest = mode === "late"
    ? JSON.parse(await readFile(manifestPath, "utf8")) as Manifest
    : { keys, expected: emptyRows() };
  if (!isDeepStrictEqual(recorded.keys, keys)) throw new Error("The fixture manifest does not declare current native row keys");
  for (const attempt of mode === "late" ? [4] : [1, 2, 3]) {
    const rows = await produce(attempt, attempt === 3, attempt === 2);
    for (const name of names) {
      recorded.expected[name] = settle(name, [...recorded.expected[name], ...rows[name]]);
      // A second actual raw representation proves that compaction deduplicates copies, not attempts.
      if (rows[name].length > 0) await persistLedger({
        ledger: name, rowContract: contracts[name] as LedgerRowContract<Row>, rows: rows[name],
        outputRoot: join(root, "state"), registryEntry: registration(name),
        ledgerSettings: { format: "parquet", compression_raw: "snappy", compression_compact: "zstd" },
        period: { tier: "raw", covers: day },
        ...(name === "feed-health-state" ? { updatedAt: new Date().toISOString() } : {}),
      });
    }
  }
  await writeFile(manifestPath, JSON.stringify(recorded));
} else {
  if (!["daily", "monthly", "reopened", "yearly"].includes(tier ?? "")) throw new Error("Name daily/monthly/reopened/yearly");
  const recorded: Manifest = JSON.parse(await readFile(manifestPath, "utf8")) as Manifest;
  const period = tier === "reopened" ? "monthly" : tier as "daily" | "monthly" | "yearly";
  for (const name of names) {
    const held = await readPlannerDay(root, registration(name), {
      day, indexes: { [period]: join(root, "state", "compact", "feed-ingest-plan", name, "index", `${period}.json`) },
    }, contracts[name] as LedgerRowContract<Row>);
    if (!held.complete || !isDeepStrictEqual(settle(name, held.rows), recorded.expected[name])) {
      throw new Error(`Production ${tier} packing changed ${name} facts or their completeness`);
    }
  }
}
console.log(JSON.stringify({ status: "verified", mode, tier: tier ?? "raw" }));
