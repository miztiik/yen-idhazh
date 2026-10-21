/** Applies Python ledger row precedence, ranked-cell refusal, and read-side identity validation. */
import { RowIdentitySchema } from "@idhazh/common-contracts";
import type { WriterIdentity } from "@idhazh/common-contracts";
import type { z } from "zod";
import type { LedgerPeriod } from "./ledger-types";

const RANKED_IDENTITY_CELLS = ["attempt", "unit_id", "pipeline_name", "task_name"] as const;

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function validateStoredIdentity(row: Record<string, unknown>): void {
  const identity = Object.fromEntries(
    Object.keys(RowIdentitySchema.shape).map((key) => [key, row[key]]),
  );
  RowIdentitySchema.parse(identity);
}

function refuseRankedContradictions(
  row: Record<string, unknown>,
  stamped: Record<string, unknown>,
): void {
  for (const key of RANKED_IDENTITY_CELLS) {
    if (Object.hasOwn(row, key) && row[key] !== stamped[key]) {
      throw new Error(`ledger row contradicts its writer identity at ${key}`);
    }
  }
}

export function buildIdentityCells(
  ledger: string,
  covers: string,
  identity: WriterIdentity,
  generatedUnitId: string,
): Record<string, unknown> {
  return {
    ledger,
    covers,
    run_id: identity.run_id,
    attempt: identity.attempt,
    job: identity.job,
    pipeline_name: identity.pipeline_name,
    task_name: identity.task_name,
    shard: identity.shard,
    unit_id: generatedUnitId,
  };
}

export function buildStoredRawRow(
  row: Record<string, unknown>,
  ledger: string,
  covers: string,
  identity: WriterIdentity,
  generatedUnitId: string,
): Record<string, unknown> {
  const stamped = buildIdentityCells(ledger, covers, identity, generatedUnitId);
  refuseRankedContradictions(row, stamped);
  const stored = { ...stamped, ...row };
  validateStoredIdentity(stored);
  return stored;
}

function isInsidePeriod(day: string, period: Extract<LedgerPeriod, { tier: "compact" }>): boolean {
  return period.period === "daily"
    ? day === period.covers
    : period.period === "monthly"
      ? day.startsWith(`${period.covers}-`)
      : day.startsWith(`${period.covers}-`);
}

export function buildStoredCompactRow<T extends object>(
  input: unknown,
  contract: z.ZodType<T>,
  ledger: string,
  period: Extract<LedgerPeriod, { tier: "compact" }>,
): Record<string, unknown> {
  if (!isObject(input) || !isObject(input.identity)) {
    throw new TypeError("compact rows require a row identity and contract row");
  }
  const identity = RowIdentitySchema.parse(input.identity);
  const row = contract.parse(input.row);
  if (!isObject(row)) throw new TypeError("ledger row contract did not produce an object");
  if (identity.ledger !== ledger || !isInsidePeriod(identity.covers, period)) {
    throw new Error(`compact ${ledger} rows must belong to the requested period`);
  }
  const identityRecord = identity as Record<string, unknown>;
  const rowRecord = row as Record<string, unknown>;
  const stored = { ...identityRecord, ...rowRecord };
  validateStoredIdentity(stored);
  return stored;
}
