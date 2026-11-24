/** How did each digest's canary pairs compare with the key saved for that attempt? */
import type { Row } from '../data/ledger';
import { isDay } from '../data/slice-shapes';
import { judgeCompact, judgeCount, judgeNumber, verdictOf, type JudgeReading, type Verdict } from './judge-observations';

const CANARY_SET_CONFIG = 'judges/content-similarity-canaries.json';

export const CANARY_CATEGORIES = [
	{ expected: 'YES', label: 'Same event' },
	{ expected: 'UNCLEAR', label: 'Not enough detail' },
	{ expected: 'NO', label: 'Different events' }
] as const;

// Top to bottom: YES above UNCLEAR, with NO anchoring the bottom.
export const CANARY_BANDS = ['YES', 'UNCLEAR', 'changed', 'invalid', 'missing', 'NO'] as const;
export type CanaryBand = (typeof CANARY_BANDS)[number];

export interface CanaryGroup {
	expected: number;
	matched: number;
	counts: Record<CanaryBand, number>;
}

function emptyGroup(): CanaryGroup {
	return { expected: 0, matched: 0, counts: { YES: 0, UNCLEAR: 0, NO: 0, changed: 0, invalid: 0, missing: 0 } };
}

export function judgeCanaries(cells: Row) {
	const key = judgeCompact(cells.canary_expectations);
	const answers = judgeCompact(cells.canary_answers);
	const unreadable = cells.canary_answers != null && answers === null;
	const entries = Object.entries(key ?? {});
	const keyState = cells.canary_expectations == null ? 'absent'
		: entries.length > 0 && entries.every(([, verdict]) => verdictOf(verdict) !== null) ? 'saved' : 'invalid';
	const version = judgeCompact(cells.config_versions)?.[CANARY_SET_CONFIG];
	const setVersion = typeof version === 'string' && isDay(version) ? version : null;
	const groups = { YES: emptyGroup(), UNCLEAR: emptyGroup(), NO: emptyGroup() };
	const ids = keyState === 'saved' ? entries.map(([id]) => id) : Object.keys(answers ?? {});
	const items = ids.map((id) => {
		const expected = keyState === 'saved' ? verdictOf(key?.[id]) : null;
		const filed = answers !== null && Object.hasOwn(answers, id);
		const answer = filed ? answers[id] : undefined;
		const original = Array.isArray(answer) ? verdictOf(answer[0]) : null;
		const reversed = Array.isArray(answer) ? verdictOf(answer[1]) : null;
		const band: CanaryBand = original !== null && reversed !== null
			? original === reversed ? original : 'changed'
			: filed || unreadable ? 'invalid' : 'missing';
		const outcome = band === 'changed' ? 'Changed on reversal'
			: band === 'invalid' ? 'Invalid'
			: band === 'missing' ? 'Missing'
			: expected === null ? 'Not graded'
			: band === expected ? 'Matched' : 'Differed';
		if (expected !== null) {
			const group = groups[expected];
			group.expected++;
			group.counts[band]++;
			if (band === expected) group.matched++;
		}
		return { id, expected, original, reversed, band, outcome };
	});
	return {
		items, groups, keyState, setVersion,
		eligible: judgeCount(cells.canary_kappa_pairs), kappa: judgeNumber(cells.canary_kappa)
	};
}

export type CanaryReading = ReturnType<typeof judgeCanaries>;

export interface CanaryDay {
	date: string;
	record: CanaryReading | null;
	setChanged: boolean;
}

export function judgeCanaryDays(calendar: readonly string[], readings: ReadonlyMap<string, JudgeReading>): CanaryDay[] {
	let lastVersion: string | null = null;
	return calendar.map((date) => {
		const reading = readings.get(date);
		const record = reading ? judgeCanaries(reading.cells) : null;
		const version = record?.setVersion ?? null;
		const setChanged = lastVersion !== null && version !== null && version !== lastVersion;
		if (version !== null) lastVersion = version;
		return { date, record, setChanged };
	});
}
