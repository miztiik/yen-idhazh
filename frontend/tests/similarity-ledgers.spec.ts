import { expect, test } from '@playwright/test';
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import type { PublicationInventory } from '../src/lib/server/publication';
import { fittedLines } from '../src/lib/server/similarity-ledger';
import { mergeLineHoldoutScore } from '../src/lib/server/similarity-holdout';

/**
 * Do the Judgement route's two ledger readers read the day files their writers commit?
 *
 * The fitted merge line and the merge line's holdout score each file one
 * `<YYYY>/<MM>/<DD>.csv` a day, and the site reads only the files the
 * publication inventory names. Each case builds that tree and its inventory
 * under its own temporary folder, in the layout the writers use, and writes out
 * every value it expects (`CLAUDE.md` section 13), so nothing here reads the
 * committed archive. The days in each tree have no gaps, so the cover's count
 * of recorded days and a count of calendar days give the same answer.
 *
 * The last case binds the layout to `config/ledgers.json`, the registry the
 * backend builds each writer's path from: the folders and the suffix written
 * here are the ones it names, so a registry edit that moves either ledger turns
 * this spec red rather than leaving the page to read nothing.
 */

const FITTED = ['content-similarity-judge', 'fitted-thresholds'] as const;
const SCORES = ['content-similarity-judge', 'merge-line-holdout-scores'] as const;
const SUFFIX = '.csv';

const FITTED_COLUMNS = [
	'date', 'run_id', 'previous', 'proposed', 'after_damping', 'applied', 'clamp_kind',
	'clamp_movement', 'held_reason', 'max_down_step', 'max_up_step', 'pairs_in_band',
	'pairs_judged', 'pairs_usable', 'disagreement_rate', 'unclear_rate',
	'negatives_on_record', 'above_line_on_record', 'days_on_record', 'cosine_weight'
];
const SCORE_COLUMNS = [
	'date', 'run_id', 'applied_line', 'labeller', 'merged_and_one_story',
	'merged_and_two_stories', 'apart_and_one_story', 'apart_and_two_stories',
	'pairs_unresolved', 'labelled_two_story_pairs'
];

/** The state-root path of one day's file, in the layout its writer files it. */
function dayPath(ledger: readonly string[], date: string): string {
	return [...ledger, date.slice(0, 4), date.slice(5, 7), `${date.slice(8, 10)}${SUFFIX}`].join('/');
}

/** Write one day's file, every row of it, and hand back its state-root path. */
function writeDay(root: string, ledger: readonly string[], date: string, columns: string[], rows: string[][]): string {
	const path = dayPath(ledger, date);
	const file = join(root, ...path.split('/'));
	mkdirSync(dirname(file), { recursive: true });
	writeFileSync(file, [columns, ...rows].map((cells) => cells.join(',')).join('\n') + '\n', 'utf8');
	return path;
}

/** Name the given state files in the root's inventory, on the contract's own template. */
function writeInventory(root: string, paths: string[]): void {
	const template = JSON.parse(readFileSync(
		join(import.meta.dirname, '..', '..', 'tests', 'fixtures', 'contracts', 'publication-inventory', 'published.json'),
		'utf8'
	)) as PublicationInventory;
	const inventory: PublicationInventory = {
		...template,
		dates: [],
		entries: paths.map((path) => ({ root: 'state' as const, path, bytes: 0, items: 0 })),
		total_bytes: 0,
		total_items: 0
	};
	writeFileSync(join(root, 'publication.json'), `${JSON.stringify(inventory)}\n`, 'utf8');
}

/** A state root of the test's own, removed whatever the case did. */
function withRoot(run: (root: string) => void): void {
	const root = mkdtempSync(join(tmpdir(), 'similarity-ledgers-'));
	try {
		run(root);
	} finally {
		rmSync(root, { recursive: true, force: true });
	}
}

/** Three days of fitted lines, 30 Sep to 2 Oct 2026; 2 Oct holds a run and its re-run. */
function writeFittedDays(root: string): string[] {
	return [
		writeDay(root, FITTED, '2026-09-30', FITTED_COLUMNS, [[
			'2026-09-30', '2026-10-01-37000000001', '0.94', '0.936', '0.938', '0.938', 'step',
			'0.002', 'none', '0.002', '0.001', '61', '58', '50', '0.1', '0.04', '12', '4', '9', '1.0'
		]]),
		writeDay(root, FITTED, '2026-10-01', FITTED_COLUMNS, [[
			'2026-10-01', '2026-10-02-37000000002', '0.938', '', '', '0.938', 'none',
			'0.0', 'sheet_too_small', '0.002', '0.001', '4', '4', '3', '0.25', '0.0', '12', '4', '9', '1.0'
		]]),
		writeDay(root, FITTED, '2026-10-02', FITTED_COLUMNS, [
			[
				'2026-10-02', '2026-10-03-37000000003', '0.938', '0.935', '0.937', '0.937', 'step',
				'0.001', 'none', '0.002', '0.001', '57', '57', '52', '0.08', '0.05', '15', '5', '10', '1.0'
			],
			[
				'2026-10-02', '2026-10-03-37000000004', '0.938', '0.934', '0.936', '0.936', 'guard',
				'0.0005', 'none', '0.002', '0.001', '57', '57', '52', '0.08', '0.05', '16', '5', '10', '0.9'
			]
		])
	];
}

const FITTED_30_SEP = {
	date: '2026-09-30', runId: '2026-10-01-37000000001', previous: 0.94, proposed: 0.936,
	afterDamping: 0.938, applied: 0.938, clampKind: 'step', clampMovement: 0.002, heldReason: 'none',
	maxDownStep: 0.002, maxUpStep: 0.001, disagreementRate: 0.1, unclearRate: 0.04, pairsInBand: 61,
	pairsJudged: 58, pairsUsable: 50, negativesOnRecord: 12, aboveLineOnRecord: 4, daysOnRecord: 9,
	cosineWeight: 1
};
const FITTED_1_OCT = {
	date: '2026-10-01', runId: '2026-10-02-37000000002', previous: 0.938, proposed: null,
	afterDamping: null, applied: 0.938, clampKind: 'none', clampMovement: 0, heldReason: 'sheet_too_small',
	maxDownStep: 0.002, maxUpStep: 0.001, disagreementRate: 0.25, unclearRate: 0, pairsInBand: 4,
	pairsJudged: 4, pairsUsable: 3, negativesOnRecord: 12, aboveLineOnRecord: 4, daysOnRecord: 9,
	cosineWeight: 1
};
const FITTED_2_OCT_RERUN = {
	date: '2026-10-02', runId: '2026-10-03-37000000004', previous: 0.938, proposed: 0.934,
	afterDamping: 0.936, applied: 0.936, clampKind: 'guard', clampMovement: 0.0005, heldReason: 'none',
	maxDownStep: 0.002, maxUpStep: 0.001, disagreementRate: 0.08, unclearRate: 0.05, pairsInBand: 57,
	pairsJudged: 57, pairsUsable: 52, negativesOnRecord: 16, aboveLineOnRecord: 5, daysOnRecord: 10,
	cosineWeight: 0.9
};

/** Two days of holdout scores, 20 and 21 Sep 2026, one scoring run each. */
function writeScoreDays(root: string): string[] {
	return [
		writeDay(root, SCORES, '2026-09-20', SCORE_COLUMNS, [[
			'2026-09-20', '2026-09-20-36000000001', '0.95', 'labeller-one', '70', '2', '110', '4', '1', '6'
		]]),
		writeDay(root, SCORES, '2026-09-21', SCORE_COLUMNS, [[
			'2026-09-21', '2026-09-21-36000000002', '0.94', 'labeller-one', '72', '1', '113', '5', '0', '6'
		]])
	];
}

const SCORE_21_SEP = {
	date: '2026-09-21', runId: '2026-09-21-36000000002', appliedLine: 0.94, labeller: 'labeller-one',
	mergedAndOneStory: 72, mergedAndTwoStories: 1, apartAndOneStory: 113, apartAndTwoStories: 5,
	pairsUnresolved: 0, labelledTwoStoryPairs: 6
};

test('THE ORACLE: the fitted lines are read from their YYYY/MM/DD.csv files, and a day outside the cover is not', () => {
	withRoot((root) => {
		writeInventory(root, writeFittedDays(root));

		// A cover of two recorded days reads 1 and 2 Oct, the newest run of each.
		expect(fittedLines(2, root)).toEqual([FITTED_1_OCT, FITTED_2_OCT_RERUN]);
		// The day the cover left out is there to be read when the cover reaches it.
		expect(fittedLines(-1, root)).toEqual([FITTED_30_SEP, FITTED_1_OCT, FITTED_2_OCT_RERUN]);
	});
});

test('THE ORACLE: the newest holdout score is read from its YYYY/MM/DD.csv file', () => {
	withRoot((root) => {
		writeInventory(root, writeScoreDays(root));

		expect(mergeLineHoldoutScore(2, root)).toEqual(SCORE_21_SEP);
		expect(mergeLineHoldoutScore(1, root)).toEqual(SCORE_21_SEP);
	});
});

test('a day the inventory names inside the cover and the disk lacks stops the read and names the file', () => {
	withRoot((root) => {
		const named = writeFittedDays(root);
		rmSync(join(root, ...named[2].split('/')));
		writeInventory(root, named);

		expect(() => fittedLines(2, root)).toThrow(
			'Publication inventory names missing ledger file content-similarity-judge/fitted-thresholds/2026/10/02.csv.'
		);
	});
});

test('THE ORACLE: a holdout day outside the cover is not read, so the disk may lack it', () => {
	withRoot((root) => {
		const named = writeScoreDays(root);
		rmSync(join(root, ...named[0].split('/')));
		writeInventory(root, named);

		expect(mergeLineHoldoutScore(1, root)).toEqual(SCORE_21_SEP);
		// A cover that reaches 20 Sep stops on the same missing file, so the read
		// above answered because it never reached that day.
		expect(() => mergeLineHoldoutScore(2, root)).toThrow(
			'Publication inventory names missing ledger file content-similarity-judge/merge-line-holdout-scores/2026/09/20.csv.'
		);
	});
});

test('the registry files both judge ledgers one YYYY/MM/DD.csv a day, in the folders the readers open', () => {
	const registry = JSON.parse(
		readFileSync(join(import.meta.dirname, '..', '..', 'config', 'ledgers.json'), 'utf8')
	) as { families: { name: string; ledgers: { name: string }[] }[] };
	const judge = registry.families.find((family) => family.name === 'content-similarity-judge');
	const entry = (name: string) => judge?.ledgers.find((ledger) => ledger.name === name);

	expect(entry('fitted-thresholds')).toEqual({
		name: 'fitted-thresholds', grain: 'day', prefix: [...FITTED], stem: null, suffix: SUFFIX
	});
	expect(entry('merge-line-holdout-scores')).toEqual({
		name: 'merge-line-holdout-scores', grain: 'day', prefix: [...SCORES], stem: null, suffix: SUFFIX
	});
});
