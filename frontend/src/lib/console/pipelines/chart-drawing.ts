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
}

export function chartTypeCounts(days: readonly ChartTypeDay[], window: TimeWindow): ChartTypeCount[] {
	const byDate = new Map(days.map((day) => [day.date, day]));
	const selected = daysInWindow(window).map((date) => byDate.get(date));
	const types = new Set<string>(DRAWABLE);
	const total = (column: 'proposed' | 'saved' | 'published') => {
		const counts = new Map<string, number>();
		let complete = true;
		for (const day of selected) {
			const daily = day?.[column];
			if (daily == null) complete = false;
			else for (const [type, count] of Object.entries(daily)) {
				types.add(type);
				counts.set(type, (counts.get(type) ?? 0) + count);
			}
		}
		return (type: string) => complete ? counts.get(type) ?? 0 : null;
	};
	const proposed = total('proposed'), saved = total('saved'), published = total('published');
	return [...types].map((type) => ({ type, proposed: proposed(type), saved: saved(type), published: published(type) }));
}
