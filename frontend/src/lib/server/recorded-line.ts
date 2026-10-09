/** Which merge line did a published day's last build record?
 *
 * Every build of a day appends a record to that day's `run.json`, and each
 * record names the line that build grouped the day's stories at,
 * `same_story_floor_applied` on `RunRecord` in
 * `backend/idhazh/contracts/run_manifest.py`. A build groups every story of the
 * day again, so the day as published stands at the line of the build that
 * finished last: the record with the newest `completed_at`. Of two records that
 * finished at the same second, the later one in the list wins, and a record
 * with no time counts as the oldest.
 *
 * Read while the site is built and never fetched: the site stages no
 * `run.json`. The input is one file, the given date's, so the read costs the
 * same on the thousandth published day as on the third (`CLAUDE.md` Guardrail
 * #12).
 *
 * Null where the date has no record, where its last build wrote no line (every
 * build before 18 Sep 2026), or where the record cannot be read; the last of
 * these warns in the build log, naming the date. The caller then works the line
 * out with the rule a build follows, `findBuiltLine` in
 * `$lib/console/applied-line`.
 *
 * Imports nothing that needs a Vite alias: the logic suite loads it in plain Node.
 */

import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
// Relative, not `$lib`, for the reason in the module docstring.
import { DIGEST_ROOT } from './payload';

/** The two keys of a run record this reader reads, as the pipeline writes them.
 * A contract test holds each to `RunRecord`, because a key renamed there would
 * otherwise turn every page back to the worked-out line with no error. */
export const RECORD_KEYS = {
	line: 'same_story_floor_applied',
	finishedAt: 'completed_at'
} as const;

/** One record of `runs`, as the file holds it. */
type RunCells = Record<string, unknown>;

function isRunCells(value: unknown): value is RunCells {
	return typeof value === 'object' && value !== null && !Array.isArray(value);
}

/** When a build finished, as text that sorts in time order: the record writes
 * fixed-width UTC, so comparing the text compares the times. Empty, and so the
 * oldest, where the build wrote no time. */
function finishedAt(run: RunCells): string {
	const at = run[RECORD_KEYS.finishedAt];
	return typeof at === 'string' ? at : '';
}

/** The line the given day's last build grouped its stories at, or null. */
export function readRecordedLine(date: string, root: string = DIGEST_ROOT): number | null {
	const [year, month, day] = date.split('-');
	if (!year || !month || !day) return null;
	const path = join(root, year, month, day, 'run.json');
	if (!existsSync(path)) return null;
	try {
		const parsed: unknown = JSON.parse(readFileSync(path, 'utf8'));
		const runs: unknown = isRunCells(parsed) ? parsed.runs : undefined;
		if (!Array.isArray(runs) || runs.length === 0 || !runs.every(isRunCells)) {
			throw new TypeError('it holds no list of run records');
		}
		const records: RunCells[] = runs;
		// `>=`, so of two builds that finished at the same second the later one wins.
		const last = records.reduce((newest, run) =>
			finishedAt(run) >= finishedAt(newest) ? run : newest
		);
		const line = last[RECORD_KEYS.line];
		if (line === undefined || line === null) return null;
		if (typeof line !== 'number' || !(line >= 0 && line <= 1)) {
			throw new TypeError(`its last build recorded ${JSON.stringify(line)} as the line`);
		}
		return line;
	} catch (cause) {
		// Degrade, do not fail (`CLAUDE.md` section 1a): the panels then name the
		// line the rule works out, and the build log says why.
		console.warn(
			`[digest] ${date}: run record unreadable, so the merge line is worked out from the fitted rows - ${String(cause)}`
		);
		return null;
	}
}
