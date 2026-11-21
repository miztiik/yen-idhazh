/** Do the Judgement holdout read and its rendered panel keep unknown, empty and partial evidence distinct? */
import { expect, test } from '@playwright/test';
import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { judgementEvidence } from '../src/lib/console/judgement-evidence';
import type { RecordRead } from '../src/lib/console/recording';
import { markedPairs, holdoutReading } from '../src/lib/server/content-similarity-holdout';
import { buildLedger, buildRows } from './support/ledger-lifecycle';
import { serverPanels } from './support/console-window/server-panels';

const WINDOW = { start: '2030-06-09', end: '2030-06-15' };
const LOADED = { start: '2030-03-18', end: '2030-06-15' };

function words(html: string): string {
	return html.replace(/<!--[\s\S]*?-->/g, '').replace(/<[^>]*>/g, ' ')
		.replace(/&(?:#39|apos);/g, "'").replace(/&quot;/g, '"').replace(/&amp;/g, '&')
		.replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/\s+/g, ' ').trim();
}

test('read notes name unavailable, lost and set-aside input without inventing a last run', () => {
	expect(judgementEvidence({ state: 'not-packed' }, WINDOW, LOADED)).toEqual([
		'The holdout record has not been packed yet. Its readings are unavailable.'
	]);
	expect(judgementEvidence({ state: 'unreadable', at: '<script>raw-fault</script>', fault: null }, WINDOW, LOADED)).toEqual([
		'The holdout record could not be read. Its readings are unavailable.'
	]);
	const read: RecordRead = {
		state: 'read', first: '2030-06-10', through: '2030-06-14',
		lastRows: { period: 'monthly', covers: '2030-05' },
		lostDays: ['2030-05-20', '2030-06-12'], setAside: { '2030-05': 2 }
	};
	const notes = judgementEvidence(read, WINDOW, LOADED);
	expect(notes.slice(0, 4)).toEqual([
		'The holdout record starts on 10 Jun 2030.',
		'The holdout record is packed through 14 Jun 2030. Later days have no packed reading here.',
		'The last packed period with rows in the holdout record is 1 May 2030 to 31 May 2030. This is a period, not the date of the last run.',
		'There is no holdout record for 12 Jun 2030, so its readings for that day are unavailable. The record for that day was lost and could not be recovered; it was not a quiet day.'
	]);
	expect(notes.at(-1)).toBe('The set-aside count covers the loaded input from 18 Mar 2030 to 15 Jun 2030, not only the selected window.');
	expect(notes[4]).toBe('2 holdout record files were set aside unread when this data was packed, so the loaded readings may be missing their rows. They wait in state/raw/content-similarity-judge/holdout-pairs/set-aside/ for a person to read.');
	expect(notes.join(' ')).not.toContain('20 May');
	expect(notes.join(' ')).not.toContain('raw-fault');
	expect(notes.join(' ')).toContain('2');
	expect(notes.join(' ')).toContain('set-aside');
});

test('the packed hand-mark reader preserves failure and successful empty reads', async ({}, info) => {
	const absent = info.outputPath('absent');
	expect(await markedPairs(WINDOW, absent)).toEqual({ rows: [], read: { state: 'not-packed' } });
	const root = info.outputPath('holdout-pairs');
	await buildLedger(root, { ledger: 'holdout-pairs', pinned: WINDOW.end, days: [{ ago: 0, state: 'empty' }] });
	const reading = await markedPairs(WINDOW, root);
	expect(reading.read.state).toBe('read');
	expect(reading.rows).toEqual([]);
	const folder = join(root, 'compact', 'content-similarity-judge', 'holdout-pairs', 'index');
	mkdirSync(folder, { recursive: true });
	writeFileSync(join(folder, 'daily.json'), 'not json');
	expect((await markedPairs(WINDOW, root)).read.state).toBe('unreadable');
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
	const scored = await holdoutReading({ cosineWeight: 1 }, WINDOW, root, info.outputPath('no-digest'));
	expect(scored.read).toEqual(marked.read);
	expect(scored.marked).toBe(1);
	expect(scored.marks).toEqual([]);
	expect(scored.skipped).toEqual([{ leftTitle: 'Left', rightTitle: 'Right', reason: 'the day it names is no longer published' }]);
});

test('the panel distinguishes unavailable marks from a violation beyond the score axis', async ({}, info) => {
	const { drawn } = await serverPanels(info.outputPath('panels'), [['src/routes/console/judgement/HoldoutMargin.svelte', 'HoldoutMargin']]);
	const config = {
		line: 0.85, axisBelow: 0.02, axisAbove: 0.01,
		weights: { cosineWeight: 1 }, height: 220, width: 760, readoutMaxShare: 1
	};
	const html = drawn.HoldoutMargin({
		...config,
		marks: null, agreedScores: null, skipped: [{ leftTitle: 'Left', rightTitle: 'Right', reason: 'the article carries no vector' }],
		marked: 1, evidence: ['<script>untrusted diagnostic</script>']
	});
	expect(words(html)).toContain('The holdout labels are unavailable.');
	expect(html).toContain('data-holdout-skips="1"');
	expect(html).toContain('&lt;script>untrusted diagnostic&lt;/script>');
	expect(html).not.toContain('<script>untrusted diagnostic');

	const scored = drawn.HoldoutMargin({
		...config,
		marks: [{ leftTitle: 'Left article', rightTitle: 'Right article', sameStory: false,
			markedOn: '2030-06-14', note: '', score: 0.93 }],
		agreedScores: [], skipped: [], marked: 1
	});
	expect(scored).toContain('data-holdout-state="violation"');
	expect(scored).toContain('data-holdout-margin="0.08"');
	expect(scored).toContain('data-holdout-violations="1"');
	expect(scored).toContain('data-holdout-offscale="high" data-holdout-offscale-count="1"');
	expect(scored).not.toContain('data-holdout-dot=');
	const copy = words(scored);
	expect(copy).toContain('Pairs marked as separate stories The original holdout labels came from a model, not a human review.');
	expect(copy).toContain('A score can clear the merge line without the stories folding.');
	expect(copy).not.toContain('a person marked');
	expect(copy).toContain('Left article');
});
