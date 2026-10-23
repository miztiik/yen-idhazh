/** Which newest named days actually contain recorded feed-health rows? */
import type { LedgerRegistration } from "@idhazh/ledger-file-writer";
import type { SeenDayInput } from "../config/service-settings";
import { FeedHealthContract } from "@idhazh/common-contracts";
import type { FeedHealthRow } from "@idhazh/common-contracts";
import type { ReadLedgerFile } from "./read-parquet";
import { readNamedDays } from "./named-days";

export async function selectHealthDays(
  root: string, registration: LedgerRegistration, inputs: readonly SeenDayInput[], count: number,
): Promise<SeenDayInput[]> {
  if (!Number.isSafeInteger(count) || count < 1) throw new Error("Feed-health recorded-day count must be positive");
  const fileCache = new Map<string, Promise<ReadLedgerFile<FeedHealthRow>>>();
  const recorded: SeenDayInput[] = [];
  for (const input of inputs.toReversed()) {
    const [held] = await readNamedDays(root, registration, [input], FeedHealthContract, fileCache);
    if (held!.rows.length > 0) recorded.push(input);
    if (recorded.length === count) break;
  }
  return recorded.reverse();
}
