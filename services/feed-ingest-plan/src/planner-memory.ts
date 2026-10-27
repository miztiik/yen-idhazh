/** Share current-process discoveries and finalized health within configured history windows. */
import type { DiscoveredArticleRow, FeedHealthStateRow } from "@idhazh/common-contracts";
import type { PlanInputs } from "./load-plan-inputs";
import { foldDiscoveryHistory } from "./read-ledger-history/read-discovered-evidence";
import { settleHealthRows } from "./read-ledger-history/health-summary";

const held = new WeakMap<PlanInputs, { discoveries: DiscoveredArticleRow[]; health: FeedHealthStateRow[] }>();
export function plannerMemory(inputs: PlanInputs) {
  let state = held.get(inputs);
  if (state === undefined) {
    state = { discoveries: [], health: [] };
    held.set(inputs, state);
  }
  const current = state;
  return {
    discoveries: () => current.discoveries,
    health: () => current.health,
    rememberDiscoveries(rows: readonly DiscoveredArticleRow[], fromDay: string) {
      current.discoveries = foldDiscoveryHistory([...current.discoveries, ...rows]).filter(row => row.date >= fromDay);
      return current.discoveries;
    },
    rememberHealth(rows: readonly FeedHealthStateRow[]) {
      const facts = settleHealthRows([...current.health, ...rows]);
      const limit = Math.max(inputs.harvest.config.feedback.lifecycle_window_days, inputs.clock_config.collect.reliability_window_days)
        + inputs.harvest.config.feedback.request_report_closed_days;
      const days = [...new Set(facts.map(row => row.date))].sort().slice(-limit);
      current.health = facts.filter(row => days.includes(row.date));
    },
  };
}
