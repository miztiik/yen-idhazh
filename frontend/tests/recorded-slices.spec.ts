/** Does every declared panel query reproduce its recorded native-canary answer? */
import { expect, test } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import * as pipelines from '../src/lib/console/queries/pipelines';
import * as model from '../src/lib/console/queries/model';
import * as machine from '../src/lib/console/queries/machine';
import * as voices from '../src/lib/console/queries/voices';
import {
	createQueryWindow, rangeFor, type PanelQuery, type Range, type RouteReach
} from '../src/lib/console/queries/window';
import { joinItemHosts } from '../src/lib/console/queries/shared';
import type { SliceResult } from '../src/lib/data/slice-shapes';
import { consoleConfig } from '../src/lib/server/config';
import { reachFromDisk, sliceFromDisk } from '../src/lib/server/ledger-disk';
import { backendPython } from './support/backend-python';

const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const FIXTURES = path.join(REPO, 'tests', 'fixtures', 'console');
// These four modules are the complete row-4 scope, not a repository walk.
const MODULES = { pipelines, model, machine, voices } satisfies
	Record<string, Readonly<Record<string, PanelQuery>>>;
let state: string;

function queriesIn(exports: Readonly<Record<string, PanelQuery>>): PanelQuery[] {
	return [...new Map(Object.values(exports).map((query) => [query.name, query])).values()];
}

function python(args: string[]): string {
	return execFileSync(backendPython(REPO), args, {
		cwd: REPO, encoding: 'utf8',
		env: { ...process.env, PYTHONPATH: path.join(REPO, 'backend') }
	});
}

test.beforeAll(() => {
	// An owned native fixture root keeps this logic spec independent of site builds.
	test.setTimeout(300_000);
	const root = test.info().outputPath('recorded-canary');
	state = path.join(root, 'state');
	python([path.join('backend', 'utilities', 'build_canary_day.py'), '--out', path.join(root, 'digest'), '--state', state]);
	execFileSync(process.execPath, [
		path.join('scripts', 'build-canary.mjs'), '--fixtures-only', '--fixture-root', root
	], {
		cwd: path.join(REPO, 'frontend'), encoding: 'utf8',
		env: { ...process.env, IDHAZH_PYTHON: backendPython(REPO) }
	});
});

/** Ordering is not declared by PanelQuery; keep every row and every cell. */
function canonical(answer: SliceResult): SliceResult {
	if (answer.state !== 'ok') return answer;
	return { ...answer, rows: [...answer.rows].sort((a, b) =>
		JSON.stringify(a).localeCompare(JSON.stringify(b))) };
}

function record(route: string, name: string, answer: SliceResult): void {
	const filename = path.join(FIXTURES, route, `${name}.json`);
	const actual = canonical(answer);
	if (process.env.IDHAZH_RECORD_SLICES === '1') {
		mkdirSync(path.dirname(filename), { recursive: true });
		writeFileSync(filename, `${JSON.stringify(actual, null, 2)}\n`, 'utf8');
	}
	// Read in the test, never at module import; edited snapshots must fail.
	const expected: unknown = JSON.parse(readFileSync(filename, 'utf8'));
	expect(actual, `${route}/${name}.json`).toEqual(expected);
}

/** Independent UTC arithmetic; do not use the production range helper twice. */
function expectedRange(query: PanelQuery, preset: number, reach: RouteReach): Range {
	const own = reach.ledgers[query.ledger];
	if (own?.state !== 'ok' || reach.through === null) {
		throw new Error(`${query.name} has no packed canary reach`);
	}
	const asked = query.span === 'newest-day' ? 1 :
		query.span === 'widest' ? Math.max(...consoleConfig().window_presets) : preset;
	const to = Date.parse(`${reach.through}T00:00:00Z`);
	const from = Math.max(Date.parse(`${own.first}T00:00:00Z`), to - (asked - 1) * 86_400_000);
	return {
		from: new Date(from).toISOString().slice(0, 10), to: reach.through,
		days: (to - from) / 86_400_000 + 1, asked
	};
}

for (const [route, exports] of Object.entries(MODULES)) {
	test(`${route}: each query export is named and has a recorded answer`, () => {
		for (const [name, query] of Object.entries(exports)) {
			expect(query.name).toBe(name);
			expect(query.columns.length).toBeGreaterThan(0);
			expect(query.columns).not.toContain('*');
		}
	});

	for (const query of queriesIn(exports)) {
		test(`${route}/${query.name}: the default slice matches its recorded native answer`, async () => {
			const window = createQueryWindow({
				reach: (ledger) => reachFromDisk(state, ledger),
				rows: (ledger, options) => sliceFromDisk(state, ledger, options)
			});
			const reach = await window.routeReach(queriesIn(exports).map((entry) => entry.ledger));
			const ends = Object.values(reach.ledgers).flatMap((held) =>
				held?.state === 'ok' ? [held.through] : []);
			expect(reach.through).toBe(ends.sort()[0]);
			const preset = consoleConfig().default_window_days;
			const range = rangeFor(query, preset, reach, consoleConfig().window_presets);
			expect(range).toEqual(expectedRange(query, preset, reach));
			if (!('from' in range)) throw new Error(`${query.name} did not name a canary range`);
			const first = window.sliceOnce(query, range);
			expect(window.sliceOnce(query, range)).toBe(first);
			record(route, query.name, await first);
		});
	}
}

test('the packed canary retains length, inferred time, watchlist, negative gap and failed re-slice states', async () => {
	const reach = await reachFromDisk(state, 'item-health');
	if (reach.state !== 'ok') throw new Error('native item-health canary was not packed');
	const answer = await sliceFromDisk(state, 'item-health', {
		columns: [
			'date', 'stage', 'outcome', 'summary_finish_reason', 'label_finish_reason',
			'watchlist_hit', 'on_front_page', 'published_at', 'time_source',
			'stage_gap_ms', 'span_integrity', 'elements_found', 'element_class',
			'machine_job', 'machine_shard', 'run_id'
		],
		from: reach.first, to: reach.through
	});
	expect(answer.state).toBe('ok');
	const rows = answer.rows;
	expect(rows.some((row) => row.summary_finish_reason === 'length' || row.label_finish_reason === 'length')).toBe(true);
	expect(rows.some((row) => row.watchlist_hit === true && row.on_front_page === true)).toBe(true);
	expect(rows.some((row) => row.time_source === 'first_seen' && typeof row.published_at === 'string')).toBe(true);
	expect(rows.some((row) => typeof row.stage_gap_ms === 'number' && row.stage_gap_ms < 0)).toBe(true);
	expect(rows.some((row) => row.span_integrity === false && row.elements_found === null && row.element_class === null)).toBe(true);
	const legacy = rows.filter((row) => row.machine_job === null && row.machine_shard !== null);
	expect(legacy.length).toBeGreaterThan(0);
	const hosts = await sliceFromDisk(state, 'host-fingerprint', {
		columns: ['date', 'run_id', 'job', 'shard'], from: reach.first, to: reach.through
	});
	expect(hosts.state).toBe('ok');
	expect(hosts.rows).toHaveLength(15);
	expect(new Set(hosts.rows.map((row) =>
		JSON.stringify([row.date, row.run_id, row.job, row.shard]))).size).toBe(15);
	expect(hosts.rows.filter((row) => row.date === '2026-08-20' &&
		row.run_id === '2026-08-20-2').map((row) => [row.job, row.shard]).sort()).toEqual([
		['assemble', 0], ['plan', 0], ['work', 0], ['work', 1]
	]);
	expect(joinItemHosts(legacy, hosts.rows).rows.some((row) => row.host !== null)).toBe(true);
	const hostDays = new Set(hosts.rows.map((row) => row.date));
	expect(rows.some((row) => row.stage === 'publish' && row.outcome === 'ok' && !hostDays.has(row.date))).toBe(true);
});

const FETCH_STATES = [
	'import json, sys',
	'from pathlib import Path',
	'from idhazh import ledger',
	'from idhazh.contracts.base import derive_url_key',
	'from idhazh.contracts.item_health import ItemHealthRow, ItemStage, ItemOutcome, FailureCode',
	'from idhazh.contracts.ledger_name import LedgerName',
	'from utilities import build_canary_day as canary',
	'root = Path(sys.argv[1])',
	'rows = []',
	'for suffix, code, status in [("rate", FailureCode.HTTP_RATE_LIMITED, 429), ("network", FailureCode.NETWORK_ERROR, None)]:',
	'    url = "https://canary.example/fetch-" + suffix',
	'    rows.append(ItemHealthRow(version=ItemHealthRow.schema_version(), date=canary.DATE, run_id=canary.SCORE_RUN_ID, item_id="fetch-" + suffix + "-0001", url_key=derive_url_key(url), canonical_url=url, vertical="ai", source_id="canary-" + suffix, stage=ItemStage.FETCH, outcome=ItemOutcome.FAILED, code=code, http_status=status))',
	'ledger.persist(root / "state", rows, ledger=LedgerName.ITEM_HEALTH, covers=canary.DATE, identity=canary._fixture_writer(canary.SCORE_RUN_ID))',
	'canary.pack_fixture_ledgers(root / "state", Path.cwd())',
	'print(json.dumps({"day": canary.DATE, "rows": len(rows)}))'
].join('\n');

test('feedsFailedQuery records real 429 and network failures without moving shared canary counts', async () => {
	const root = test.info().outputPath('fetch-states');
	const filed: { day: string; rows: number } = JSON.parse(python(['-c', FETCH_STATES, root]).trim().split('\n').at(-1)!);
	expect(filed.rows).toBe(2);
	const query = voices.feedsFailedQuery;
	const answer = await sliceFromDisk(path.join(root, 'state'), query.ledger, {
		columns: query.columns, where: query.where, from: filed.day, to: filed.day
	});
	expect(answer.state).toBe('ok');
	expect(answer.rows).toHaveLength(2);
	expect(answer.rows.some((row) => row.code === 'http_rate_limited' && row.http_status === 429)).toBe(true);
	expect(answer.rows.some((row) => row.code === 'network_error' && row.http_status === null)).toBe(true);
	record('voices', 'feedsFailedStates', answer);
});

test('a missing native root and a packed quiet day remain different answers', async () => {
	const missing = await sliceFromDisk(test.info().outputPath('no-record'), 'item-health', {
		columns: ['date'], from: '2026-08-20', to: '2026-08-20'
	});
	expect(missing).toEqual({ state: 'missing', rows: [], fault: 'not-packed' });
	const reach = await reachFromDisk(state, 'item-health');
	if (reach.state !== 'ok') throw new Error('native canary was not packed');
	const after = new Date(`${reach.through}T00:00:00Z`);
	after.setUTCDate(after.getUTCDate() + 1);
	const day = after.toISOString().slice(0, 10);
	const quiet = await sliceFromDisk(state, 'item-health', {
		columns: ['date'], from: day, to: day
	});
	expect(quiet.state).toBe('quiet');
	expect(quiet.rows).toEqual([]);
});
