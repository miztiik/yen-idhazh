/** Read only closed request-report days and expose their independent counter fields. */
import { defaultDayInput } from "./named-days";
import { readHealthCapture } from "./read-health-capture";
import type { HealthCaptureCache, HealthCaptureInput } from "./read-health-capture";
import type { SourceSnapshot } from "@idhazh/common-contracts";
import { closedRequestDays, summarizeRequestReport } from "./request-summary";

export async function readRequestHistory(input: HealthCaptureInput & {
  sources: readonly SourceSnapshot[]; request_report_closed_days: number; input_complete?: boolean;
}, cache?: HealthCaptureCache) {
  const days = closedRequestDays(input.now, input.request_report_closed_days);
  const capture = await readHealthCapture({
    ...input, own_days: (input.own_days ?? []).filter(day => days.includes(day.day)),
    own_rows: (input.own_rows ?? []).filter(row => days.includes(row.date)),
    current_rows: (input.current_rows ?? []).filter(row => days.includes(row.date)),
  }, days.map(day => input.health_days.find(value => value.day === day) ?? defaultDayInput(input.health.prefix, day)), cache);
  const fields = capture.uses.request_totals;
  return {
    ...fields, days: capture.request_days,
    request_report: summarizeRequestReport({
      ...input, ...fields, days: capture.request_days,
    }),
  };
}
