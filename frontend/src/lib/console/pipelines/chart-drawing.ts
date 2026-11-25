/** One private day record drives the drawing rule, flow and daily evidence. */
import { daysInWindow, type TimeWindow } from '../../charts/viewport';
import { DRAWABLE } from '../../payload/drawing';
import type { ChartTypeTotals } from './visual-attempts';

export { chartRule, minutesText, coverageText } from '../../charts/glance';
export { chartFlow } from './drawing-flow';
import type { FlowDay } from './drawing-flow';

export function visualsPublished(days: readonly FlowDay[]): number {
	return days.reduce((total, day) => total + day.published, 0);
}

export interface ChartTypeDay {
	date: string;
	proposed: ChartTypeTotals | null;
	saved: ChartTypeTotals | null;
	published: ChartTypeTotals | null;
}

export interface ChartTypeCount {
	type: string;
	proposed: number | null;
	saved: number | null;
	published: number | null;
	recordedProposed: number | null;
	recordedSaved: number | null;
}

export interface ChartTypeWindow {
	rows: ChartTypeCount[];
	coveredDays: number;
	selectedDays: number;
}

export function chartTypeCounts(days: readonly ChartTypeDay[], window: TimeWindow): ChartTypeWindow {
	const byDate = new Map(days.map((day) => [day.date, day]));
	const selected = daysInWindow(window);
	const types = new Set<string>(DRAWABLE);
	const proposed = new Map<string, number>(), saved = new Map<string, number>(), published = new Map<string, number>();
	const add = (counts: Map<string, number>, day: ChartTypeTotals) => {
		for (const [type, count] of Object.entries(day)) {
			types.add(type);
			counts.set(type, (counts.get(type) ?? 0) + count);
		}
	};
	let coveredDays = 0, publishedDays = 0;
	for (const date of selected) {
		const day = byDate.get(date);
		if (day === undefined) continue;
		if (day.proposed !== null && day.saved !== null) {
			add(proposed, day.proposed);
			add(saved, day.saved);
			coveredDays++;
		}
		if (day.published !== null) {
			add(published, day.published);
			publishedDays++;
		}
	}
	const complete = coveredDays === selected.length;
	const rows = [...types].map((type) => {
		const proposedCount = proposed.get(type) ?? 0;
		const savedCount = saved.get(type) ?? 0;
		return {
			type,
			proposed: complete ? proposedCount : null,
			saved: complete ? savedCount : null,
			published: publishedDays === selected.length ? published.get(type) ?? 0 : null,
			recordedProposed: !complete && proposedCount > 0 ? proposedCount : null,
			recordedSaved: !complete && savedCount > 0 ? savedCount : null
		};
	});
	return { rows, coveredDays, selectedDays: selected.length };
}
