/** Prepare only the health evidence needed before fetch or during selection. */
import type { FeedHealthStateRow } from "@idhazh/common-contracts";
import type { PlanInputs } from "../load-plan-inputs";
import type { RunContext } from "../resolve-run-context";
import type { HealthCaptureCache } from "../read-ledger-history/read-health-capture";
import { readFeedHistory } from "../read-ledger-history/read-feed-history";
import { sourceSnapshot } from "../harvest-feeds/load-harvest-inputs";
import { plannerMemory } from "../planner-memory";
import { createStageLogger } from "../logging/structured-logger";
import { summarizePlanningHealth } from "../read-ledger-history/health-summary";
import { summarizeFeedAvailability } from "../availability/feed-availability-view";
import { projectFeedHealthFields } from "../read-ledger-history/read-feed-health-fields";

export type CurrentHealthWork = { context: RunContext; rows: readonly FeedHealthStateRow[] };
export function healthHistoryInput(inputs: PlanInputs, now: string, current?: CurrentHealthWork) {
  return {
    root: inputs.root, now, sources: inputs.harvest.sources.map(source => sourceSnapshot(inputs.harvest, source)),
    policy: inputs.clock_config.collect, ...inputs.harvest.config.feedback,
    lifecycle_policy: inputs.harvest.config.availability,
    concurrency: inputs.harvest.config.harvest.concurrency, health: inputs.registrations.feed_health_state,
    health_days: inputs.settings.inputs.feed_health_days,
    own_rows: plannerMemory(inputs).health(),
    ...(current === undefined ? {} : {
      current_rows: current.rows, exclude_execution: { run_id: current.context.run_id, attempt: current.context.writer.attempt },
      log: createStageLogger(current.context),
    }),
  };
}
export async function preparePlanningHealth(
  inputs: PlanInputs, now: string, current?: CurrentHealthWork, cache?: HealthCaptureCache,
) {
  const input = healthHistoryInput(inputs, now, current);
  let captured: Awaited<ReturnType<typeof readFeedHistory>>;
  if (current === undefined) captured = await readFeedHistory(input, cache);
  else {
    let runs = captures.get(inputs);
    if (runs === undefined) { runs = new Map(); captures.set(inputs, runs); }
    const key = `${current.context.run_id}:${current.context.writer.attempt}`;
    let pending = runs.get(key);
    if (pending === undefined) {
      pending = readFeedHistory({ ...input, now: current.context.now, current_rows: [] }, cache);
      while (runs.size >= inputs.settings.listener.max_stage_batches) runs.delete(runs.keys().next().value!);
      runs.set(key, pending);
      try { await pending; } catch (error) { runs.delete(key); throw error; }
    }
    captured = await pending;
  }
  const result = current === undefined || current.rows.length === 0 ? captured : {
    ...captured, ...summarizePlanningHealth({ ...captured, ...input,
      saved_sources: captured.sources, current_rows: current.rows }),
  };
  const sources = new Map(result.sources);
  const requestRows = (current?.rows ?? []).flatMap(row => projectFeedHealthFields(row.date, [row]).request_totals.rows);
  const uses = { ...result.uses, request_totals: {
    ...result.uses.request_totals, rows: [...result.uses.request_totals.rows, ...requestRows],
  } };
  if (inputs.settings.inputs.feed_health_input_gap) {
    for (const [id, source] of sources) sources.set(id, {
      ...source, article_pass_rate: null,
      reliability: source.reliability === null ? null : { ...source.reliability, complete: false },
    });
  }
  return { ...result, sources, uses, availability: summarizeFeedAvailability(sources, now, inputs.harvest.sources) };
}
const captures = new WeakMap<PlanInputs, Map<string, Promise<Awaited<ReturnType<typeof readFeedHistory>>>>>();
