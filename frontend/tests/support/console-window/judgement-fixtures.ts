/** The independent judge days and props used by focused Judgement window checks. */

import { daysInWindow, windowOfDays } from '../../../src/lib/charts/viewport';

import type { JudgeDay, LineDay } from '../../../src/lib/console/merge-line';

import { DRAWN_THROUGH, DRAWN_AT } from './readout';
export { DRAWN_AT } from './readout';
export const JUDGED_THROUGH = DRAWN_THROUGH;

/** The three gates, the two limits and the share floor the cases hand the
 * panels. Written here, so every number in a sentence below is one this file chose. */
export const GATES = { minimumNegatives: 200, minimumDays: 10, minimumAboveLine: 30 };
export const LIMITS = { disagreementMax: 0.15, unclearMax: 0.35 };
export const SHARE_FLOOR = 5;

/** The size a panel is drawn at moves no word, so every case draws at one size. */

/** A record holding all three counts the gates ask for, and one short of all three. */
export const FILLED = { negativesOnRecord: 250, daysOnRecord: 12, aboveLineOnRecord: 40 };
export const FILLING = {
	negativesOnRecord: 120,
	daysOnRecord: 6,
	aboveLineOnRecord: 12,
	heldReason: 'sheet_too_small'
};

/** One day of the judge's record: nothing read and nothing held, unless a case says so.
 * A case that reads pairs writes out how many agreed, so the counts nest as the
 * run writes them. */
export function judgeDay(date: string, over: Partial<JudgeDay> = {}): JudgeDay {
	return {
		date,
		disagreementRate: 0,
		unclearRate: 0,
		pairsJudged: 0,
		pairsUsable: 0,
		negativesOnRecord: 0,
		aboveLineOnRecord: 0,
		daysOnRecord: 0,
		heldReason: 'none',
		...over
	};
}

/** One fitted day of the merge line. */
export function lineDay(date: string): LineDay {
	return {
		date,
		previous: 0.94,
		proposed: 0.95,
		applied: 0.943,
		clampKind: 'none',
		heldReason: 'none',
		maxDownStep: 0.01,
		maxUpStep: 0.003
	};
}

/** The knobs the route hands the merge line, which draws its axis over the band.
 * The switch is off unless a case turns it on. */
export const LINE_KNOBS = { band_low: 0.88, band_high: 1, enabled: false, applied_lookback_days: 7 };

/** One panel in one state at one window, and every word it owes about its days. */
export type SpanCase =
	| {
			surface: 'judge-agreement' | 'record-gates';
			preset: number;
			state: string;
			days: JudgeDay[];
			words: string;
	  }
	| {
			surface: 'merge-line';
			preset: number;
			state: string;
			days: LineDay[];
			words: string;
			/** The dashed rule's label. */
			label: string;
	  };

/** Where each panel prints its sentences about its own days. */
export const SAID = {
	'judge-agreement': '[data-agreement-state]',
	'record-gates': '[data-gates-note]',
	'merge-line': '[data-line-state]'
} as const;
export function propsOf(one: SpanCase): Record<string, unknown> {
	const viewport = windowOfDays(JUDGED_THROUGH, one.preset, 'right');
	switch (one.surface) {
		case 'judge-agreement':
			return { days: one.days, limits: LIMITS, attemptsFloor: SHARE_FLOOR, viewport, ...DRAWN_AT };
		case 'record-gates':
			return {
				days: one.days,
				dates: daysInWindow(viewport),
				gates: GATES,
				viewport,
				readoutMaxShare: DRAWN_AT.readoutMaxShare
			};
		case 'merge-line':
			return {
				days: one.days,
				knobs: LINE_KNOBS,
				builtWith: 0.94,
				markedApart: null,
				viewport,
				...DRAWN_AT
			};
	}
}
export function appliedOn(date: string, line: number): LineDay {
	return { ...lineDay(date), proposed: line, applied: line };
}
