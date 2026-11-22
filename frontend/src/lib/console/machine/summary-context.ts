/** How much of each recorded slot did summary prompts use on each UTC day? */
import type { Row } from '../../data/ledger';
import type { SeriesInput } from '../../charts/d3/dateSeries';
import { finiteCell } from '../rates';

const UPPER_PROMPT_PERCENTILE = 0.9;
export const CONTEXT_CAPACITY_TOKEN = '--chart-marker';
export const CONTEXT_PROMPT_TOKEN = '--chart-measure';

interface SlotReading {
	capacity: number;
	used: number;
	room: number;
	measured: number;
}

export interface ContextDay {
	date: string;
	recorded: number;
	measured: number;
	slots: SlotReading[];
}

function positive(value: Row[string] | undefined): number | null {
	const number = finiteCell(value);
	return number !== null && number > 0 ? number : null;
}

export function summaryContext(rows: readonly Row[], calendar: readonly string[]) {
	const buckets = new Map(calendar.map((date) => [date, { recorded: 0, measured: 0, slots: new Map<number, number[]>() }]));
	const prompts: number[] = [];
	let cut = 0, measured = 0;
	let peak: { used: number; capacity: number; share: number } | null = null;
	for (const row of rows) {
		const day = typeof row.date === 'string' ? buckets.get(row.date) : undefined;
		if (day === undefined) continue;
		if (positive(row.truncation_cap_tokens) !== null) cut++;
		const used = positive(row.summary_input_tokens);
		if (used === null) continue;
		prompts.push(used);
		day.recorded++;
		const context = positive(row.n_ctx_configured), parallel = positive(row.n_parallel);
		if (context === null || parallel === null) continue;
		const capacity = context / parallel;
		if (!Number.isFinite(capacity) || capacity <= 0) continue;
		const share = used / capacity;
		if (peak === null || share > peak.share || (share === peak.share && used > peak.used)) {
			peak = { used, capacity, share };
		}
		const group = day.slots.get(capacity) ?? [];
		group.push(used);
		day.slots.set(capacity, group);
		day.measured++;
		measured++;
	}
	const days: ContextDay[] = [...buckets].map(([date, day]) => ({
		date, recorded: day.recorded, measured: day.measured,
		slots: [...day.slots].sort(([a], [b]) => a - b).map(([capacity, values]) => {
			const used = values.sort((a, b) => a - b)[Math.ceil(UPPER_PROMPT_PERCENTILE * values.length) - 1];
			return { capacity, used, room: capacity - used, measured: values.length };
		})
	}));
	return { days, prompts, cut, peak, measured };
}

/** Mixed settings on one day are separate marks, not an invented daily setting. */
export function summaryContextSeries(days: readonly ContextDay[]): SeriesInput[] {
	const capacity: SeriesInput = {
		label: 'Slot capacity', token: CONTEXT_CAPACITY_TOKEN, lineStyle: 'step-guide',
		points: days.map(({ date, slots }) => ({ date, value: slots.length === 1 ? slots[0].capacity : null }))
	};
	const usage: SeriesInput = {
		label: 'Prompt used (p90)', token: CONTEXT_PROMPT_TOKEN, lineStyle: 'step',
		spreadLabels: { low: 'Prompt used', high: 'Slot capacity' },
		points: days.map(({ date, slots }) => {
			if (slots.length !== 1) return { date, value: null };
			const [{ used, room, capacity }] = slots;
			return { date, value: used, ...(room < 0 ? {} : { spread: { low: used, high: capacity } }) };
		})
	};
	const mixed = new Map<number, { date: string; used: number }[]>();
	for (const day of days) {
		if (day.slots.length < 2) continue;
		for (const slot of day.slots) {
			const points = mixed.get(slot.capacity) ?? [];
			points.push({ date: day.date, used: slot.used });
			mixed.set(slot.capacity, points);
		}
	}
	return [capacity, usage, ...[...mixed].flatMap(([size, points]): SeriesInput[] => [
		{ label: `Slot capacity (${size})`, token: CONTEXT_CAPACITY_TOKEN, lineStyle: 'points',
			points: points.map(({ date }) => ({ date, value: size })) },
		{ label: `Prompt used (slot ${size})`, token: CONTEXT_PROMPT_TOKEN, lineStyle: 'points',
			points: points.map(({ date, used }) => ({ date, value: used })) }
	])];
}
