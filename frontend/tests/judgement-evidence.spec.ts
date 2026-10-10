/** Do Judgement reads and rendered panels keep unknown, empty and partial evidence distinct? */
import { expect, test } from '@playwright/test';
import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { judgementEvidence } from '../src/lib/console/judgement-evidence';
import type { RecordRead } from '../src/lib/console/recording';
import { fittedLines } from '../src/lib/server/content-similarity-judge';
import { markedPairs, holdoutReading, mergeLineHoldoutScore } from '../src/lib/server/content-similarity-holdout';
import { buildLedger, buildRows } from './support/ledger-lifecycle';
import { serverPanels } from './support/console-window/server-panels';
import { judgeDay, propsOf } from './support/console-window/judgement-fixtures';

const WINDOW = { start: '2030-06-09', end: '2030-06-15' };
const LOADED = { start: '2030-03-18', end: '2030-06-15' };

function words(html: string): string {
	return html.replace(/<!--[\s\S]*?-->/g, '').replace(/<[^>]*>/g, ' ')
		.replace(/&(?:#39|apos);/g, "'").replace(/&quot;/g, '"').replace(/&amp;/g, '&')
		.replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/\s+/g, ' ').trim();
}

test('read notes name unavailable, lost and set-aside input without inventing a last run', () => {
	expect(judgementEvidence({ state: 'not-packed' }, WINDOW, LOADED, 'judge')).toEqual([
		'The judge record has not been packed yet. Its readings are unavailable.'
	]);
	expect(judgementEvidence({ state: 'unreadable', at: '<script>raw-fault</script>', fault: null }, WINDOW, LOADED, 'judge')).toEqual([
		'The judge record could not be read. Its readings are unavailable.'
	]);
	const read: RecordRead = {
		state: 'read', first: '2030-06-10', through: '2030-06-14',
		lastRows: { period: 'monthly', covers: '2030-05' },
		lostDays: ['2030-05-20', '2030-06-12'], setAside: { '2030-05': 2 }
	};
	const notes = judgementEvidence(read, WINDOW, LOADED, 'judge');
	expect(notes.slice(0, 4)).toEqual([
		'The judge record starts on 10 Jun 2030.',
		'The judge record is packed through 14 Jun 2030. Later days have no packed reading here.',
		'The last packed period with rows in the judge record is 1 May 2030 to 31 May 2030. This is a period, not the date of the last run.',
		'There is no judge record for 12 Jun 2030, so its readings for that day are unavailable. The record for that day was lost and could not be recovered; it was not a quiet day.'
	]);
	expect(notes.at(-1)).toBe('The set-aside count covers the loaded input from 18 Mar 2030 to 15 Jun 2030, not only the selected window.');
	expect(notes[4]).toBe('2 judge record files were set aside unread when this data was packed, so the loaded readings may be missing their rows. They wait in state/raw/content-similarity-judge/fitted-thresholds/set-aside/ for a person to read.');
	expect(notes.join(' ')).not.toContain('20 May');
	expect(notes.join(' ')).not.toContain('raw-fault');
	expect(notes.join(' ')).toContain('2');
	expect(notes.join(' ')).toContain('set-aside');
});

test('all three packed readers preserve failure and successful empty reads', async ({}, info) => {
	const absent = info.outputPath('absent');
	expect(await fittedLines(WINDOW, absent)).toEqual({ rows: [], rates: [], rejected: [], read: { state: 'not-packed' } });
	expect(await markedPairs(WINDOW, absent)).toEqual({ rows: [], read: { state: 'not-packed' } });
	expect(await mergeLineHoldoutScore(WINDOW, absent)).toEqual({ score: null, read: { state: 'not-packed' } });
	for (const ledger of ['fitted-thresholds', 'holdout-pairs', 'merge-line-holdout-scores'] as const) {
		const root = info.outputPath(ledger);
		await buildLedger(root, { ledger, pinned: WINDOW.end, days: [{ ago: 0, state: 'empty' }] });
		const reading = ledger === 'fitted-thresholds' ? await fittedLines(WINDOW, root)
			: ledger === 'holdout-pairs' ? await markedPairs(WINDOW, root)
			: await mergeLineHoldoutScore(WINDOW, root);
		expect(reading.read.state).toBe('read');
		if ('rows' in reading) expect(reading.rows).toEqual([]);
		else expect(reading.score).toBeNull();
		const folder = join(root, 'compact', 'content-similarity-judge', ledger, 'index');
		mkdirSync(folder, { recursive: true });
		writeFileSync(join(folder, 'daily.json'), 'not json');
		const broken = ledger === 'fitted-thresholds' ? await fittedLines(WINDOW, root)
			: ledger === 'holdout-pairs' ? await markedPairs(WINDOW, root)
			: await mergeLineHoldoutScore(WINDOW, root);
		expect(broken.read.state).toBe('unreadable');
	}
});

test('real packed nulls survive with partial read evidence; required blank counts are not zero', async ({}, info) => {
	const root = info.outputPath('judge');
	const columns = {
		run_id: '2030-06-14-1', previous: 0.95, proposed: null, after_damping: null,
		applied: 0.95, clamp_kind: 'none', clamp_movement: 0, held_reason: 'sheet_too_small',
		max_down_step: 0.01, max_up_step: 0.01, pairs_in_band: null,
		pairs_judged: null, pairs_usable: 8, disagreement_rate: 0, unclear_rate: 0.25,
		negatives_on_record: 0, above_line_on_record: 0, days_on_record: 0, cosine_weight: null
	};
	await buildLedger(root, {
		ledger: 'fitted-thresholds', pinned: WINDOW.end,
		days: [{ ago: 1, rows: 1, setAside: 2 }, { ago: 2, state: 'lost' }], columns
	});
	const reading = await fittedLines(WINDOW, root);
	expect(reading.rows).toHaveLength(1);
	expect(reading.rows[0]).toMatchObject({
		pairsInBand: null, pairsJudged: null, pairsUsable: 8,
		negativesOnRecord: 0, daysOnRecord: 0, aboveLineOnRecord: 0
	});
	expect(reading.read).toMatchObject({ state: 'read', lostDays: ['2030-06-13'], setAside: { '2030-06-14': 2 } });
	const malformed = info.outputPath('required-blank');
	await buildLedger(malformed, { ledger: 'fitted-thresholds', pinned: WINDOW.end, days: [{ ago: 0, rows: 1 }], columns: { ...columns, negatives_on_record: null } });
	const partial = await fittedLines(WINDOW, malformed);
	expect(partial.rows).toEqual([]);
	expect(partial.rates).toHaveLength(1);
	expect(partial.rates[0]).toMatchObject({ pairsJudged: null, pairsUsable: 8, unclearRate: 0.25 });
	expect(partial.rejected).toEqual([{ date: WINDOW.end, rates: false }]);
});

test('an unavailable gate count cannot discard a valid bad judge reading', async ({}, info) => {
	const root = info.outputPath('independent-readings');
	const common = {
		previous: 0.95, proposed: 0.95, after_damping: 0.95, applied: 0.95,
		clamp_kind: 'none', clamp_movement: 0, max_down_step: 0.01, max_up_step: 0.01,
		pairs_in_band: 10, pairs_judged: 10, pairs_usable: 10, unclear_rate: 0,
		above_line_on_record: 5, days_on_record: 1, cosine_weight: 1
	};
	await buildRows(root, 'fitted-thresholds', [
		{ covers: '2030-06-14', rows: [{ ...common, date: '2030-06-14', run_id: '2030-06-14-1', disagreement_rate: 0, negatives_on_record: 5, held_reason: 'none' }] },
		{ covers: '2030-06-15', rows: [{ ...common, date: '2030-06-15', run_id: '2030-06-15-1', disagreement_rate: 0.5, negatives_on_record: null, held_reason: 'judge_unstable' }] }
	]);
	const reading = await fittedLines(WINDOW, root);
	expect(reading.rows.map((row) => row.date)).toEqual(['2030-06-14']);
	expect(reading.rates.map((row) => row.date)).toEqual(['2030-06-14', '2030-06-15']);
	expect(reading.rejected).toEqual([{ date: '2030-06-15', rates: false }]);
	const { drawn } = await serverPanels(info.outputPath('panels'), [['src/routes/console/judgement/JudgeAgreement.svelte', 'JudgeAgreement']]);
	const html = drawn.JudgeAgreement({
		...propsOf({ surface: 'judge-agreement', preset: 7, days: [], state: '', words: '' }),
		days: reading.rates
	});
	expect(words(html)).toContain('25% of 20 pairs');
	expect(words(html)).not.toContain('Both rates are inside the marks.');
	expect((html.match(/<circle\b/g) ?? []).length).toBe(4);
	const incomplete = drawn.JudgeAgreement({
		...propsOf({ surface: 'judge-agreement', preset: 7, days: [], state: '', words: '' }),
		days: reading.rates.slice(0, 1),
		complete: false
	});
	expect(words(incomplete)).toContain('The count of pairs read twice is unavailable for this window.');
	expect(words(incomplete)).not.toContain('Both rates are inside the marks.');
});

test('unscorable hand marks keep their total, skipped reason and the same mark read', async ({}, info) => {
	const root = info.outputPath('marks');
	await buildRows(root, 'holdout-pairs', [{
		covers: '2030-06-14',
		rows: [{
			left_url: 'https://left.test/a', right_url: 'https://right.test/a',
			left_date: '2030-06-01', right_date: '2030-06-01',
			left_title: 'Left', right_title: 'Right', same_story: false,
			marked_on: '2030-06-14', note: 'Recorded by a person'
		}]
	}]);
	const marked = await markedPairs(WINDOW, root);
	const scored = await holdoutReading({ cosineWeight: 1, fittedOn: null }, WINDOW, root, info.outputPath('no-digest'));
	expect(scored.read).toEqual(marked.read);
	expect(scored.marked).toBe(1);
	expect(scored.marks).toEqual([]);
	expect(scored.skipped).toEqual([{ leftTitle: 'Left', rightTitle: 'Right', reason: 'the day it names is no longer published' }]);
});

test('each nullable denominator suppresses only its own dot and never contributes zero to the window', async ({}, info) => {
	const { drawn } = await serverPanels(info.outputPath('panels'), [['src/routes/console/judgement/JudgeAgreement.svelte', 'JudgeAgreement'], ['src/routes/console/judgement/RecordGates.svelte', 'RecordGates'], ['src/routes/console/judgement/HoldoutMargin.svelte', 'HoldoutMargin']]);
	for (const [judged, usable, dots, expected] of [
		[null, 8, 1, 'Could not tell: 25% of the 8 that agreed.'],
		[8, null, 1, 'disagreed with the second reading: 0% of 8 pairs.'],
		[0, null, 0, 'the count of pairs whose readings agreed is unavailable'],
		[null, null, 0, 'the count of pairs read twice is unavailable'],
		[8, 4, 1, '1 of the 4 that agreed']
	] as const) {
		const day = judgeDay(WINDOW.end, { pairsJudged: judged, pairsUsable: usable, unclearRate: 0.25 });
		const html = drawn.JudgeAgreement(propsOf({ surface: 'judge-agreement', preset: 7, days: [day], state: '', words: '' }));
		expect((html.match(/<circle\b/g) ?? []).length).toBe(dots);
		expect(words(html)).toContain(expected);
		expect(html).not.toContain('NaN');
	}
	const partial = drawn.JudgeAgreement(propsOf({
		surface: 'judge-agreement', preset: 7, state: '', words: '',
		days: [
			judgeDay('2030-06-14', { pairsJudged: null, pairsUsable: 8, unclearRate: 0.25 }),
			judgeDay(WINDOW.end, { pairsJudged: 10, pairsUsable: 10, disagreementRate: 0.1, unclearRate: 0.1 })
		]
	}));
	expect(words(partial)).toContain('The count of pairs read twice is unavailable for this window.');
	expect(words(partial)).toContain('Could not tell: 17% of the 18 that agreed.');
	expect((partial.match(/<circle\b/g) ?? []).length).toBe(3);
	const zero = judgeDay(WINDOW.end, { pairsJudged: 8, pairsUsable: 8, disagreementRate: 0, unclearRate: 0 });
	const zeroHtml = drawn.JudgeAgreement(propsOf({ surface: 'judge-agreement', preset: 7, days: [zero], state: '', words: '' }));
	expect((zeroHtml.match(/<circle\b/g) ?? []).length).toBe(2);
	expect(words(zeroHtml)).toContain('0% of 8 pairs');
	const gates = drawn.RecordGates(propsOf({ surface: 'record-gates', preset: 7, days: [judgeDay(WINDOW.end)], state: '', words: '' }));
	expect((gates.match(/data-target-cell="track"/g) ?? []).length).toBe(3);
	expect((gates.match(/data-target-cell="value"[^>]*>0</g) ?? []).length).toBe(3);
	for (const days of [null, []]) {
		const html = drawn.RecordGates({
			...propsOf({ surface: 'record-gates', preset: 7, days: [], state: '', words: '' }), days
		});
		expect(html).not.toContain('data-target-cell="track"');
		expect(words(html)).not.toContain('Nothing was judged');
		if (days === null) expect(words(html)).toContain("The record's gate counts are unavailable for these 7 days.");
	}
	const escaped = drawn.RecordGates({
		...propsOf({ surface: 'record-gates', preset: 7, days: [], state: '', words: '' }),
		evidence: ['<script>untrusted diagnostic</script>']
	});
	expect(escaped).toContain('&lt;script>untrusted diagnostic&lt;/script>');
	expect(escaped).not.toContain('<script>untrusted diagnostic');
	const separateScore = drawn.HoldoutMargin({
		marks: null, agreedScores: null, skipped: [{ leftTitle: 'Left', rightTitle: 'Right', reason: 'the article carries no vector' }],
		marked: 1, applied: 0.94, maxDownStep: 0.01, fitted: false,
		weights: { cosineWeight: 1, fittedOn: null },
		scored: {
			date: '2030-06-14', appliedLine: 0.94, labeller: 'a person',
			mergedAndOneStory: 2, mergedAndTwoStories: 1, apartAndOneStory: 3,
			apartAndTwoStories: 4, pairsUnresolved: 0, labelledTwoStoryPairs: 5
		}, height: 220, width: 760, readoutMaxShare: 1
	});
	expect(words(separateScore)).toContain('The hand-marked pairs are unavailable.');
	expect(words(separateScore)).toContain('Scored on 2030-06-14 at a line of 0.9400, against marks by a person. It joined 1 of the 5 pairs marked as two stories, and left 3 pairs marked as one story apart.');
	expect(separateScore).toContain('data-holdout-skips="1"');
});
