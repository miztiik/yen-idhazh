import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';

import {
	modelRuleRow,
	modelRuleTitle,
	modelRules,
	MODEL_RULE_LABEL,
	MODEL_RULE_ROW
} from '../src/lib/charts/frame';
import {
	namesMoved,
	namesMovedShort,
	settingsByDate,
	comparableInputs,
	type SettingsMoved,
	settingsRules,
	unreadRuleNote,
	NAMES_SHOWN,
	SETTING_WORDS,
	WORDS_IN_ORDER
} from '../src/lib/console/settings-moved';
import { BAND_UNREAD, readBand } from '../src/lib/console/band';
import { ruleBoundaries, ruleDeclaration, ruleEvents } from '../src/lib/charts/d3/model-rule';
import type { DateStamp } from '../src/lib/data/ledger';

/** Authored movement answers test current rules and words, not a retired TS producer.
 * The bounded run fixture still tests the live comparable-input normalization.
 * console-settings-moved.spec.ts owns the generated-schema word-table drift gate.
 */

const ROOT = resolve(process.cwd(), '..');

interface FixtureDay {
	date: string;
	records: { inputs: Record<string, unknown> | null }[];
}

/** The fixture, read inside the test that needs it.
 *
 * At module scope one unexpected shape raises while the file is loading and
 * takes every test in it down with a stack trace. Read here, it fails one test
 * with a message naming the file.
 */
function fixture(): FixtureDay[] {
	const path = join(ROOT, 'tests', 'fixtures', 'settings-moved', 'five-on-one-day.json');
	const parsed = JSON.parse(readFileSync(path, 'utf8')) as { days: FixtureDay[] };
	expect(parsed.days.length, `${path} carries no days`).toBeGreaterThan(0);
	return parsed.days;
}

test('current rules consume the independently authored movement answer without a derivation port', () => {
	const expected = JSON.parse(readFileSync(join(ROOT, 'tests', 'fixtures', 'settings-moved', 'five-on-one-day.expected.json'), 'utf8'));
	const shell = readBand({
		verdict: { sentence: 'A run finished.' }, size: { sentence: 'A recorded size.' }, settings_moved: expected
	});
	expect(shell.settingsMoved).toEqual(expected);
	expect(settingsRules(shell, { from: '2026-09-14', to: '2026-09-20' }, 'none')).toEqual({
		changes: [
			{ date: '2026-09-17', kind: 'settings', words: 'the prompt, the turn markers, the truncation cap and 2 more changed on this day' },
			{ date: '2026-09-18', kind: 'settings', words: 'the prompt changed on this day' },
			{ date: '2026-09-19', kind: 'settings', words: 'the sanitizer changed on this day' }
		], note: 'This chart can mark a change in how the summaries are written only from 17 Sept on.'
	});
	expect(fixture()[4].records[0].inputs?.prompt_sha256).not.toBe(fixture()[4].records[1].inputs?.prompt_sha256);
});

test('live comparable inputs omit absent values and flatten recorded settings without a change producer', () => {
	expect(comparableInputs(null)).toEqual(new Map());
	expect(comparableInputs({ prompt_sha256: null, n_ctx: '', unknown: 'ignored' })).toEqual(new Map());
	expect(comparableInputs({ n_ctx: 4096, sampling: { temperature: 0, seed: '123' } })).toEqual(new Map([
		['sampling.seed', '"123"'], ['sampling.temperature', '0'], ['n_ctx', '4096']
	]));
});

const ruleWindow = { from: '2026-09-16' as DateStamp, to: '2026-09-20' as DateStamp };
function ruleShell() {
	return { ...BAND_UNREAD, settingsMoved: {
		compared_from: '2026-09-16', changes: [
			{ date: '2026-09-17', inputs: ['prompt_sha256', 'n_ctx'] },
			{ date: '2026-09-21', inputs: ['runtime_build'] }
		]
	}, checkerMoved: {
		compared_from: '2026-09-16', changes: [
			{ date: '2026-09-17', score_moved: false },
			{ date: '2026-09-18', score_moved: true }
		]
	} };
}

test('settings and checker readouts retain two events at one boundary', () => {
	const rule = settingsRules(ruleShell(), ruleWindow, 'every');
	expect(rule).toEqual({ changes: [
		{ date: '2026-09-17', kind: 'settings', words: 'the prompt and the context size changed on this day' },
		{ date: '2026-09-17', kind: 'checker', words: 'the checker changed on this day; the faithfulness score did not' },
		{ date: '2026-09-18', kind: 'checker', words: 'the faithfulness scorer changed on this day' }
	], note: null });
	expect(ruleDeclaration(rule)).toEqual({ value: 'yes' });
	expect(ruleEvents(rule, ['2026-09-17']).lines[0]).toHaveLength(2);
	expect(ruleBoundaries(rule, ['2026-09-16', '2026-09-17'], [100, 200], 50)).toEqual([
		{ date: '2026-09-17', x: 150, kind: 'settings' }
	]);
});

test('checker filters do not remove settings and missing kinds remain independent', () => {
	const onlyScore = settingsRules(ruleShell(), ruleWindow, 'score');
	expect('changes' in onlyScore && onlyScore.changes.map((c) => `${c.date} ${c.kind}`)).toEqual([
		'2026-09-17 settings', '2026-09-18 checker'
	]);
	const shell = ruleShell();
	const missing = settingsRules({ ...shell, settingsMoved: null }, ruleWindow, 'every');
	expect('changes' in missing && missing.changes).toHaveLength(2);
	expect('note' in missing && missing.note).toContain('written did not arrive');
	const settings = settingsRules({ ...shell, checkerMoved: null }, ruleWindow, 'every');
	expect('changes' in settings && settings.changes).toHaveLength(1);
	expect('note' in settings && settings.note).toContain('checked did not arrive');
	expect(ruleDeclaration(settingsRules(BAND_UNREAD, ruleWindow, 'none')).value).toBe('no');
});

test('rule notes distinguish full, partial and unrecorded spans without invented certainty', () => {
	const empty = { ...ruleShell(), settingsMoved: { compared_from: '2026-09-16', changes: [] } };
	expect(settingsRules(empty, ruleWindow, 'none')).toEqual({
		changes: [], note: 'Nothing changed about how the summaries are written inside these 5 days.'
	});
	expect(settingsRules({ ...empty, settingsMoved: { compared_from: '2026-09-18', changes: [] } }, ruleWindow, 'none')).toEqual({
		changes: [], note: 'This chart can mark a change in how the summaries are written only from 18 Sept on. None came after that day.'
	});
	expect(settingsRules({ ...empty, settingsMoved: { compared_from: null, changes: [] } }, ruleWindow, 'none')).toEqual({
		changes: [], note: 'How the summaries are written was not recorded on these days, so this chart cannot mark a change.'
	});
	const unknown = { ...empty, settingsMoved: { compared_from: '2026-09-16', changes: [{ date: '2026-09-17', inputs: ['new_setting'] }] } };
	const unknownRule = settingsRules(unknown, ruleWindow, 'none');
	expect('changes' in unknownRule && unknownRule.changes[0].words).toBe('a recorded setting changed on this day');
});

test('score-only notes and windows before coverage make no checker-wide certainty claim', () => {
	const empty = { ...BAND_UNREAD, settingsMoved: { compared_from: '2026-09-16', changes: [] }, checkerMoved: { compared_from: '2026-09-16', changes: [{ date: '2026-09-17', score_moved: false }] } };
	expect(settingsRules(empty, ruleWindow, 'score')).toEqual({
		changes: [], note: 'Nothing changed about how the summaries are written or the faithfulness scorer inside these 5 days.'
	});

	expect(settingsRules({ ...empty, checkerMoved: { ...empty.checkerMoved, compared_from: '2026-09-18' } }, ruleWindow, 'score')).toEqual({
		changes: [], note: 'This chart can mark a change in the faithfulness scorer only from 18 Sept on. None came after that day.'
	});
	expect(settingsRules({ ...empty, settingsMoved: { compared_from: '2026-09-22', changes: [] } }, ruleWindow, 'none')).toEqual({
		changes: [], note: 'This chart can mark a change in how the summaries are written only from 22 Sept on. That is after this window.'
	});
});

test('one-day unchanged settings notes keep the common control singular', () => {
	const empty = { ...BAND_UNREAD,
		settingsMoved: { compared_from: '2026-09-16', changes: [] },
		checkerMoved: { compared_from: '2026-09-16', changes: [] } };
	const window = { from: '2026-09-20', to: '2026-09-20' };
	for (const checker of ['none', 'score', 'every'] as const) {
		const rule = settingsRules(empty, window, checker);
		expect('note' in rule && rule.note).toContain('inside this one day.');
		expect('note' in rule && rule.note).not.toContain('1 days');
		expect('changes' in rule && rule.changes).toEqual([]);
	}
});

test('one-day rule notes use the singular without changing multi-day or checker claims', () => {
	const empty = {
		...ruleShell(), settingsMoved: { compared_from: '2026-09-16', changes: [] },
		checkerMoved: { compared_from: '2026-09-16', changes: [] }
	};
	const one = { from: ruleWindow.from, to: ruleWindow.from };
	expect(settingsRules(empty, one, 'none')).toEqual({
		changes: [], note: 'Nothing changed about how the summaries are written inside this one day.'
	});
	expect(settingsRules(empty, one, 'score')).toEqual({
		changes: [], note: 'Nothing changed about how the summaries are written or the faithfulness scorer inside this one day.'
	});
	expect(settingsRules(empty, one, 'every')).toEqual({
		changes: [], note: 'Nothing changed about how the summaries are written or checked inside this one day.'
	});
	expect(settingsRules(empty, ruleWindow, 'none')).toEqual({
		changes: [], note: 'Nothing changed about how the summaries are written inside these 5 days.'
	});
});

test('the band treats absent and malformed movement fields as unknown separately', () => {
	const payload = { verdict: { sentence: 'A run finished.' }, size: { sentence: 'A recorded size.' } };
	expect(readBand(payload).settingsMoved).toBeNull();
	expect(readBand(payload).checkerMoved).toBeNull();
	for (const bad of [{}, { compared_from: null, changes: [{ date: '2026-09-17', inputs: ['prompt_sha256'] }] },
		{ compared_from: '2026-09-16', changes: [{ date: '2026-09-31', inputs: ['prompt_sha256'] }] },
		{ compared_from: '2026-09-16', changes: [{ date: '2026-09-17', inputs: ['prompt_sha256', 'prompt_sha256'] }] }]) {
		const shell = readBand({ ...payload, settings_moved: bad, checker_moved: ruleShell().checkerMoved });
		expect(shell.settingsMoved).toBeNull();
		expect(shell.checkerMoved).toEqual(ruleShell().checkerMoved);
	}
});

test('historical strings normalize renamed flags without discarding a recorded setting absent later', () => {
	const earlier = comparableInputs(fixture()[5].records[0].inputs);
	const later = comparableInputs(fixture()[6].records[0].inputs);
	expect(earlier.get('sampling.max_answer_tokens')).toBe('"900"');
	expect(later.has('sampling.max_answer_tokens')).toBe(false);
	earlier.delete('sampling.max_answer_tokens');
	expect(earlier).toEqual(later);
});

const authoredReadout: SettingsMoved[] = [
	{ date: '2026-09-17', settings: ['the prompt', 'the turn markers', 'the truncation cap', 'the sampling temperature', 'the context size'] },
	{ date: '2026-09-18', settings: ['the prompt'] },
	{ date: '2026-09-19', settings: ['the sanitizer'] }
];

test('the display contract covers keyed setting words in declared order, without raw block labels', () => {
	const names = authoredReadout[0].settings;
	expect(names).not.toContain('the sampling settings');
	expect(names).not.toContain('the sampling seed');
	const places = names.map((name) => WORDS_IN_ORDER.indexOf(name));
	expect(places).not.toContain(-1);
	expect(places).toEqual([...places].sort((left, right) => left - right));
});

test.describe('what a chart draws from it', () => {
	/** Four run columns, the way a panel hands them over: one x each, and the
	 * day that changed sitting third. */
	const drawn = ['2026-09-16', '2026-09-17', '2026-09-18', '2026-09-19'];
	const columns = [100, 200, 300, 400];

	test('a date that moved five settings draws exactly one rule', () => {
		const moved = authoredReadout;
		const rules = modelRules(
			moved.map((one) => one.date),
			drawn.slice(0, 3),
			columns.slice(0, 3)
		);
		expect(rules.map((rule) => rule.date)).toEqual(['2026-09-17', '2026-09-18']);
	});

	test('that one rule reads out all five, on one line', () => {
		const moved = settingsByDate(authoredReadout);
		const row = modelRuleRow(namesMoved(moved.get('2026-09-17') ?? []));
		expect(row.label, 'the heading a reader meets never changes').toBe(MODEL_RULE_ROW.label);
		expect(row.value).toBe(
			'the prompt, the turn markers, the truncation cap, the sampling temperature and the context size changed on this day'
		);
	});

	test('the title a reader points at names them too', () => {
		const moved = settingsByDate(authoredReadout);
		const title = modelRuleTitle('2026-09-17', namesMoved(moved.get('2026-09-17') ?? []));
		expect(title).toContain('The prompt, the turn markers');
		expect(title).toContain('Everything left of this line was written by the one before it.');
	});

	test('a date the record cannot name falls back to the sentence that names none', () => {
		// The score ledger's stamp is a digest. It says something moved and can
		// never say what, so a chart drawing a rule off it must not invent a name.
		expect(modelRuleRow('')).toEqual(MODEL_RULE_ROW);
		expect(modelRuleTitle('2026-09-17')).toContain('A new model, prompt or setting started on');
	});

	test('a date with no run record draws no rule', () => {
		const moved = authoredReadout;
		const rules = modelRules(
			moved.map((one) => one.date),
			['2026-09-13', '2026-09-14', '2026-09-15'],
			columns.slice(0, 3)
		);
		expect(rules, 'a gap in the record is not a day nothing moved on').toEqual([]);
	});

	test('a date with a rule and no reading is named in words instead', () => {
		// The state the marker exists for. A chart with no column for that day
		// cannot draw a line on it, and silence there is the one answer that
		// invites the unsafe comparison.
		const moved = authoredReadout;
		const unread = moved.filter((one) => !drawn.slice(0, 3).includes(one.date));
		expect(unread.map((one) => one.date)).toEqual(['2026-09-19']);
		const note = unreadRuleNote(unread);
		expect(note).toContain('2026-09-19');
		expect(note).toContain('the sanitizer');
		expect(note).toContain('nothing here measured that day');
	});

	test('no unread day is no sentence, rather than an empty one', () => {
		expect(unreadRuleNote([])).toBe('');
	});
});

test.describe('the words, against the contract', () => {
	test('no words are a field name with its bars swapped for spaces', () => {
		// `n_ctx` is what the runtime calls it and "the context size" is what it
		// is. A term from a subsystem is not a term for a user. Containing the
		// field name is not the failure - "the model runtime build" contains
		// "runtime build" and is the right words - BEING it is.
		for (const [field, words] of Object.entries(SETTING_WORDS)) {
			expect(words, `${field} has no words`).not.toBe('');
			expect(words, `${field}: "${words}" does not read as a thing`).toMatch(/^the /);
			expect(words, `${field}: "${words}" carries a digest spelling`).not.toContain('sha256');
			expect(
				words.toLowerCase().replace(/^the /, ''),
				`${field} is spelled out rather than named`
			).not.toBe(field.replaceAll('_', ' '));
		}
	});

	test('a list reads the way a person writes one', () => {
		expect(namesMoved([])).toBe('');
		expect(namesMoved(['the prompt'])).toBe('the prompt');
		expect(namesMoved(['the prompt', 'the context size'])).toBe('the prompt and the context size');
		expect(namesMoved(['a', 'b', 'c'])).toBe('a, b and c');
	});

	test('a strip row names three settings and then counts the rest', () => {
		// Up to the cap it is the same sentence, so a short day reads identically
		// in the row and in the hover.
		expect(namesMovedShort(['a', 'b', 'c'])).toBe(namesMoved(['a', 'b', 'c']));
		// Past it the count is kept rather than dropped. Three names and no number
		// cannot tell a day that moved three settings from one that moved seven.
		expect(namesMovedShort(['a', 'b', 'c', 'd'])).toBe('a, b, c and 1 more');
		expect(namesMovedShort(['a', 'b', 'c', 'd', 'e', 'f', 'g'])).toBe('a, b, c and 4 more');
	});

	test('the hover keeps every name the row had to cut', () => {
		const seven = [
			'the prompt',
			'the context size',
			'the weights',
			'the runtime build',
			'the batch size',
			'the thread count',
			'the output schema'
		];
		const full = modelRuleTitle('2026-09-17', namesMoved(seven));
		// The title opens the sentence, so the first name is capitalised there.
		// What matters is the four the row had no line for.
		for (const name of seven.slice(NAMES_SHOWN)) expect(full).toContain(name);
		// The row keeps the first three and the count. The four it dropped are
		// still one hover away, so nothing is lost - only moved off one line.
		const row = modelRuleRow(namesMovedShort(seven)).value;
		expect(row).toContain('and 4 more');
		expect(row).not.toContain('the output schema');
	});

	test('the rule carries its own words on the plot', () => {
		// A rule a reader has to hover to identify is a rule most readers never
		// identify, so the label is plain English and names no subsystem.
		expect(MODEL_RULE_LABEL).toBe('setup changed');
		expect(MODEL_RULE_LABEL).not.toMatch(/pipeline|fingerprint|manifest|inputs/i);
	});
});
