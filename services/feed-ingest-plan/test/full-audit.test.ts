/** Can actual API and CLI runs complete an audit only with verified publication and closed history? */
import { expect, test } from "bun:test";
import { rm } from "node:fs/promises";
import { join } from "node:path";
import { main } from "../src/index";
import { createPlanApp } from "../src/api/server";
import { recordPublicationMetrics, verifyPublicationMetrics } from "../src/metrics/metrics-recorder";
import type { PublicationRecorderInput } from "../src/metrics/metrics-recorder";
import { generatePublicationInput } from "./full-audit-recording";
import { recordedPlan } from "./plan-recordings";
import { source } from "./harvest-recordings";

test("API and CLI expose genuine full audit completion, with independent native observer verification", async () => {
  for (const entry of ["cli", "api"] as const) {
    const fixture = await recordedPlan();
    try {
      let observation: PublicationRecorderInput | undefined;
      const runtime = { ...fixture.runtime, observe_publication: async (...args: Parameters<NonNullable<typeof fixture.runtime.observe_publication>>) => {
        observation = await generatePublicationInput(args[0], args[1], fixture.inputs, join(fixture.directory, "publication"));
        return observation;
      } };
      const app = createPlanApp(fixture.inputs, runtime);
      const summary = entry === "cli"
        ? await main(["--cli"], { inputs: fixture.inputs, runtime, output: () => {} })
        : await (await app.request("/api/2026-10-20/plan", { method: "POST", body: "{}" })).json();
      if (!("files" in summary) || summary.publication === null || observation === undefined) throw new Error("Actual full audit absent");
      expect(summary).toMatchObject({ status: "audit_complete", planning_complete: true, audited_complete: true,
        audit: { status: "complete", reason: null } });
      expect(summary.publication.history.coverage_days).toBe(summary.publication.history.required_days);
      expect(summary.metrics.evidence.trace[0]?.evaluated[0]?.scores).toMatchObject({
        source_reliability: null,
        source_operational: {
          status: "unavailable", state_status: "unavailable", operational_penalty: null,
        },
      });
      expect(await verifyPublicationMetrics(observation, summary.publication)).toEqual({ status: "complete", reasons: [] });
      await expect(verifyPublicationMetrics(observation, { ...summary.publication, attempt: 2 })).rejects.toThrow("identity");
      await expect(verifyPublicationMetrics(observation, { ...summary.publication,
        history: { ...summary.publication.history, coverage_days: 0 } })).rejects.toThrow("history");
      await expect(verifyPublicationMetrics(observation, { ...summary.publication,
        receipts: { diversity: { ...summary.publication.receipts.diversity, row_count: 0 } } })).rejects.toThrow("receipt");
      const file = summary.publication.files.sources?.files[0];
      if (file === undefined) throw new Error("Missing actual completed source file");
      await rm(join(observation.outputRoot, file.path));
      await expect(verifyPublicationMetrics(observation, summary.publication)).rejects.toThrow();
    } finally { await fixture.close(); }
  }
}, 30000);

test("missing planning, publication, event evidence and open history remain pending instead of fabricated success", async () => {
  const fixture = await recordedPlan();
  try {
    let observation: PublicationRecorderInput | undefined;
    const summary = await main(["--cli"], {
      inputs: fixture.inputs, output: () => {},
      runtime: { ...fixture.runtime, observe_publication: async (plan, metrics) => {
        observation = await generatePublicationInput(plan, metrics, fixture.inputs, join(fixture.directory, "publication"));
        return observation;
      } },
    });
    if (!("files" in summary) || observation === undefined) throw new Error("Missing actual fixture evidence");
    const { event_pairs: _pairs, ...withoutPairs } = observation;
    const variations: PublicationRecorderInput[] = [
      { ...observation, planning_days: observation.planning_days.slice(1) },
      { ...observation, publication_days: observation.publication_days.slice(1) },
      { ...observation, as_of: summary.observed_at },
      withoutPairs,
    ];
    for (const [index, input] of variations.entries()) {
      const output = await recordPublicationMetrics({ ...input, outputRoot: join(fixture.directory, `pending-${index}`) });
      expect(output.audited_complete).toBe(false);
      expect(output.audit_completion.status).toBe("pending");
      expect(output.audit_completion.reasons.length).toBeGreaterThan(0);
    }
  } finally { await fixture.close(); }
}, 30000);

test("a measured empty portfolio can complete an audit without invented articles or empty files", async () => {
  const fixture = await recordedPlan([source({ url: "https://news.example/empty.xml" })]);
  try {
    const summary = await main(["--cli"], {
      inputs: fixture.inputs, output: () => {},
      runtime: { ...fixture.runtime, observe_publication: (plan, metrics) =>
        generatePublicationInput(plan, metrics, fixture.inputs, join(fixture.directory, "publication")) },
    });
    if (!("files" in summary)) throw new Error("Missing summary");
    expect(summary.audited_complete).toBe(true);
    expect(summary.files.dispatches).toEqual({ status: "empty", files: [] });
    expect(summary.source_records?.every(row => row.selected_count === 0)).toBe(true);
    expect(summary.publication?.source_observations.every(row => row.published_count === 0 && row.lead_count === 0)).toBe(true);
  } finally { await fixture.close(); }
}, 30000);
