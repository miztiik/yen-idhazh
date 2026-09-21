/** The hand-marked holdout pairs, scored at build time from the published days.
 *
 * `state/content-similarity-judge/holdout-pairs.csv` names two addresses and two dates
 * a row. The published day payload carries the vectors and the key points those
 * addresses were scored on, so the score is recomputed here, once, and the page
 * ships the answer. Nothing is scored in a browser.
 *
 * **What it reads, and what bounds it.** One hand-typed file, plus one day
 * payload for each distinct date that file names. The bound is the length of
 * the holdout file rather than the archive: a published day nothing marks is
 * never opened, and another year of archive adds no read at all. The days it
 * does open are outside the window preset the rest of this route works to,
 * which is why the read has an entry of its own in
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
import {
	cosineInt8,
	keyPointOverlap,
	pairScore,
	reduceWords,
	type HoldoutMark,
	type HoldoutSkip,
	type ScoreWeights
} from '../console/holdout';
import { DIGEST_ROOT, readCsv, STATE_ROOT } from './payload';

/** Every mark the day tree could answer for, and every one it could not. */
export interface HoldoutReading {
	marks: HoldoutMark[];
	skipped: HoldoutSkip[];
	/** How many rows the file holds, scored or not. */
	marked: number;
	/** How many distinct published days were opened to answer it. */
	daysOpened: number;
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

/** One published item, reduced to the three things a score needs. */
interface ScoredItem {
	title: string;
	words: string[];
	vector: Int8Array | null;
}

/** The items of one published day that the holdout file actually names.
 *
 * The day payload is the biggest file this build reads and the vector block is
 * most of it, so the wanted keys are worked out before the file is opened and
 * everything else is dropped on the way past. Null where the day is no longer
 * published, which is a designed state: retention deletes a day the file still
 * names.
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
		items?: { item_id?: string; source_url?: string; title?: string; key_points?: string[] }[];
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
			words: reduceWords((item.key_points ?? []).join(' ')),
			vector: raw === undefined ? null : new Int8Array(Buffer.from(raw, 'base64'))
		});
	}
	return found;
}

/** Every hand-marked pair, scored under the weights in force.
 *
 * A row the day tree cannot answer for is counted with its reason rather than
 * dropped. A blank dot would say the margin is fine; a counted skip says the
 * mark could not be checked.
 */
export function holdoutReading(
	weights: ScoreWeights,
	stateRoot: string = STATE_ROOT,
	digestRoot: string = DIGEST_ROOT
): HoldoutReading {
    const table = readCsv(join(stateRoot, 'content-similarity-judge', 'holdout-pairs.csv'));
	if (table.rows.length === 0) {
		return { marks: [], skipped: [], marked: 0, daysOpened: 0 };
	}

	// The cover is worked out before the first day is opened (Guardrail #12):
	// the dates and the addresses this file names, and no others.
	const wanted = new Set<string>();
	const dates = new Set<string>();
	for (const row of table.rows) {
		wanted.add(urlKey(row.left_url ?? ''));
		wanted.add(urlKey(row.right_url ?? ''));
		if (row.left_date) dates.add(row.left_date);
		if (row.right_date) dates.add(row.right_date);
	}
	const days = new Map<string, Map<string, ScoredItem> | null>();
	for (const date of dates) days.set(date, dayItems(date, digestRoot, wanted));

	const marks: HoldoutMark[] = [];
	const skipped: HoldoutSkip[] = [];
	for (const row of table.rows) {
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
			// The contract writes a JSON bool, so anything that is not the word
			// true is a mark that the two are different stories - which is the
			// load-bearing direction and the one to reach by default.
			sameStory: (row.same_story ?? '').trim().toLowerCase() === 'true',
			markedOn: row.marked_on ?? '',
			note: row.note ?? '',
			score: pairScore(
				cosineInt8(left.vector, right.vector),
				keyPointOverlap(left.words, right.words),
				weights
			)
		});
	}
	return { marks, skipped, marked: table.rows.length, daysOpened: dates.size };
}
