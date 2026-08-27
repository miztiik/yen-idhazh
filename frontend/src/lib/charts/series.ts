import { daysInWindow, type TimeWindow } from './viewport';

export const TELEMETRY_COLUMNS = [
	'date',
	'run_id',
	'item_id',
	'vertical',
	'source_id',
	'stage',
	'outcome',
	'code',
	'source_words',
	'summary_words'
] as const;

export type TelemetryColumn = (typeof TELEMETRY_COLUMNS)[number];

export interface TelemetryRow {
	date: string;
	run_id: string;
	item_id: string;
	vertical: string;
	source_id: string;
	stage: string;
	outcome: string;
	code: string;
	source_words: number | null;
	summary_words: number | null;
}

export interface CompressionPoint {
	date: string;
	item_id: string;
	source_words: number;
	summary_words: number;
	truncation_flagged: boolean;
}

export interface SummaryBand {
	min_source_words: number;
	target_words_min: number;
	target_words_max: number;
}

/** One stage's day: the median, and the counts behind it.
 *
 * `ms` is null where nothing was timed. Zero is a measurement - a cheap stage
 * finishes inside a millisecond clock's own resolution - so the two facts
 * cannot share a value. `timed` against `total` carries the third one: a day
 * timed in full and a day timed in part are not the same day either.
 */
export interface StageTiming {
	ms: number | null;
	timed: number;
	total: number;
}

/** One day's median milliseconds per stage, over the item-health census. */
export interface StageTimingDay {
	date: string;
	items: number;
	fetch: StageTiming;
	extract: StageTiming;
	summarize: StageTiming;
	score: StageTiming;
}

/** The spread of one day's per-item rates. A candle, never an average.
 *
 * The spread is the point. A worker summarises its short articles first and its
 * long ones last, so the slowest item of a day is several times slower than the
 * fastest, and a single number hides the fact that the two ends moved apart.
 */
export interface RateSpread {
	min: number;
	p25: number;
	median: number;
	p75: number;
	max: number;
}

/** One run's median rates. Four of these sit behind a day's candle. */
export interface ThroughputRun {
	runId: string;
	items: number;
	read: number;
	write: number;
}

export interface ThroughputDay {
	date: string;
	items: number;
	read: RateSpread;
	write: RateSpread;
	/** The whole day's tokens over the whole day's milliseconds. Weighted by
	 * work done, unlike the median, which weighs a release note like a feature. */
	readTps: number;
	writeTps: number;
	cacheHitPct: number;
	runs: ThroughputRun[];
	/** What wrote the day, where a ledger says. Two days on different models are
	 * two measurements, so nothing compares them. */
	model: string | null;
}

export interface StageFailureDay {
	date: string;
	attempts: number;
	failures: number;
	rate: number | null;
	codes: Record<string, number>;
}

export interface StageFailureSeries {
	stage: 'fetch' | 'extract' | 'summarize';
	label: string;
	days: StageFailureDay[];
}

export const FAILURE_STAGES: StageFailureSeries['stage'][] = ['fetch', 'extract', 'summarize'];

function parseCsv(text: string): string[][] {
	const rows: string[][] = [];
	let row: string[] = [];
	let cell = '';
	let quoted = false;
	for (let index = 0; index < text.length; index += 1) {
		const ch = text[index];
		if (quoted) {
			if (ch === '"' && text[index + 1] === '"') {
				cell += '"';
				index += 1;
			} else if (ch === '"') {
				quoted = false;
			} else {
				cell += ch;
			}
		} else if (ch === '"') {
			quoted = true;
		} else if (ch === ',') {
			row.push(cell);
			cell = '';
		} else if (ch === '\n' || (ch === '\r' && text[index + 1] === '\n')) {
			if (ch === '\r') index += 1;
			row.push(cell);
			rows.push(row);
			row = [];
			cell = '';
		} else {
			cell += ch;
		}
	}
	if (cell !== '' || row.length > 0) {
		row.push(cell);
		rows.push(row);
	}
	return rows.filter((cells) => cells.some((cellText) => cellText !== ''));
}

function numberCell(value: string): number | null {
	if (value === '') return null;
	const parsed = Number(value);
	return Number.isFinite(parsed) ? parsed : null;
}

export function parseTelemetryCsv(text: string): TelemetryRow[] {
	const rows = parseCsv(text);
	const header = rows[0] ?? [];
	if (TELEMETRY_COLUMNS.some((name, index) => header[index] !== name)) {
		throw new Error('telemetry projection header did not match the contract');
	}
	return rows.slice(1).map((cells) => ({
		date: cells[0] ?? '',
		run_id: cells[1] ?? '',
		item_id: cells[2] ?? '',
		vertical: cells[3] ?? '',
		source_id: cells[4] ?? '',
		stage: cells[5] ?? '',
		outcome: cells[6] ?? '',
		code: cells[7] ?? '',
		source_words: numberCell(cells[8] ?? ''),
		summary_words: numberCell(cells[9] ?? '')
	}));
}

export function telemetryCsv(rows: TelemetryRow[]): string {
	const body = rows.map((row) =>
		TELEMETRY_COLUMNS.map((column) => {
			const value = row[column];
			return value === null ? '' : String(value);
		}).join(',')
	);
	return `${TELEMETRY_COLUMNS.join(',')}\n${body.join('\n')}${body.length ? '\n' : ''}`;
}

export function datesIn(rows: TelemetryRow[]): string[] {
	return [...new Set(rows.map((row) => row.date).filter(Boolean))].sort();
}

export function rowsInWindow<T extends { date: string }>(rows: T[], window: TimeWindow): T[] {
	return rows.filter((row) => row.date >= window.start && row.date <= window.end);
}

export function failureSeries(rows: TelemetryRow[], window: TimeWindow): StageFailureSeries[] {
	const byDate = new Map<string, TelemetryRow[]>();
	for (const row of rowsInWindow(rows, window)) {
		byDate.set(row.date, [...(byDate.get(row.date) ?? []), row]);
	}
	return FAILURE_STAGES.map((stage) => ({
		stage,
		label: stage,
		days: daysInWindow(window).map((date) => {
			const group = byDate.get(date) ?? [];
			const failures = group.filter((row) => row.outcome === 'failed' && row.stage === stage);
			const codes: Record<string, number> = {};
			for (const row of failures) {
				const key = row.code || 'unknown';
				codes[key] = (codes[key] ?? 0) + 1;
			}
			return {
				date,
				attempts: group.length,
				failures: failures.length,
				rate: group.length === 0 ? null : failures.length / group.length,
				codes
			};
		})
	}));
}

export function failedRows(rows: TelemetryRow[], window: TimeWindow, code: string | null): TelemetryRow[] {
	return rowsInWindow(rows, window)
		.filter((row) => row.outcome === 'failed')
		.filter((row) => code === null || row.code === code)
		.sort((a, b) => b.date.localeCompare(a.date) || a.item_id.localeCompare(b.item_id));
}
