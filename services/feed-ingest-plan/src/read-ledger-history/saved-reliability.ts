/** Which saved feed-read window supplies the requested calculation without mixing different questions? */
import type { FeedHealthReliability } from "@idhazh/common-contracts";
import { selectNewestCalculation } from "./saved-calculation";

type Snapshot = { at: string | null; value: FeedHealthReliability };
type Bounds = Pick<FeedHealthReliability, "from_day" | "through_day">;

export function selectSavedReliability(
  snapshots: readonly Snapshot[], bounds: Bounds, now: string,
): ReturnType<typeof selectNewestCalculation<FeedHealthReliability>> {
  const questions = new Map<string, { bounds: Bounds; snapshots: Snapshot[] }>();
  for (const snapshot of snapshots) {
    const { from_day, through_day } = snapshot.value;
    const key = `${from_day}:${through_day}`;
    const question = questions.get(key) ?? { bounds: { from_day, through_day }, snapshots: [] };
    question.snapshots.push(snapshot);
    questions.set(key, question);
  }
  const available = [...questions.values()].map(question => ({
    bounds: question.bounds, selection: selectNewestCalculation(question.snapshots, now),
  })).filter(question => question.selection.value !== null || question.selection.conflicting.length > 0);
  const matching = available.find(question => question.bounds.from_day === bounds.from_day
    && question.bounds.through_day === bounds.through_day);
  if (matching !== undefined) return matching.selection;
  const beforeEnd = available.filter(question => bounds.through_day === null
    || (question.bounds.through_day !== null && question.bounds.through_day <= bounds.through_day));
  const candidates = beforeEnd.length > 0 ? beforeEnd : available;
  const startDistance = (day: string | null) => bounds.from_day === null || day === null ? Infinity
    : Math.abs(Date.parse(`${day}T00:00:00Z`) - Date.parse(`${bounds.from_day}T00:00:00Z`));
  candidates.sort((left, right) => {
    const end = (right.bounds.through_day ?? "").localeCompare(left.bounds.through_day ?? "");
    if (end !== 0) return end;
    const distance = startDistance(left.bounds.from_day) - startDistance(right.bounds.from_day);
    if (!Number.isNaN(distance) && distance !== 0) return distance;
    return (right.bounds.from_day ?? "").localeCompare(left.bounds.from_day ?? "");
  });
  return candidates[0]?.selection ?? { value: null, conflicting: [] };
}
