/** Which preset, if any, names this closed span ending on today's UTC day? */
import { daysBetween } from '../../data/slice';
import type { DateStamp } from '../../data/slice-shapes';

export function matchPresetSpan(from: DateStamp, end: DateStamp, today: DateStamp, presets: readonly number[]): number | null {
	if (end !== today || from > end) return null;
	const days = daysBetween(from, end).length;
	return presets.includes(days) ? days : null;
}
