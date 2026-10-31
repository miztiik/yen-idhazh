/** For each potential class, how many visual attempts reach each stage, and where the rest stop? */
import type { Row } from '../../data/ledger';

/** The classes the extractor assigns, plus a bucket for attempts with none recorded. */
export const POTENTIAL_CLASSES = ['chartable', 'narrative', 'unclassified'] as const;
export const UNMEASURED = 'unmeasured';
export type PotentialGroup = (typeof POTENTIAL_CLASSES)[number] | typeof UNMEASURED;

/** Attempts that share every funnel-relevant cell on one UTC day. Counts keep the page small. */
export interface AttemptCount {
	date: string;
	potential: PotentialGroup;
	/** True when a plan was drafted, whether or not it survived. */
	drafted: boolean;
	/** Why no visual came of it; '' when none is recorded. */
	noneReason: string;
	/** True when the first validator check refused the plan as drafted. */
	refusedAsDrafted: boolean;
	/** The deepest downgrade rung searched; 0 when none was. */
	depth: number;
	/** `rendered`, `render_failed` or `absent`; '' when none is recorded. */
	state: string;
	n: number;
}

export interface FunnelStep {
	label: string;
	count: number;
	/** Whole percent of the class denominator; null when the class has none. */
	share: number | null;
	/** More than the stage before, so the counts are not one flow. */
	grew: boolean;
}
export interface FunnelLoss { label: string; count: number }
export interface ClassFunnel {
	group: PotentialGroup;
	/** The stage every share in this class is measured against. */
	denominator: number;
	steps: FunnelStep[];
	/** Where the attempts that were not written went, by recorded reason. */
	losses: FunnelLoss[];
	/** Final outcomes only; they should add up to the denominator. */
	ends: FunnelStep[];
	/** Plans the ends do not account for; a non-zero value is shown, never hidden. */
	unaccounted: number;
}

const text = (row: Row, column: string): string => {
	const value = row[column];
	return value === null || value === undefined ? '' : String(value);
};

/** Group ledger rows into counts. Cells are the console's text cells: missing is ''. */
export function attemptCounts(rows: readonly Row[]): AttemptCount[] {
	const found = new Map<string, AttemptCount>();
	for (const row of rows) {
		const potential = (POTENTIAL_CLASSES as readonly string[]).includes(text(row, 'potential_primary'))
			? text(row, 'potential_primary') as PotentialGroup : UNMEASURED;
		const depth = Number(text(row, 'downgrade_depth'));
		const next: AttemptCount = {
			date: text(row, 'date'), potential, drafted: text(row, 'decision') === 'visual',
			noneReason: text(row, 'none_reason'), refusedAsDrafted: text(row, 'rejection_reason') !== '',
			depth: Number.isFinite(depth) ? depth : 0, state: text(row, 'state'), n: 1
		};
		const key = JSON.stringify({ ...next, n: 0 });
		const held = found.get(key);
		if (held === undefined) found.set(key, next); else held.n += 1;
	}
	return [...found.values()];
}

const sum = (counts: readonly AttemptCount[]): number => counts.reduce((total, count) => total + count.n, 0);

function build(denominator: number, stages: readonly [string, number][], chained = true): FunnelStep[] {
	return stages.map(([label, count], index) => ({
		label, count,
		share: denominator === 0 ? null : Math.round((count / denominator) * 100),
		grew: chained && index > 0 && count > stages[index - 1][1]
	}));
}

function tally(counts: readonly AttemptCount[], label: (count: AttemptCount) => string): FunnelLoss[] {
	const found = new Map<string, number>();
	for (const count of counts) found.set(label(count), (found.get(label(count)) ?? 0) + count.n);
	return [...found].map(([name, total]) => ({ label: name, count: total }))
		.sort((a, b) => b.count - a.count || a.label.localeCompare(b.label));
}

const stopReason = (count: AttemptCount): string =>
	count.noneReason !== '' ? count.noneReason : count.state === 'render_failed' ? 'render_failed' : 'no reason recorded';

function groups(counts: readonly AttemptCount[]): { group: PotentialGroup; own: AttemptCount[] }[] {
	return ([...POTENTIAL_CLASSES, UNMEASURED] as PotentialGroup[]).map((group) => ({ group, own: counts.filter((count) => count.potential === group) }));
}

/** Every settled attempt, then drafted, then past the checks, then written. */
export function pipelineFunnels(counts: readonly AttemptCount[]): ClassFunnel[] {
	return groups(counts).map(({ group, own }) => {
		const planned = own.filter((count) => count.drafted);
		const passed = planned.filter((count) => count.noneReason === '');
		const written = own.filter((count) => count.state === 'rendered');
		return {
			group, denominator: sum(own), ends: [], unaccounted: 0,
			steps: build(sum(own), [
				['Attempted', sum(own)], ['Plan drafted', sum(planned)],
				['Passed the checks', sum(passed)], ['Written', sum(written)]
			]),
			losses: tally(own.filter((count) => count.state !== 'rendered'), stopReason)
		};
	});
}

/**
 * Of the drafted plans, how many were refused as drafted, reached each rung of
 * the downgrade ladder, and how they ended. Rungs come from the recorded depths.
 */
export function downgradeFunnels(counts: readonly AttemptCount[]): ClassFunnel[] {
	return groups(counts).map(({ group, own }) => {
		const planned = own.filter((count) => count.drafted);
		const deepest = planned.reduce((most, count) => Math.max(most, count.depth), 0);
		const stages: [string, number][] = [
			['Planned', sum(planned)],
			['Refused as drafted', sum(planned.filter((count) => count.refusedAsDrafted))],
			...Array.from({ length: deepest }, (_, index): [string, number] => [
				`Searched depth ${index + 1}`, sum(planned.filter((count) => count.depth > index))
			])
		];
		const done = sum(planned.filter((count) => count.state === 'rendered'));
		const none = sum(planned.filter((count) => count.noneReason !== ''));
		const failed = sum(planned.filter((count) => count.state === 'render_failed' && count.noneReason === ''));
		return {
			group, denominator: sum(planned), steps: build(sum(planned), stages), losses: [],
			ends: build(sum(planned), [['Rendered', done], ['None', none], ['Render failed', failed]], false),
			unaccounted: sum(planned) - done - none - failed
		};
	});
}
