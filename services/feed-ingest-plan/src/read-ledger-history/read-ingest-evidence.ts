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
import type { LedgerDay } from "./read-period";

export function closedObservationDays(now: string, windowDays: number): string[] {
  const today = TimestampSchema.parse(now).slice(0, 10);
  const count = PositiveCountSchema.parse(windowDays);
  return Array.from({ length: count }, (_, index) => shiftUtcDay(today, index - count));
}

export async function readIngestEvidence(input: Readonly<{
  root: string; now: string; window_days: number; registration: LedgerRegistration;
  legacy_registration: LedgerRegistration;
  days: readonly SeenDayInput[]; legacy_days: readonly SeenDayInput[];
}>) {
  const dates = closedObservationDays(input.now, input.window_days);
  const configured = new Map<string, SeenDayInput>();
  for (const day of input.days) {
    if (!dates.includes(day.day)) continue;
    if (configured.has(day.day)) throw new Error("Document observation inputs repeat a UTC day");
    configured.set(day.day, day);
  }
  const legacyConfigured = new Map<string, SeenDayInput>();
  for (const day of input.legacy_days) {
    if (!dates.includes(day.day)) continue;
    if (legacyConfigured.has(day.day)) throw new Error("Legacy document observation inputs repeat a UTC day");
    legacyConfigured.set(day.day, day);
  }
  if (input.registration.name !== "ingest-observations" || input.registration.family !== "feed-ingest-plan"
    || input.legacy_registration.name !== "document-observations"
    || input.legacy_registration.family !== "feed-ingest-plan") {
    throw new Error("Article evidence requires both registered observation ledgers");
  }
  const days: LedgerDay<DocumentObservationRecord>[] = [];
  const gaps: { day: string; diagnostic: string }[] = [];
  const fileCache = new Map<string, Promise<ReadLedgerFile<DocumentObservationRecord>>>();
  for (const date of dates) {
    const aliases = [
      {
        registration: input.legacy_registration,
        day: legacyConfigured.get(date) ?? defaultDayInput(input.legacy_registration.prefix, date),
      },
      {
        registration: input.registration,
        day: configured.get(date) ?? defaultDayInput(input.registration.prefix, date),
      },
    ];
    const held = [];
    const diagnostics: string[] = [];
    for (const alias of aliases) {
      try {
        const [day] = await readNamedDays(input.root, alias.registration,
          [alias.day], DocumentObservationContract, fileCache);
        if (day === undefined) throw new Error("Named observation day was not returned");
        if (day.rows.some(({ row }) => row.occurred_at.slice(0, 10) !== date)) {
          throw new LedgerHistoryReadError("Document observation differs from its UTC day partition");
        }
        if (day.status === "lost" || day.notices.some(notice =>
          notice === "period-expired" || notice.startsWith("files-set-aside:"))) {
          diagnostics.push(`${alias.registration.name}:history-unavailable`);
        }
        held.push(day);
      } catch (error) {
        const diagnostic = classifyPublicationHistoryError(error);
        if (diagnostic === null) throw error;
        diagnostics.push(`${alias.registration.name}:${diagnostic}`);
      }
    }
    const rows = held.flatMap(day => day.rows);
    const notices = held.flatMap(day => day.notices);
    const status = held.some(day => day.status === "lost") ? "lost"
      : rows.length > 0 ? "rows"
        : held.some(day => day.status === "empty") ? "empty" : "missing";
    days.push({
      ledger: "ingest-observations", day: date, status,
      tier: held.find(day => day.status === "rows" || day.status === "empty")?.tier ?? null,
      rows, files: held.flatMap(day => day.files), notices,
    });
    if (diagnostics.length > 0) gaps.push({ day: date, diagnostic: diagnostics.join(";") });
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
