/** Do explicit run outcomes and distinct-attempt work survive current-format packing without raw proof ledgers? */
import { expect, test } from "bun:test";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import {
  DiscoveredArticleRowContract, FeedHealthStateRowContract, PlanRunRowContract, SelectedArticleRowContract,
} from "@idhazh/common-contracts";
import type { FeedHealthStateRow } from "@idhazh/common-contracts";
import { plannerRecordings } from "../../../packages/ledger-file-writer/test/planner-recordings";
import type { PlannerRecording } from "../../../packages/ledger-file-writer/test/planner-recordings";
import { readPlannerDay } from "../src/read-ledger-history/read-planner-history";
import { readPlannerParquet } from "../src/read-ledger-history/read-planner-parquet";
import { settleHealthRows } from "../src/read-ledger-history/health-summary";
import { foldDiscoveryHistory } from "../src/read-ledger-history/read-discovered-evidence";
import { commitFixtureFiles, compactRows, registration, writeRows } from "./partition-fixtures";
import { fixtureGit } from "./publication-recordings";

const day = "2026-10-20";
const contracts = {
  "discovered-articles": DiscoveredArticleRowContract, "selected-articles": SelectedArticleRowContract,
  "feed-health-state": FeedHealthStateRowContract, "plan-runs": PlanRunRowContract,
};
function facts() {
  return plannerRecordings(day).map(record => ({
    ...record, row: record.name === "plan-runs" ? { ...record.row, selected_count: 1 } : record.row,
  }));
}

test("explicit run results survive native daily, monthly and yearly packing without original raw files", async () => {
  const root = await mkdtemp(join(tmpdir(), "planner-completion-packing-"));
  try {
    for (const record of facts()) {
      const raw = await writeRows(root, record.name, day, record.contract, [record.row]);
      expect(raw.status).toBe("written");
      for (const period of ["daily", "monthly", "yearly"] as const) {
        const packed = await compactRows(join(root, "state"), record.name, day, record.contract, [record.row], period, root);
        for (const file of raw.files) await rm(join(root, file.path), { force: true });
        const reopened = await readPlannerDay(root, registration(record.name), {
          day,
        }, record.contract);
        expect(reopened.complete).toBe(true);
        expect(reopened.rows).toEqual([record.row]);
        const file = await readPlannerParquet(packed.path!, record.name, record.contract);
        expect(file.envelope).not.toHaveProperty("identity");
        expect(file.envelope).not.toHaveProperty("unit_id");
        expect(file.rows[0]).not.toHaveProperty("article_text");
      }
    }
  } finally { await rm(root, { recursive: true, force: true }); }
}, 30_000);

test("identical storage copies count once while distinct attempts retain their real request spend", async () => {
  const root = await mkdtemp(join(tmpdir(), "planner-attempt-facts-"));
  try {
    const original = plannerRecordings(day).find(record => record.name === "feed-health-state")!;
    const first = FeedHealthStateRowContract.schema.parse({ ...original.row, article_requests: 3 });
    const retry = FeedHealthStateRowContract.schema.parse({ ...first, attempt: 2, article_requests: 7 });
    const raw = await Promise.all([first, retry].map(row =>
      writeRows(join(root, "state"), original.name, day, FeedHealthStateRowContract, [row])));
    const rawFiles = raw.flatMap(result => result.files.map(file => `state/${file.path}`));
    await commitFixtureFiles(root, rawFiles);
    await compactRows(join(root, "state"), original.name, day, FeedHealthStateRowContract, [first, retry], "daily", root);
    const raw_revision = await fixtureGit(root, ["rev-parse", "--verify", "HEAD"]);
    const merged = await readPlannerDay(root, registration(original.name), {
      day, raw_files: rawFiles, raw_revision,
    }, FeedHealthStateRowContract);
    expect(merged.rows).toHaveLength(4);
    const settled = settleHealthRows(merged.rows);
    expect(settled).toEqual([first, retry]);
    expect(settled.reduce((total, row) => total + row.article_requests!, 0)).toBe(10);
    expect(() => settleHealthRows([...settled, { ...first, article_requests: 99 }])).toThrow("Conflicting copies");
    const discovery = DiscoveredArticleRowContract.schema.parse(plannerRecordings(day)[0]!.row);
    const earlier = { ...discovery, first_seen_at: "2026-10-19T23:59:59.999Z", date: "2026-10-19" };
    expect(foldDiscoveryHistory([discovery, earlier, discovery])).toEqual([earlier]);
    expect(settled.every((row: FeedHealthStateRow) => !("unit_id" in row))).toBe(true);
  } finally { await rm(root, { recursive: true, force: true }); }
}, 30_000);

test("a later explicit zero completion coexists with prior selections and failed-attempt work", async () => {
  const root = await mkdtemp(join(tmpdir(), "planner-zero-result-"));
  try {
    const runs = [1, 2, 3].map(attempt => PlanRunRowContract.schema.parse({
      ...plannerRecordings(day, attempt).find(record => record.name === "plan-runs")!.row,
      selected_count: attempt === 1 ? 1 : 0, status: attempt === 2 ? "partial" : "completed",
      failure_code: attempt === 2 ? "PLANNER_EXECUTION_FAILED" : null,
    }));
    const selected = SelectedArticleRowContract.schema.parse(
      plannerRecordings(day).find(record => record.name === "selected-articles")!.row,
    );
    const health = [1, 2, 3].map(attempt => FeedHealthStateRowContract.schema.parse({
      ...plannerRecordings(day, attempt).find(record => record.name === "feed-health-state")!.row,
      articles_selected: attempt === 1 ? 1 : 0, article_requests: attempt,
    }));
    const populations: PlannerRecording[] = [
      { name: "plan-runs", contract: contracts["plan-runs"], row: runs[0]! },
      { name: "selected-articles", contract: contracts["selected-articles"], row: selected },
    ];
    for (const period of ["daily", "monthly", "yearly"] as const) {
      for (const population of populations) {
        const rows = population.name === "plan-runs" ? runs : [selected];
        await compactRows(join(root, "state"), population.name, day, population.contract, rows, period, root);
        const held = await readPlannerDay(root, registration(population.name), {
          day,
        }, population.contract);
        expect(held.rows).toEqual(rows);
      }
      await compactRows(join(root, "state"), "feed-health-state", day, FeedHealthStateRowContract, health, period, root);
      const held = await readPlannerDay(root, registration("feed-health-state"), {
        day,
      }, FeedHealthStateRowContract);
      expect(settleHealthRows(held.rows).reduce((total, row) => total + row.article_requests!, 0)).toBe(6);
    }
    expect(runs[2]).toMatchObject({ status: "completed", selected_count: 0 });
    expect(selected.attempt).toBe(1);
    expect(runs.map(row => row.attempt)).toEqual([1, 2, 3]);
  } finally { await rm(root, { recursive: true, force: true }); }
}, 30_000);
