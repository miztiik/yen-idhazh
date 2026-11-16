/** What values and record availability do the model cards show? */
import type { ModelDay } from '../../server/model-work';
import type { MovementPolarity } from '../../charts/theme';
import type { TimeWindow } from '../../charts/viewport';
import { checkedRule, completeModelRule, type ModelRule } from '../../charts/d3/model-rule';
import { coveredDays } from '../../data/slice';
import type { RecordRead } from '../recording';

export interface CardReads {
	article: RecordRead;
	score: RecordRead;
}

export function cardReadState(reads: CardReads, window: TimeWindow): 'quiet' | 'missing' {
	const complete = [reads.article, reads.score].every((read) => {
		if (read.state !== 'read' || read.first > window.start || read.through < window.end) return false;
		if (read.lostDays.some((date) => date >= window.start && date <= window.end)) return false;
		return !Object.entries(read.setAside).some(([date, count]) => {
			const period = date.length === 4 ? 'yearly' : date.length === 7 ? 'monthly' : 'daily';
			const span = coveredDays(period, date);
			return count > 0 && span.first <= window.end && span.last >= window.start;
		});
	});
	return complete ? 'quiet' : 'missing';
}

export const cardColumns: readonly { key: string; label: string; line: string; polarity: MovementPolarity }[] = [
	{ key: 'summaries', label: 'Published summaries checked', line: '', polarity: 'no-agreed-direction' },
	{ key: 'part', label: 'Article read only in part', line: 'The article was too long, so the machine read the start and stopped.', polarity: 'lower-is-better' },
	{ key: 'part-pct', label: 'Read only in part, as a percent', line: "The same articles, against the day's own count, so a busy day and a quiet one compare.", polarity: 'lower-is-better' },
	{ key: 'per-item', label: 'Time to write one', line: 'How long the machine takes on one article. The second figure is the articles it read only the start of.', polarity: 'lower-is-better' },
	{ key: 'minutes', label: 'Model minutes', line: '', polarity: 'no-agreed-direction' },
	{ key: 'too-long', label: 'Too long to send', line: 'The article and the instructions together did not fit, so the machine was never asked.', polarity: 'lower-is-better' },
	{ key: 'failed', label: 'Failed', line: '', polarity: 'lower-is-better' }
];

export function cardValue(day: ModelDay, key: string): number | null {
	const values: Record<string, number | null> = {
		summaries: day.summaries, part: day.readInPart, 'part-pct': day.readInPartPct,
		'per-item': day.perItemMs, minutes: day.totalMs,
		'too-long': day.refusedForLength, failed: day.failed
	};
	if (!(key in values)) throw new Error(`No model card declares ${key}.`);
	return values[key];
}

export function cardText(value: number | null, key: string): string {
	if (value === null) return 'not measured';
	if (key === 'per-item' || key === 'minutes') {
		const rounded = Math.round(value / (key === 'minutes' ? 60000 : 1000));
		const figure = rounded === 0 && value > 0 ? '<1' : String(rounded);
		return key === 'minutes' ? `${figure} min` : `${figure} s`;
	}

	return `${value}${key === 'part-pct' ? '%' : ''}`;
}

export function cardTrendDays<T extends { date: string }>(days: readonly T[]): T[] {
	const newest = days.at(-1)?.date;
	if (newest === undefined) return [];
	const first = new Date(`${newest}T00:00:00Z`);
	first.setUTCDate(first.getUTCDate() - 13);
	return days.filter((day) => day.date >= first.toISOString().slice(0, 10));
}

/** Only gaps inside this card's measured history need a card-specific warning. */
export function cardModelRule(rule: ModelRule, dates: readonly string[]): ModelRule {
	checkedRule(rule);
	if ('declined' in rule) return rule;
	const first = dates[0];
	const last = dates.at(-1);
	return completeModelRule({
		changes: rule.changes.filter((change) => first !== undefined && last !== undefined &&
			change.date >= first && change.date <= last),
		note: null
	}, dates);
}
