/** Which date window follows a captured, canonical UTC instant? */
import { TimestampSchema } from "@idhazh/common-contracts";

export const UtcInstantSchema = TimestampSchema.refine(value => {
  const instant = Date.parse(value);
  return Number.isFinite(instant) && new Date(instant).toISOString().replace(".000Z", "Z") === value;
}, "must be a valid UTC instant");

const dayMilliseconds = 86_400_000;

export function requiredUtcDays(now: string, lookbackDays: number): string[] {
  UtcInstantSchema.parse(now);
  if (!Number.isSafeInteger(lookbackDays) || lookbackDays < 0) {
    throw new Error("Lookback window must be a nonnegative integer");
  }
  const midnight = Date.parse(`${now.slice(0, 10)}T00:00:00Z`);
  return Array.from({ length: lookbackDays + 1 }, (_, index) =>
    new Date(midnight - (lookbackDays - index) * dayMilliseconds).toISOString().slice(0, 10));
}
