/** Prepare only the health evidence needed before fetch or during selection. */
import type { FeedHealthStateRow } from "@idhazh/common-contracts";
import type { PlanInputs } from "../load-plan-inputs";
import type { RunContext } from "../resolve-run-context";
import type { HealthCaptureCache } from "../read-ledger-history/read-health-capture";
import { readFeedHistory } from "../read-ledger-history/read-feed-history";
import { sourceSnapshot } from "../harvest-feeds/load-harvest-inputs";
import { plannerMemory } from "../planner-memory";

export type CurrentHealthWork = { context: RunContext; rows: readonly FeedHealthStateRow[] };
export function healthHistoryInput(inputs: PlanInputs, now: string, current?: CurrentHealthWork) {
  return {
    root: inputs.root, now, sources: inputs.harvest.sources.map(source => sourceSnapshot(inputs.harvest, source)),
    policy: inputs.clock_config.collect, ...inputs.harvest.config.feedback,
    concurrency: inputs.harvest.config.harvest.concurrency, health: inputs.registrations.feed_health_state,
    health_days: inputs.settings.inputs.feed_health_days,
    own_rows: plannerMemory(inputs).health(),
    ...(current === undefined ? {} : {
      current_rows: current.rows, exclude_execution: { run_id: current.context.run_id, attempt: current.context.writer.attempt },
    }),
  };
}
export async function preparePlanningHealth(
  inputs: PlanInputs, now: string, current?: CurrentHealthWork, cache?: HealthCaptureCache,
) {
  const result = await readFeedHistory(healthHistoryInput(inputs, now, current), cache);
  if (inputs.settings.inputs.feed_health_input_gap) {
    for (const [id, source] of result.sources) result.sources.set(id, {
      ...source, article_pass_rate: null,
      reliability: source.reliability === null ? null : { ...source.reliability, complete: false },
    });
  }
  return result;
}
