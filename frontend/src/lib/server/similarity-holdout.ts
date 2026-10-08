/** The hand-marked holdout pairs, scored at build time from the published days.
 *
 * Each mark names two addresses and two dates. A person saves the marks through
 * the ledger door with `backend/utilities/sample_sheet.py --harvest`, under
 * `state/raw/content-similarity-judge/holdout-pairs/`, and the gardener packs
 * them under `state/compact/content-similarity-judge/holdout-pairs/`. The
 * published day payload carries the vectors and the key points those addresses
 * were scored on, so the score is recomputed here, once, and the page ships the
 * answer. Nothing is scored in a browser.
 *
 * **The four cells come off a committed row and are never counted here.**
 * `python -m idhazh score-merge-line-holdout` writes how the line stood against
 * the marks, so a reading survives the page that drew it and two of them can be
 * held against each other weeks apart. What this file still derives is the
 * per-pair score, which the panel draws as dots and no row carries.
 *
 * **What it reads, and what bounds it.** The packed marks inside the reach
 * `similarity.holdout_reach_days` sets, plus one day payload for each distinct
 * date those marks name, plus the committed readings a window of days reaches.
 * The bound is the reach and the marks inside it rather than the archive: a
 * published day nothing marks is never opened, and another year of archive adds
 * no read at all. The days it does open are outside the window preset the rest
 * of this route works to, which is why the read has an entry of its own in
 * `docs/concepts/growing-reads.md`.
 *
 * Nothing here is published. It sits under `$lib/server/` so SvelteKit refuses
 * to bundle it for a browser, the same place and for the same reason as
 * `similarity-ledger.ts`.
 */

import { createHash } from 'node:crypto';
import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
// Relative, not `$lib`, for the reason in `similarity-ledger.ts`: the browser
// suite loads this module in plain Node, where no Vite alias resolves.
import { windowOfDays, type TimeWindow } from '../charts/viewport';
import {
	cosineInt8,
	pairScore,
	type HoldoutMark,
	type HoldoutSkip,
	type ScoreWeights
} from '../console/holdout';
import { FILED_DAY_COLUMN } from '../data/slice-query';
import { sliceFromDisk } from './ledger-disk';
import { datedFirst, windowRows } from './ledger-rows';
import { DIGEST_ROOT, STATE_ROOT } from './payload';

/** Every mark the day tree could answer for, and every one it could not. */
export interface HoldoutReading {
	marks: HoldoutMark[];
	skipped: HoldoutSkip[];
	/** How many marks were read, scored or not. */
	marked: number;
	/** How many distinct published days were opened to answer it. */
	daysOpened: number;
}

/** One committed reading of the line against the marks - the four cells and their line.
 *
 * `state/compact/content-similarity-judge/merge-line-holdout-scores/` holds
 * one row a scoring run, written by `python -m idhazh score-merge-line-holdout`
 * through the ledger door and packed by the gardener.
 * The page reads it rather than counting the same cells again: two answers to
 * one question is what the committed row exists to stop.
 */
export interface MergeLineHoldoutScore {
	date: string;
	runId: string;
	appliedLine: number;
	labeller: string;
	mergedAndOneStory: number;
	mergedAndTwoStories: number;
	apartAndOneStory: number;
	apartAndTwoStories: number;
	pairsUnresolved: number;
	labelledTwoStoryPairs: number;
}

/** The columns of `MergeLineHoldoutScore` the panel reads, in the contract's own order.
 *
 * The door answers only the columns it is asked for. A backend contract test
 * fails when the contract renames or drops one of these, or when this order is
 * not the contract's.
 */
export const HOLDOUT_SCORE_COLUMNS = [
	'date',
	'run_id',
	'applied_line',
	'labeller',
	'merged_and_one_story',
	'merged_and_two_stories',
	'apart_and_one_story',
	'apart_and_two_stories',
	'pairs_unresolved',
	'labelled_two_story_pairs'
] as const;

/** The columns of `SimilarityHoldoutPair` the panel reads, in the contract's own order.
 *
 * Every column but `version`. A backend contract test fails when the contract
 * renames or drops one of these, or when this order is not the contract's.
 */
export const HOLDOUT_PAIR_COLUMNS = [
	'left_url',
	'right_url',
	'left_date',
	'right_date',
	'left_title',
	'right_title',
	'same_story',
	'marked_on',
	'note'
] as const;

/** The UTC days the hand marks are read over: `reachDays` days before `day`, and `day`.
 *
 * Both ends are named, as `day_partition.days_in_window` names them for the
 * backend's reader, so the page and the scoring verb count the same marks.
 */
export function markReach(day: string, reachDays: number): TimeWindow {
	return windowOfDays(day, reachDays + 1, 'right');
}

/** One row of the hand marks as text cells, keyed by column name. */
type MarkRow = Record<string, string>;

/** Every packed mark inside `reach`, once a pair, each with the mark it was given last.
 *
 * The door packs a day by settling its rows under the ledger's key, the two
 * addresses, and its preference: the newer mark wins. A pair marked again on a
 * later day sits in two days, so the same rule is applied once more here, across
 * the days, with the rows asked for oldest filed day first - the order the
 * backend's `similarity/holdout.marked_pairs` reads them in, so the two readers
 * keep the same mark. A day reaches this page once the gardener has packed it.
 *
 * No packed file is an ordinary state - nobody has harvested a mark yet, or the
 * gardener has not packed the first one - and it reads as no mark.
 */
export async function markedPairs(reach: TimeWindow, root: string = STATE_ROOT): Promise<MarkRow[]> {
	const asked = [FILED_DAY_COLUMN, ...HOLDOUT_PAIR_COLUMNS];
	const table = await windowRows(root, 'holdout-pairs', reach, HOLDOUT_PAIR_COLUMNS, (start, end) =>
		sliceFromDisk(root, 'holdout-pairs', { columns: asked, from: start, to: end })
	);
	const kept = new Map<string, MarkRow>();
	for (const row of table.rows) {
		const pair = JSON.stringify([row.left_url ?? '', row.right_url ?? '']);
		const held = kept.get(pair);
		if (held === undefined || (row.marked_on ?? '') >= (held.marked_on ?? '')) kept.set(pair, row);
	}
	return [...kept.values()];
}

/** The identity a holdout row and a published item are joined on.
 *
 * Recomputed from the address on both sides rather than read off either, which
 * is what `SimilarityHoldoutPair` says in its own docstring: a person types the
 * file, so there is no cell a typist can get wrong and none that can go stale.
 */
function urlKey(canonicalUrl: string): string {
	return createHash('sha256').update(canonicalUrl, 'utf8').digest('hex');
}

/** One published item, reduced to the two things a score needs. */
interface ScoredItem {
	title: string;
	vector: Int8Array | null;
}

/** The items of one published day that the marks actually name.
 *
 * The day payload is the biggest file this build reads and the vector block is
 * most of it, so the wanted keys are worked out before the file is opened and
 * everything else is dropped on the way past. Null where the day is no longer
 * published, which is a designed state: retention deletes a day the marks still
 * name.
 */
function dayItems(
	date: string,
	digestRoot: string,
	wanted: ReadonlySet<string>
): Map<string, ScoredItem> | null {
	const [year, month, day] = date.split('-');
	if (!year || !month || !day) return null;
	const path = join(digestRoot, year, month, day, 'digest.json');
	if (!existsSync(path)) return null;
	let parsed: {
		items?: { item_id?: string; source_url?: string; title?: string }[];
		embeddings?: { vectors?: Record<string, string> } | null;
	};
	try {
		parsed = JSON.parse(readFileSync(path, 'utf8'));
	} catch {
		// Degrade, do not fail (`CLAUDE.md` section 1a). One unreadable day costs
		// the marks that name it, and the panel counts them as skipped rather than
		// taking the console route down.
		return null;
	}
	const vectors = parsed.embeddings?.vectors ?? {};
	const found = new Map<string, ScoredItem>();
	for (const item of parsed.items ?? []) {
		const key = urlKey(item.source_url ?? '');
		if (!wanted.has(key)) continue;
		const raw = vectors[item.item_id ?? ''];
		found.set(key, {
			title: item.title ?? '',
			vector: raw === undefined ? null : new Int8Array(Buffer.from(raw, 'base64'))
		});
	}
	return found;
}

/** Every hand-marked pair inside `reach`, scored under the weights in force.
 *
 * A mark the day tree cannot answer for is counted with its reason rather than
 * dropped. A blank dot would say the margin is fine; a counted skip says the
 * mark could not be checked.
 */
export async function holdoutReading(
	weights: ScoreWeights,
	reach: TimeWindow,
	stateRoot: string = STATE_ROOT,
	digestRoot: string = DIGEST_ROOT
): Promise<HoldoutReading> {
	const rows = await markedPairs(reach, stateRoot);
	if (rows.length === 0) {
		return { marks: [], skipped: [], marked: 0, daysOpened: 0 };
	}

	// The cover is worked out before the first day is opened (Guardrail #12):
	// the dates and the addresses these marks name, and no others.
	const wanted = new Set<string>();
	const dates = new Set<string>();
	for (const row of rows) {
		wanted.add(urlKey(row.left_url ?? ''));
		wanted.add(urlKey(row.right_url ?? ''));
		if (row.left_date) dates.add(row.left_date);
		if (row.right_date) dates.add(row.right_date);
	}
	const days = new Map<string, Map<string, ScoredItem> | null>();
	for (const date of dates) days.set(date, dayItems(date, digestRoot, wanted));

	const marks: HoldoutMark[] = [];
	const skipped: HoldoutSkip[] = [];
	for (const row of rows) {
		const leftTitle = row.left_title ?? '';
		const rightTitle = row.right_title ?? '';
		const leftDay = days.get(row.left_date ?? '') ?? null;
		const rightDay = days.get(row.right_date ?? '') ?? null;
		if (leftDay === null || rightDay === null) {
			skipped.push({ leftTitle, rightTitle, reason: 'the day it names is no longer published' });
			continue;
		}
		const left = leftDay.get(urlKey(row.left_url ?? ''));
		const right = rightDay.get(urlKey(row.right_url ?? ''));
		if (left === undefined || right === undefined) {
			skipped.push({ leftTitle, rightTitle, reason: 'the article is not on the day it names' });
			continue;
		}
		if (left.vector === null || right.vector === null) {
			skipped.push({ leftTitle, rightTitle, reason: 'the article carries no vector' });
			continue;
		}
		marks.push({
			leftTitle,
			rightTitle,
			// The door hands the mark back as Python spells a flag, `True` or
			// `False`, so anything that is not the word true is a mark that the two
			// are different stories - which is the load-bearing direction and the
			// one to reach by default.
			sameStory: (row.same_story ?? '').trim().toLowerCase() === 'true',
			markedOn: row.marked_on ?? '',
			note: row.note ?? '',
			score: pairScore(cosineInt8(left.vector, right.vector), weights)
		});
	}
	return { marks, skipped, marked: rows.length, daysOpened: dates.size };
}

/** The newest committed reading of the line against the marks in `window`, or null for none.
 *
 * **Null is an ordinary state and the panel says so rather than erroring.** A
 * person types the verb that writes these rows; nothing in the daily pipeline
 * calls it, so a tree where nobody has run it yet has no row at all - and a
 * window that starts after the newest row has none either. A row reaches the
 * page once the gardener has packed its day.
 *
 * Bounded by the same window every other read on this route takes: the packed
 * days inside it and no more (Guardrail #12).
 */
export async function mergeLineHoldoutScore(
	window: TimeWindow,
	root: string = STATE_ROOT
): Promise<MergeLineHoldoutScore | null> {
	const table = await windowRows(root, 'merge-line-holdout-scores', window, HOLDOUT_SCORE_COLUMNS, (start, end) =>
		sliceFromDisk(root, 'merge-line-holdout-scores', {
			columns: [...datedFirst(HOLDOUT_SCORE_COLUMNS)],
			from: start,
			to: end
		})
	);
	let newest: MergeLineHoldoutScore | null = null;
	for (const row of table.rows) {
		const date = (row.date ?? '').trim();
		const runId = (row.run_id ?? '').trim();
		const line = Number(row.applied_line);
		if (date === '' || runId === '' || !Number.isFinite(line)) continue;
		// Date first, then run: two runs of one date both scored the line, and the
		// later one read the later tree.
		if (newest !== null && `${newest.date}${newest.runId}` >= `${date}${runId}`) continue;
		newest = {
			date,
			runId,
			appliedLine: line,
			labeller: (row.labeller ?? '').trim(),
			mergedAndOneStory: Number(row.merged_and_one_story ?? 0),
			mergedAndTwoStories: Number(row.merged_and_two_stories ?? 0),
			apartAndOneStory: Number(row.apart_and_one_story ?? 0),
			apartAndTwoStories: Number(row.apart_and_two_stories ?? 0),
			pairsUnresolved: Number(row.pairs_unresolved ?? 0),
			labelledTwoStoryPairs: Number(row.labelled_two_story_pairs ?? 0)
		};
	}
	return newest;
}
