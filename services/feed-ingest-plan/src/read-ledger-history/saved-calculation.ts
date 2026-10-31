/** Which saved calculation is newest under the recorded UTC clock precision? */
import { isDeepStrictEqual } from "node:util";
import { instantBounds, validRecordedInstant } from "@idhazh/common-contracts";

export function selectNewestCalculation<T>(
  rows: readonly { at: string | null; value: T }[], now: string,
): { value: T | null; conflicting: readonly T[] } {
  const available = rows.filter(row => row.at === null
    || (validRecordedInstant(row.at) && Date.parse(row.at) <= Date.parse(now)));
  const timed = available.filter(row => row.at !== null);
  const latest = timed.length ? Math.max(...timed.map(row => instantBounds(row.at!).lower)) : null;
  const candidates = latest === null ? available
    : timed.filter(row => instantBounds(row.at!).upper > latest);
  if (candidates.length === 0) return { value: null, conflicting: [] };
  const value = candidates[0]!.value;
  return candidates.every(candidate => isDeepStrictEqual(candidate.value, value))
    ? { value, conflicting: [] } : { value: null, conflicting: candidates.map(candidate => candidate.value) };
}
