/** Is a nonnegative endpoint counter difference available? */
import type { Observation } from "../probe/proc-reader";
import type { TaskUnavailableReason } from "./profile-schema";

export function calculateCounterDifference(
  start: number | null, end: number | null, reason: TaskUnavailableReason,
): Observation<number, TaskUnavailableReason> {
  return start === null || end === null ? { value: null, reason }
    : end < start ? { value: null, reason: "counter_reset" }
    : { value: end - start, reason: null };
}
