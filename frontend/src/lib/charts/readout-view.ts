/** Resolve the same exact reading for the standing strip and the hover tooltip. */
import type { Readout, ReadoutFacts, ReadoutLine } from './readout';

export interface ReadoutEntry {
	label: string;
	value: string;
	swatch: string | null;
	reserve: number;
	held?: boolean;
}

export interface ReadoutView {
	shape: 'columns' | 'record';
	heading: string;
	resting: boolean;
	one: boolean;
	entries: ReadoutEntry[];
}

function widest(values: readonly (string | null)[], missing: string, counted: readonly boolean[]): number {
	return values.reduce((most, value, column) =>
		Math.max(most, (value ?? (counted[column] ? missing : '')).length), 0);
}

export function readoutView(
	readout: Readout | ReadoutFacts | null,
	at: number | null = null,
	resting = false,
	eventRoom = false
): ReadoutView | null {
	if (readout === null) return null;
	if ('subject' in readout) {
		return {
			shape: 'record', heading: readout.subject, resting, one: false,
			entries: readout.facts.map((fact) => ({
				label: fact.label, value: fact.value ?? readout.notMeasured,
				swatch: fact.swatch, reserve: fact.reserve ?? 0
			}))
		};
	}
	if (readout.columns.length === 0) return null;
	const column = Math.min(readout.columns.length - 1, Math.max(0, at ?? readout.resting));
	const counted = readout.columns.map((_, index) =>
		readout.series.some((series) => series.values[index] !== null));
	const measured = counted[column] ?? false;
	const series: ReadoutEntry[] = measured
		? readout.series.map((series) => ({
			label: series.note === undefined ? series.label : `${series.label} (${series.note})`,
			value: series.values[column] ?? readout.notMeasured,
			swatch: series.swatch, reserve: widest(series.values, readout.notMeasured, counted)
		}))
		: [{ label: readout.notMeasuredAt[column] ?? readout.notMeasured, value: '', swatch: null, reserve: 0 }];
	const events = readout.events[column] ?? [];
	const none: ReadoutEntry[] = measured && events.length === 0 && readout.eventsNone !== ''
		? [{ label: readout.eventsNone, value: '', swatch: null, reserve: 0 }] : [];
	const most = eventRoom ? Math.max(0, ...readout.events.map((lines) => lines.length)) : 0;
	const roomiest = readout.events.flat().reduce<ReadoutLine | null>((best, line) =>
		best === null || line.label.length + line.value.length > best.label.length + best.value.length
			? line : best, null);
	const held: ReadoutEntry[] = readout.eventsNone === '' && roomiest !== null
		? Array.from({ length: Math.max(0, most - events.length) }, () => ({
			...roomiest, reserve: 0, held: true
		})) : [];
	return {
		shape: 'columns', heading: readout.columns[column], resting: at === null,
		one: readout.columns.length === 1,
		entries: [...series, ...events.map((line) => ({ ...line, reserve: 0 })), ...none, ...held]
	};
}
