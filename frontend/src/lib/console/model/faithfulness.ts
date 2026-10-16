import type { Row } from '../../data/ledger';
import { evalDays, matchFloor, matchRules, widerNote } from '../eval-instruments';
import { textRows } from './rows';

export function faithfulness(rows: readonly Row[], thresholds: { high: number; low: number }, axis: { step: number; floorMax: number }) {
	const days = evalDays(textRows(rows));
	const floor = matchFloor(days, thresholds, axis);
	return {
		days, floor, rules: matchRules(thresholds, floor), wider: widerNote(days, days.length),
		series: [{
			label: 'median faithfulness', token: '--chart-1' as const,
			points: days.map((day) => ({
				date: day.date, value: day.matchMid,
				...(day.matchLow === null || day.matchHigh === null ? {} :
					{ spread: { low: day.matchLow, high: day.matchHigh } })
			}))
		}]
	};
}
