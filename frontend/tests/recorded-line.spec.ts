/** Which line did a day's last build record? Read from run records the test writes.
 *
 * `readRecordedLine` opens the one `run.json` of the date it is handed and
 * answers the line that the build which finished last grouped the day at. Every
 * record here is written by the test into its own output folder, so no case
 * depends on what the canary or the archive holds.
 *
 * No build and no browser: this file is in the `logic` group.
 */

import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { expect, test } from '@playwright/test';

import { readRecordedLine } from '../src/lib/server/recorded-line';

/** The day every case asks about. */
const DAY = '2030-06-15';

/** One build's record: its ordinal, the line it grouped the day at, and when it
 * finished. With no time, the record carries no `completed_at` key at all. */
function build(n: number, line: number, completedAt?: string): Record<string, unknown> {
	return {
		run_id: `${DAY}-${n}`,
		n,
		...(completedAt === undefined ? {} : { completed_at: completedAt }),
		same_story_floor_applied: line
	};
}

/** A record written before the run record carried a line: no line key at all. */
function buildWithNoLine(n: number, completedAt: string): Record<string, unknown> {
	return { run_id: `${DAY}-${n}`, n, completed_at: completedAt };
}

/** Writes `content` as the day's `run.json` under a root of this test's own,
 * and returns the root. */
function rootHolding(content: string): string {
	const root = test.info().outputPath('digest');
	mkdirSync(join(root, '2030', '06', '15'), { recursive: true });
	writeFileSync(join(root, '2030', '06', '15', 'run.json'), content);
	return root;
}

/** What `work` returned, and every line it printed with `console.warn`, where
 * the site build prints. */
function warnings<T>(work: () => T): { result: T; warned: string[] } {
	const warned: string[] = [];
	const original = console.warn;
	console.warn = (...parts: unknown[]) => {
		warned.push(parts.map(String).join(' '));
	};
	try {
		return { result: work(), warned };
	} finally {
		console.warn = original;
	}
}

/** Each day's builds, in the order its file lists them, and the line written out. */
const CASES: { state: string; runs: Record<string, unknown>[]; line: number | null }[] = [
	{
		state: 'a build at 18:00 recorded 0.937 and a build at 23:10 recorded 0.940',
		runs: [build(1, 0.937, '2030-06-15T18:00:00Z'), build(2, 0.94, '2030-06-15T23:10:00Z')],
		line: 0.94
	},
	{
		state: 'the same two builds are listed newest first, as a re-run of an earlier build leaves them',
		runs: [build(2, 0.94, '2030-06-15T23:10:00Z'), build(1, 0.937, '2030-06-15T18:00:00Z')],
		line: 0.94
	},
	{
		state: 'two builds finished at the same second, and the one listed later recorded 0.940',
		runs: [build(1, 0.937, '2030-06-15T23:10:00Z'), build(2, 0.94, '2030-06-15T23:10:00Z')],
		line: 0.94
	},
	{
		state: 'the build listed last wrote no time, so it counts as the oldest',
		runs: [build(1, 0.937, '2030-06-15T23:10:00Z'), build(2, 0.94)],
		line: 0.937
	},
	{
		state: 'every build ran before the run record carried a line',
		runs: [buildWithNoLine(1, '2030-06-15T06:20:00Z'), buildWithNoLine(2, '2030-06-15T12:20:00Z')],
		line: null
	}
];

test.describe('the line a published day was built with, from its own run record', () => {
	for (const one of CASES) {
		test(`THE ORACLE: answers ${one.line === null ? 'no line' : one.line.toFixed(3)} when ${one.state}`, () => {
			const root = rootHolding(JSON.stringify({ date: DAY, runs: one.runs }));

			const { result, warned } = warnings(() => readRecordedLine(DAY, root));

			expect(result).toBe(one.line);
			expect(warned, 'a record that reads warns nothing').toEqual([]);
		});
	}

	test('a day with no run record answers no line, and warns nothing', () => {
		const root = test.info().outputPath('digest');
		mkdirSync(root, { recursive: true });

		const { result, warned } = warnings(() => readRecordedLine(DAY, root));

		expect(result).toBeNull();
		expect(warned).toEqual([]);
	});

	const BROKEN: { state: string; content: string }[] = [
		{ state: 'is not JSON', content: '{"date": "2030-06-15", "runs": [' },
		{ state: 'lists no run', content: JSON.stringify({ date: DAY, runs: [] }) },
		{
			state: 'records a line that is not a number',
			content: JSON.stringify({
				date: DAY,
				runs: [{ run_id: `${DAY}-1`, n: 1, completed_at: '2030-06-15T18:00:00Z', same_story_floor_applied: '0.94' }]
			})
		}
	];

	for (const one of BROKEN) {
		test(`a run record that ${one.state} answers no line, and the build log names the day`, () => {
			const root = rootHolding(one.content);

			const { result, warned } = warnings(() => readRecordedLine(DAY, root));

			expect(result).toBeNull();
			expect(warned).toEqual([
				expect.stringContaining('[digest] 2030-06-15: run record unreadable, so the merge line is worked out from the fitted rows')
			]);
		});
	}
});
