/** Which required audit evidence is still absent after native observation readback? */
import type { DiversityMetricRow } from "@idhazh/common-contracts";
import type { HistoryWindow } from "./history-window";
import type { PlanningDay } from "./planning-populations";

export function resolveAuditCompletion(input: {
  source_reason: string | null; history: HistoryWindow;
  planning: readonly PlanningDay[]; rows: readonly DiversityMetricRow[];
}) {
  const reasons: string[] = [];
  if (input.source_reason !== null) reasons.push(input.source_reason);
  if (input.history.availability !== "available") reasons.push("The named publication history is not complete and closed");
  const planning = new Map(input.planning.map(day => [day.day, day]));
  for (const day of input.history.days) {
    const held = planning.get(day.day);
    if (held === undefined || (held.status !== "rows" && held.status !== "empty")) {
      reasons.push(`${day.day}: complete planning history is unavailable`);
    }
  }
  for (const row of input.rows) {
    if (row.unavailable_reason !== null && row.unavailable_reason !== "empty_denominator") {
      const reason = `${row.metric}/${row.basis}: ${row.unavailable_reason}`;
      if (!reasons.includes(reason)) reasons.push(reason);
    }
  }
  if (input.rows.length === 0) reasons.push("No publication metrics were verified");
  return { status: reasons.length === 0 ? "complete" as const : "pending" as const, reasons };
}
