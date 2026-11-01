/** Independent lifecycle calculations preserve native results delivered in reverse order. */
import { expect, test } from "bun:test";
import { readFile, stat } from "node:fs/promises";
import { join } from "node:path";
import {
  FeedHealthStateRowContract, FeedHealthStateRowSchema,
} from "@idhazh/common-contracts";
import { readPlannerParquet } from "@idhazh/ledger-file-writer";
import { publicationGitRecording } from "./publication-recordings";
import { fixtureGit } from "./fixture-git";
import { plannerRecordings } from "../../../packages/ledger-file-writer/test/planner-recordings";
import { randomUUID } from "node:crypto";
import { applyFeedCheck } from "../src/availability/feed-lifecycle";
import { deliverPlannerFiles } from "../scripts/feed-ingest-plan-deliver";
import { writeRows } from "./partition-fixtures";
import { inputEndpointKey } from "../src/read-ledger-history/health-summary";

test("independent baselines each apply one check and reverse delivery preserves both native results", async () => {
  const fixture = await publicationGitRecording();
  try {
    const day = "2026-10-20";
    const source = fixture.inputs.harvest.sources[0]!;
    const seed = plannerRecordings(day).find(record => record.name === "feed-health-state")!.row;
    const baseline = FeedHealthStateRowSchema.parse({
      ...seed, feed_id: source.id, endpoint_key: inputEndpointKey(source.url), strikes: 4,
      availability_updated_at: `${day}T10:00:00.123Z`, first_confirmed_failure_at: `${day}T06:00:00Z`,
    });
    const saved = await writeRows(join(fixture.repository, "state"), "feed-health-state", day, FeedHealthStateRowContract, [baseline]);
    await fixtureGit(fixture.repository, ["add", "--", ...saved.files.map(file => `state/${file.path}`)]);
    await fixtureGit(fixture.repository, ["commit", "-m", "Record generated lifecycle baseline"]);
    await fixtureGit(fixture.repository, ["push", "origin", "HEAD:refs/heads/main"]);
    const head = await fixtureGit(fixture.repository, ["rev-parse", "HEAD"]);
    const check = { check_result: "confirmed-http-failure" as const, checked_at: "2026-10-21T23:59:59.123Z", status: 503 };
    const rows = [701, 702].map(run => {
      const observed = { ...check, check_request_id: randomUUID() };
      return FeedHealthStateRowSchema.parse({ ...baseline,
        ...applyFeedCheck(baseline, observed, fixture.inputs.harvest.config.availability),
        ...observed, date: "2026-10-21", run_id: `2026-10-21-${run}`,
      });
    });
    const results = await Promise.all(rows.map(row => writeRows(fixture.inputs.outputRoot,
      "feed-health-state", row.date, FeedHealthStateRowContract, [row])));
    expect(await fixtureGit(fixture.origin, ["--git-dir", fixture.origin, "rev-parse", "main"])).toBe(head);
    for (const path of ["state/raw/planner/feed-availability/state.json", "state/raw/planner/feed-availability/enrollment.json"]) {
      await expect(stat(join(fixture.repository, path))).rejects.toMatchObject({ code: "ENOENT" });
    }
    const health = await Promise.all(results.map(result =>
      readPlannerParquet(join(fixture.inputs.outputRoot, result.files[0]!.path),
        "feed-health-state", FeedHealthStateRowContract)));
    for (const file of health) expect(file.rows[0]).toMatchObject({
      availability: "resting", strikes: 5, check_result: "confirmed-http-failure",
      status: 503, failed_recovery_checks: 0, retired_at: null,
    });
    expect(health[0]!.rows[0]!.check_request_id).not.toBe(health[1]!.rows[0]!.check_request_id);
    const paths = results.map(result => result.files.map(file => file.path));
    for (const index of [1, 0]) {
      const result = await deliverPlannerFiles({
        ...fixture.commit, paths: paths[index]!,
        identity: { run_id: rows[index]!.run_id, attempt: rows[index]!.attempt, git_sha: head },
        committer: { name: "Fixture", email: "fixture@example.test" },
      });
      expect(result.status).toBe("landed");
    }
    for (const file of health) {
      const path = `state/${results[rows.findIndex(row => row.run_id === file.rows[0]!.run_id)]!.files[0]!.path}`;
      expect(await fixtureGit(fixture.origin, ["--git-dir", fixture.origin, "cat-file", "-t", `main:${path}`])).toBe("blob");
    }
    const subjects = await fixtureGit(fixture.origin, ["--git-dir", fixture.origin, "log", "--format=%s", `${head}..main`]);
    expect(subjects.split("\n")).toEqual(["Record generated planner and host metadata", "Record generated planner and host metadata"]);
    expect(subjects).not.toContain("Update feed availability state");
    const retained = await readFile(join(fixture.inputs.outputRoot, results[0]!.files[0]!.path));
    expect(retained.byteLength).toBeGreaterThan(0);
  } finally { await fixture.close(); }
}, 120_000);
