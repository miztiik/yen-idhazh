/** Prove full audit completion on generated publication evidence, never production publication. */
import { join } from "node:path";
import { main } from "../../services/feed-ingest-plan/src/index";
import { verifyPublicationMetrics } from "../../services/feed-ingest-plan/src/metrics/metrics-recorder";
import type { PublicationRecorderInput } from "../../services/feed-ingest-plan/src/metrics/metrics-recorder";
import { recordedPlan } from "../../services/feed-ingest-plan/test/plan-recordings";
import { generatePublicationInput } from "../../services/feed-ingest-plan/test/full-audit-recording";
import { verifyPlanningCompletion } from "./feed-ingest-plan-verification";

export async function verifyFullAuditFixture(root: string) {
  const fixture = await recordedPlan();
  try {
    fixture.inputs.outputRoot = join(root, "planning");
    let observation: PublicationRecorderInput | undefined;
    const summary = await main(["--cli"], {
      inputs: fixture.inputs, output: () => {},
      runtime: { ...fixture.runtime, observe_publication: async (plan, metrics) => {
        observation = await generatePublicationInput(plan, metrics, fixture.inputs, join(root, "publication"));
        return observation;
      } },
    });
    if (!("files" in summary) || summary.publication === null || observation === undefined) throw new Error("Generated full-audit evidence is absent");
    await verifyPlanningCompletion(fixture.inputs.outputRoot, summary);
    const completion = await verifyPublicationMetrics(observation, summary.publication);
    if (completion.status !== "complete" || !summary.audited_complete || summary.status !== "audit_complete") {
      throw new Error(`Generated full-audit verification is incomplete: ${JSON.stringify(completion.reasons)}`);
    }
    return { scope: "generated_fixture" as const, audited_complete: true, run_id: summary.run_id,
      attempt: summary.planning_completion!.attempt, history: summary.publication.history };
  } finally { await fixture.close(); }
}
if (import.meta.main) {
  const root = Bun.argv[2];
  if (root === undefined) throw new Error("Name one generated fixture output directory");
  console.log(JSON.stringify(await verifyFullAuditFixture(root)));
}
