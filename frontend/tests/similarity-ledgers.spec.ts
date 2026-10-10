import { expect, test } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { ledgerFolder } from '../src/lib/data/slice-reader';
import { FITTED_LINE_COLUMNS, fittedLines, type FittedLine } from '../src/lib/server/content-similarity-judge';
import { backendPython } from './support/backend-python';
import { buildLedger, everyDay, quietDays } from './support/ledger-lifecycle';

/**
 * Does the Judgement route read the fitted line the council files?
 *
 * The council's save job files one fitted line a run through the ledger door,
 * under `raw/content-similarity-judge/fitted-thresholds/`, and the gardener packs
 * it under `compact/content-similarity-judge/fitted-thresholds/`. The page reads
 * the packed files through the query door, and nothing else.
 *
 * The oracle runs the backend itself: the night before is a line a fit moved,
 * filed through the door the way the fitting stage files one, then the fitting
 * stage runs a night and its re-run over the contracts' own published day, and
 * the gardener's shipped compaction packs both days. The reader then returns the
 * values the backend reads back from the same packed files. Every file is
 * written under the test's own output folder, so nothing here reads the
 * committed archive (`CLAUDE.md` section 13). The backend's own half of the
 * move is `backend/tests/test_similarity_fit.py`.
 *
 * The other cases read a packed record this file builds through the door's own
 * query engine, and the last binds the reader's folder to `config/ledgers.json`.
 */

const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const FIXTURES = path.join(REPO, 'tests', 'fixtures', 'contracts');
const FITTED = ['content-similarity-judge', 'fitted-thresholds'] as const;

/** The published day the contracts' own fixture holds, the night the stage fits. */
const NIGHT = '2026-08-21';
/** The night before it, a line a fit moved. */
const BEFORE = '2026-08-20';
/** The council run that fitted the night before, and the night's run and its re-run. */
const BEFORE_RUN = '2026-08-21-37000000001';
const NIGHT_RUN = '2026-08-22-37000000002';
const RERUN = '2026-08-22-37000000003';

/**
 * File the night before through the door, fit the night twice, and pack both days.
 *
 * A fixed program over fixed arguments, every path one this test made: the
 * contracts' fixtures, the folder the test owns, the dates and the runs above.
 * It prints every row the backend reads back from the packed files.
 */
const A_FIXTURE_NIGHT = [
	'import json, shutil, sys',
	'from datetime import date, timedelta',
	'from pathlib import Path',
	'from idhazh import assemble, config, ledger',
	'from idhazh.contracts.base import ServerJob',
	'from idhazh.contracts.file_envelope import WriterIdentity',
	'from idhazh.contracts.fitted_similarity_threshold import FittedSimilarityThreshold',
	'from idhazh.contracts.ledger_name import LedgerName',
	'from idhazh.gardener.context import TaskContext',
	'from idhazh.gardener.file_listing import FileListing',
	'from idhazh.gardener.tasks import compaction',
	'from idhazh.stages.set_merge_line import stage_set_merge_line',
	'root, fixtures, night, before, before_run = Path(sys.argv[1]), Path(sys.argv[2]), *sys.argv[3:6]',
	'runs = sys.argv[6:]',
	'state, digest = root / "state", root / "digest"',
	'which = LedgerName.CONTENT_SIMILARITY_JUDGE_FITTED_THRESHOLDS',
	'def council(run, producer):',
	'    return WriterIdentity(run_id=run, attempt=1, job=ServerJob.SAVE_COUNCIL_RESULTS, shard=0, producer=producer, git_sha="0" * 40)',
	'moved = FittedSimilarityThreshold.from_json((fixtures / "fitted-similarity-threshold" / "the-clamp-held-a-fall-back-to-the-step.json").read_text(encoding="utf-8"))',
	'moved = FittedSimilarityThreshold.model_validate(moved.model_dump() | {"date": before, "run_id": before_run})',
	'ledger.persist(state, [moved], ledger=which, covers=before, identity=council(before_run, "stages.set_merge_line"))',
	'published = assemble.day_dir(digest, night)',
	'published.mkdir(parents=True)',
	'shutil.copyfile(fixtures / "digest-day" / "two-runs.json", published / "digest.json")',
	'for run in runs:',
	'    stage_set_merge_line(night, run_id=run, settings=config.load(), identity=council(run, "council.session"), state_dir=state, digest_root=digest)',
	'gardener = config.load_gardener()',
	'policy = gardener.tasks[config.compaction_task(which)]',
	'compaction.run(TaskContext(state_dir=state, repo_root=root, today=date.fromisoformat(night) + timedelta(days=2), policy=policy, run_id=night + "-1", attempt=1, job=ServerJob.RUN_TASKS, shard=0, git_sha="0" * 40, owned_folders=tuple(folder for folder in policy.owns if (root / folder).is_dir()), listing=FileListing.from_disk(root, policy.owns, paths=(root / folder for folder in policy.owns)), first_ledger_year=gardener.config.first_ledger_year))',
	'assert not ledger.list_raw_files(state, which), "a raw day was left unpacked"',
	'rows = ledger.load_days(state, which, [before, night], model=FittedSimilarityThreshold)',
	'print(json.dumps([row.model_dump(mode="json") for row in rows]))'
].join('\n');

/** One fitted row as the backend reads it back, by its contract's own field names. */
type FiledRow = Record<string, string | number | boolean | null>;

/** The line the page draws for one row the backend read back: the same fields, by the page's names. */
function asLine(row: FiledRow): FittedLine {
	return {
		date: row.date as string,
		runId: row.run_id as string,
		previous: row.previous as number,
		proposed: row.proposed as number | null,
		afterDamping: row.after_damping as number | null,
		applied: row.applied as number,
		clampKind: row.clamp_kind as string,
		clampMovement: row.clamp_movement as number,
		heldReason: row.held_reason as string,
		maxDownStep: row.max_down_step as number,
		maxUpStep: row.max_up_step as number,
		disagreementRate: row.disagreement_rate as number,
		unclearRate: row.unclear_rate as number,
		pairsInBand: row.pairs_in_band as number,
		pairsJudged: row.pairs_judged as number,
		pairsUsable: row.pairs_usable as number,
		negativesOnRecord: row.negatives_on_record as number,
		aboveLineOnRecord: row.above_line_on_record as number,
		daysOnRecord: row.days_on_record as number,
		cosineWeight: row.cosine_weight as number | null
	};
}

/** Run the fixture night under `root` and hand back what the backend read back from the packed files. */
function aFixtureNight(root: string): FiledRow[] {
	const printed = execFileSync(
		backendPython(REPO),
		['-c', A_FIXTURE_NIGHT, root, FIXTURES, NIGHT, BEFORE, BEFORE_RUN, NIGHT_RUN, RERUN],
		{ cwd: REPO, env: { ...process.env, PYTHONPATH: path.join(REPO, 'backend') }, encoding: 'utf8' }
	);
	return JSON.parse(printed.trim().split('\n').at(-1) ?? '[]') as FiledRow[];
}

test('THE ORACLE: the page reads the fitted line the council files and the gardener packs, value for value', async () => {
	// Most of this is the backend starting: on a slow Windows machine its imports
	// alone took two minutes.
	test.setTimeout(300_000);
	const root = test.info().outputPath('night');

	const filed = aFixtureNight(root);
	const reading = await fittedLines({ start: BEFORE, end: NIGHT }, path.join(root, 'state'));
	const lines = reading.rows;
	expect(reading.read.state).toBe('read');

	// The backend read back three rows: the night before, and the night's run and re-run.
	expect(filed.map((row) => `${row.date} ${row.run_id}`).sort()).toEqual([
		`${BEFORE} ${BEFORE_RUN}`,
		`${NIGHT} ${NIGHT_RUN}`,
		`${NIGHT} ${RERUN}`
	]);
	// The page draws one line a date, the newest run's, with every value the backend holds.
	const newest = filed.filter((row) => row.run_id !== NIGHT_RUN);
	expect(lines).toEqual(newest.map(asLine).sort((left, right) => left.date.localeCompare(right.date)));
	// The night was held, and its fit read the night before's line through the door.
	expect(lines.map((line) => [line.date, line.runId, line.previous, line.applied, line.heldReason])).toEqual([
		[BEFORE, BEFORE_RUN, 0.94, 0.93, 'none'],
		[NIGHT, RERUN, 0.93, 0.93, 'shards_missing']
	]);
});

/** Every column the reader asks for, each with one value, as the contracts' moved fixture holds it. */
function aMovedLine(): Record<string, string | number> {
	const row = JSON.parse(
		readFileSync(path.join(FIXTURES, 'fitted-similarity-threshold', 'the-clamp-held-a-fall-back-to-the-step.json'), 'utf8')
	) as Record<string, string | number>;
	return Object.fromEntries(
		FITTED_LINE_COLUMNS.filter((name) => name !== 'date').map((name) => [name, row[name]!])
	);
}

test('a record the gardener has not packed reads no line, rather than an error', async () => {
	const root = test.info().outputPath('nothing-packed');

	expect(await fittedLines({ start: BEFORE, end: NIGHT }, root)).toEqual({ rows: [], rates: [], rejected: [], read: { state: 'not-packed' } });
});

test('a window that starts after the newest packed day reads no line, rather than an old one', async () => {
	// Packed with one line 40 days before the pinned day, and quiet after.
	const state = test.info().outputPath('state');
	await buildLedger(state, {
		ledger: 'fitted-thresholds',
		pinned: NIGHT,
		days: [...everyDay(40, 40), ...quietDays(39, 0)],
		columns: aMovedLine()
	});

	const empty = await fittedLines({ start: BEFORE, end: NIGHT }, state);
	expect(empty.rows).toEqual([]);
	expect(empty.read.state).toBe('read');
	expect((await fittedLines({ start: '2026-07-01', end: NIGHT }, state)).rows.map((line) => line.date)).toEqual([
		'2026-07-12'
	]);
});

test('the registry files the fitted line under the judge folder the reader opens', () => {
	const registry = JSON.parse(
		readFileSync(path.join(REPO, 'config', 'ledgers.json'), 'utf8')
	) as { families: { name: string; ledgers: { name: string }[] }[] };
	const judge = registry.families.find((family) => family.name === 'content-similarity-judge');
	const entry = judge?.ledgers.find((ledger) => ledger.name === 'fitted-thresholds');

	expect(entry).toEqual({
		name: 'fitted-thresholds', grain: 'raw-and-compact', prefix: [...FITTED], stem: null, suffix: null
	});
	expect(ledgerFolder('fitted-thresholds')).toBe(FITTED.join('/'));
});