/** How many distinct URLs did each source put in the digest on this UTC day? */
import { z } from "zod";
import { CONTRACT_VERSION, DateStampSchema, Sha256Schema, SlugSchema } from "@idhazh/common-contracts";
import type { LedgerRegistration } from "@idhazh/ledger-file-writer";
import type { SeenDayInput } from "../config/service-settings";
import { defaultDayInput, historyCoverage, latestNativeRows, readNamedDays } from "./named-days";

// Projection of contracts/item_health.py; successful item outcomes are the native day-count authority.
export const DailyPublicationSchema = z.strictObject({
  date: DateStampSchema, url_key: Sha256Schema, source_id: SlugSchema, outcome: z.enum(["ok", "failed"]),
});
export const DailyPublicationContract = {
  schema: DailyPublicationSchema, schemaVersion: CONTRACT_VERSION,
  projectedFields: ["date", "url_key", "source_id", "outcome"],
};
export async function readDailyPublication(input: {
  root: string; day: string; registration: LedgerRegistration; days: readonly SeenDayInput[];
}) {
  if (input.days.some(day => day.day !== input.day) || input.days.length > 1) {
    throw new Error("Daily publication evidence must name only the captured UTC day");
  }
  const held = await readNamedDays(input.root, input.registration,
    input.days.length === 0 ? [defaultDayInput(input.registration.prefix, input.day)] : input.days,
    DailyPublicationContract);
  const carried = new Map<string, string>();
  for (const day of held) for (const { row } of day.rows) {
    if (row.date !== day.day) throw new Error("Daily publication row differs from its named UTC day");
  }
  for (const row of latestNativeRows(held.flatMap(day => [...day.rows]))) {
    if (row.outcome === "ok") carried.set(row.url_key, row.source_id);
  }
  const counts = new Map<string, number>();
  for (const source of carried.values()) counts.set(source, (counts.get(source) ?? 0) + 1);
  return { day: input.day, counts, history: historyCoverage(held) };
}
