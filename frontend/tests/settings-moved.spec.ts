import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';

import { modelRuleRow, modelRuleTitle, modelRules, MODEL_RULE_ROW } from '../src/lib/charts/frame';
import {
	namesMoved,
	settingsByDate,
	settingsMoved,
	unreadRuleNote,
	SETTING_WORDS
} from '../src/lib/console/settings-moved';

/**
 * Which settings moved, and what a chart may say about it.
 *
 * A dashed rule saying "something changed here" is a warning. A rule saying
 * "the prompt and the context size changed here" is a finding, and the
 * difference is whether an owner can decide anything from it. What makes the
 * second possible is that a run has recorded its inputs field by field since
 * 2026-09-12, so the same comparison that draws the line can name what moved.
 *
 * **Driven by a bounded fixture, never by the archive.** Every case below reads
 * `tests/fixtures/settings-moved/five-on-one-day.json`, six days of run records
 * that carry states the committed archive has never produced and could produce
 * at any time. A test that walked the archive would cost more every run and
 * would go red because somebody published a day (`CLAUDE.md` section 13).
 *
 * The last case is the drift gate: the words table must cover `PipelineInputs`
 * exactly, read out of the generated schema, so a field added to the contract
 * next month fails here rather than going unnamed on the page for a year.
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

test.describe('what moved, and on which day', () => {
	test('five settings on one date are one entry naming all five', () => {
		const moved = settingsMoved(fixture());
		const day = moved.filter((one) => one.date === '2026-09-17');
		expect(day.length, 'a day that moved five settings is one entry, never five').toBe(1);
		expect(day[0].settings).toEqual([
			'the prompt',
			'the turn markers',
			'the truncation cap',
			'the sampling settings',
			'the context size'
		]);
	});

	test('the names come out in the order the contract declares them', () => {
		// Never in the order the data happened to differ: a readout whose order
		// changes with the data is a readout a reader cannot scan twice.
		const moved = settingsMoved(fixture());
		const order = Object.values(SETTING_WORDS);
		for (const one of moved) {
			const places = one.settings.map((name) => order.indexOf(name));
			expect(places, `${one.date} names a setting the words table does not`).not.toContain(-1);
			expect(places, `${one.date} names its settings out of contract order`).toEqual(
				[...places].sort((left, right) => left - right)
			);
		}
	});

	test('a day with no recorded inputs is no entry at all', () => {
		// 100 of 118 committed run entries carried no record when this row was
		// written. Drawing "nothing moved" for a day nothing was recorded on is
		// the same claim as a zero theft figure, and is refused for the same
		// reason.
		const moved = settingsMoved(fixture());
		expect(moved.map((one) => one.date)).not.toContain('2026-09-14');
		expect(moved.map((one) => one.date)).not.toContain('2026-09-15');
	});

	test('the first recorded day is never an entry - nothing precedes it', () => {
		expect(settingsMoved(fixture()).map((one) => one.date)).not.toContain('2026-09-16');
	});

	test('a day that only went back to an older value started nothing', () => {
		expect(settingsMoved(fixture()).map((one) => one.date)).not.toContain('2026-09-18');
	});

	test('one setting on its own is one entry naming one', () => {
		const moved = settingsMoved(fixture());
		const day = moved.find((one) => one.date === '2026-09-19');
		expect(day?.settings).toEqual(['the sanitizer']);
	});

	test('a fixture with no run record at all names nothing', () => {
		expect(settingsMoved([])).toEqual([]);
	});
});

test.describe('what a chart draws from it', () => {
	/** Four run columns, the way a panel hands them over: one x each, and the
	 * day that changed sitting third. */
	const drawn = ['2026-09-16', '2026-09-17', '2026-09-18', '2026-09-19'];
	const columns = [100, 200, 300, 400];

	test('a date that moved five settings draws exactly one rule', () => {
		const moved = settingsMoved(fixture());
		const rules = modelRules(
			moved.map((one) => one.date),
			drawn.slice(0, 3),
			columns.slice(0, 3)
		);
		expect(rules.map((rule) => rule.date)).toEqual(['2026-09-17']);
	});

	test('that one rule reads out all five, on one line', () => {
		const moved = settingsByDate(settingsMoved(fixture()));
		const row = modelRuleRow(namesMoved(moved.get('2026-09-17') ?? []));
		expect(row.label, 'the heading a reader meets never changes').toBe(MODEL_RULE_ROW.label);
		expect(row.value).toBe(
			'the prompt, the turn markers, the truncation cap, the sampling settings and the context size changed on this day'
		);
	});

	test('the title a reader points at names them too', () => {
		const moved = settingsByDate(settingsMoved(fixture()));
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
		const moved = settingsMoved(fixture());
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
		const moved = settingsMoved(fixture());
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
	test('every recorded input has words, and every word has an input', () => {
		const schema = JSON.parse(
			readFileSync(join(ROOT, 'schemas', 'run-manifest.schema.json'), 'utf8')
		) as { $defs?: Record<string, { properties?: Record<string, unknown> }> };
		const declared = Object.keys(schema.$defs?.PipelineInputs?.properties ?? {});
		expect(declared.length, 'the generated schema declares no recorded inputs').toBeGreaterThan(0);
		expect(
			declared.sort(),
			'a recorded input with no words, or words with no recorded input'
		).toEqual(Object.keys(SETTING_WORDS).sort());
	});

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
});
