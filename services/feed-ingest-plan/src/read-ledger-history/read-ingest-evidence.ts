/** What bounded native article evidence is available from the configured closed UTC days? */
import { PositiveCountSchema, TimestampSchema } from "@idhazh/common-contracts";
import type { DocumentObservationRecord } from "@idhazh/common-contracts";
import type { LedgerRegistration } from "@idhazh/ledger-file-writer";
import type { SeenDayInput } from "../config/service-settings";
import { shiftUtcDay } from "../metrics/history-window";
import { DocumentObservationContract } from "../metrics/audit-contracts";
import { settleIngestObservations } from "../settle-ingest-observations";
import { rollupIngestOutcomes } from "../rollup-ingest-outcomes";
import { defaultDayInput, historyCoverage, readNamedDays, usableDay } from "./named-days";
import { classifyPublicationHistoryError } from "./classify-publication-history-error";
import { LedgerHistoryReadError } from "./ledger-history-error";
import { writeJsonLine } from "../logging/structured-logger";
import type { ReadLedgerFile } from "./read-parquet";

export function closedObservationDays(now: string, windowDays: number): string[] {
  const today = TimestampSchema.parse(now).slice(0, 10);
  const count = PositiveCountSchema.parse(windowDays);
  return Array.from({ length: count }, (_, index) => shiftUtcDay(today, index - count));
}

export async function readIngestEvidence(input: Readonly<{
  root: string; now: string; window_days: number; registration: LedgerRegistration;
  days: readonly SeenDayInput[];
}>) {
  const dates = closedObservationDays(input.now, input.window_days);
  const configured = new Map<string, SeenDayInput>();
  for (const day of input.days) {
    if (!dates.includes(day.day)) continue;
    if (configured.has(day.day)) throw new Error("Document observation inputs repeat a UTC day");
    configured.set(day.day, day);
  }
  if (input.registration.name !== "document-observations" || input.registration.family !== "feed-ingest-plan") {
    throw new Error("Article evidence requires the registered document-observations ledger");
  }
  const days = [];
  const gaps: { day: string; diagnostic: string }[] = [];
  const fileCache = new Map<string, Promise<ReadLedgerFile<DocumentObservationRecord>>>();
  for (const date of dates) {
    try {
      const held = await readNamedDays(input.root, input.registration,
        [configured.get(date) ?? defaultDayInput(input.registration.prefix, date)], DocumentObservationContract, fileCache);
      for (const day of held) {
        if (day.rows.some(({ row }) => row.occurred_at.slice(0, 10) !== date)) {
          throw new LedgerHistoryReadError("Document observation differs from its UTC day partition");
        }
        days.push(day);
      }
    } catch (error) {
      const diagnostic = classifyPublicationHistoryError(error);
      if (diagnostic === null) throw error;
      gaps.push({ day: date, diagnostic });
    }
  }
  let rows: readonly DocumentObservationRecord[] = [];
  let notices: ReturnType<typeof settleIngestObservations>["notices"] = [];
  let totals = rollupIngestOutcomes([], false);
  try {
    ({ rows, notices } = settleIngestObservations(days.flatMap(day => day.rows.map(held => held.row)), dates[0]!, dates.at(-1)!));
    totals = rollupIngestOutcomes(rows, gaps.length === 0 && days.length === dates.length
      && days.every(usableDay) && notices.length === 0);
  } catch (error) {
    if (!(error instanceof LedgerHistoryReadError)) throw error;
    gaps.push({ day: dates[0]!, diagnostic: error.message });
  }
  for (const gap of gaps) writeJsonLine({
    timestamp: input.now, level: "WARN", event: "article_evidence_unavailable", ...gap,
  });
  const complete = gaps.length === 0 && days.length === dates.length && days.every(usableDay)
    && notices.length === 0;
  return {
    window: { start: dates[0]!, end: dates.at(-1)!, days: input.window_days },
    availability: complete ? "available" as const : "unavailable" as const,
    history: historyCoverage(days), gaps, notices,
    ...totals,
  };
}
