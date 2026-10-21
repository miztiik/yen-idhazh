/** Routes validated public writes to the raw or compact persistence unit. */
import type { PersistLedgerInput, PersistLedgerResult } from "./ledger-types";
import { persistCompactLedger } from "./persist-compact";
import { persistRawLedger } from "./persist-raw";

export async function persistLedger<T extends object>(
  input: PersistLedgerInput<T>,
): Promise<PersistLedgerResult> {
  if (input.period.tier === "raw") {
    return persistRawLedger(input as Extract<PersistLedgerInput<T>, { period: { tier: "raw" } }>);
  }
  return persistCompactLedger(input as Extract<PersistLedgerInput<T>, { period: { tier: "compact" } }>);
}
