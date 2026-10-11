/** What did native extraction find, and how many distinct articles carry recorded flags? */
import type { Row } from '../../data/ledger';
import { finiteCell } from '../rates';
import { daysInWindow, type TimeWindow } from '../../charts/viewport';
import type { ExtractionDay } from '../../charts/extraction-trend';

export function nativeExtraction(items: readonly Row[], evaluations: readonly Row[] | null) {
	const byUrl = new Map<string, Row>();
	for (const row of [...items].sort((a, b) => String(a.date).localeCompare(String(b.date)))) {
		if (typeof row.url_key !== 'string' || row.url_key === '') continue;
		const held = byUrl.get(row.url_key) ?? {};
		byUrl.set(row.url_key, { ...held, ...Object.fromEntries(Object.entries(row).filter(([, value]) => value !== null)) });
	}

	export function extractionYield(days: readonly ExtractionDay[], window: TimeWindow) {
		const recorded = new Map(days.map((day) => [day.date, day]));
		return [
			{ label: 'Enough figures to draw', token: '--chart-1', key: 'chartable' as const },
			{ label: 'Published carrying a chart', token: '--chart-4', key: 'charted' as const }
		].map(({ label, token, key }) => ({
			label, token,
			points: daysInWindow(window).map((date) => ({ date, value: recorded.get(date)?.[key] ?? null }))
		}));
	}
	const classes = new Map<string, number>();
	const wouldNotReslice = items.filter((row) => row.span_integrity === false).length;
	let elementsFound = 0;
	let elementsMeasured = 0;
	const notProse = new Set<string>();
	const contaminated = new Set<string>();
	for (const row of items) {
		if (typeof row.url_key !== 'string' || row.url_key === '') continue;
		if (row.code === 'not_prose') notProse.add(row.url_key);
		if (row.code === 'contaminated') contaminated.add(row.url_key);
	}
	for (const row of byUrl.values()) {
		if (typeof row.element_class === 'string' && row.element_class !== '') {
			classes.set(row.element_class, (classes.get(row.element_class) ?? 0) + 1);
		}
		const elements = finiteCell(row.elements_found);
		if (elements !== null) { elementsFound += elements; elementsMeasured += 1; }
	}
	const checked = new Map<string, { date: string; readings: Set<boolean> }>();
	for (const row of evaluations ?? []) {
		if (typeof row.url_key !== 'string' || row.url_key === '') continue;
		const date = typeof row.date === 'string' ? row.date : '';
		const previous = checked.get(row.url_key);
		if (typeof row.extraction_suspect !== 'boolean') {
			if (previous === undefined) checked.set(row.url_key, { date: '', readings: new Set() });
			continue;
		}
		if (previous === undefined || date > previous.date) {
			checked.set(row.url_key, { date, readings: new Set([row.extraction_suspect]) });
		} else if (date === previous.date) previous.readings.add(row.extraction_suspect);
	}
	const suspect = [...checked.values()].filter((value) => value.readings.size === 1 && value.readings.has(true)).length;
	const unmeasured = [...checked.values()].filter((value) => value.readings.size !== 1).length;
	return {
		articles: byUrl.size,
		classes: [...classes].map(([label, count]) => ({ label, count }))
			.concat({ label: 'would not re-slice', count: wouldNotReslice })
			.sort((a, b) => b.count - a.count || a.label.localeCompare(b.label)),
		wouldNotReslice, elementsFound: elementsMeasured === 0 ? null : elementsFound, elementsMeasured,
		notProse: notProse.size, contaminated: contaminated.size,
		checked: evaluations === null ? null : checked.size, suspect: evaluations === null ? null : suspect,
		suspectUnknown: evaluations === null ? null : unmeasured,
		suspectShare: evaluations === null || checked.size === 0 || unmeasured > 0 ? null : suspect / checked.size,
		note: 'These counts include articles that were not published. Nothing acts on these numbers.'
	};
}
