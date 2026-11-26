/** Do the staged readers agree after the hardware and serving records split? */
import { expect, test } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { mkdirSync, readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { fleetJobs } from '../src/lib/charts/fleet';
import { platformMixQuery, servingSpeedQuery } from '../src/lib/console/queries/machine';
import { nodeEngine } from '../src/lib/data/engine';
import { engineExtensionRepository, explorerConfig } from '../src/lib/server/config';
import { sliceFromDisk } from '../src/lib/server/ledger-disk';
import { backendPython } from './support/backend-python';

const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const FRONTEND = path.join(REPO, 'frontend');
const EARLIER = '2026-07-11';
const YESTERDAY = '2026-08-19';
const TODAY = '2026-08-20';
let canary: string;
let staged: string;

function python(args: string[]): string {
	return execFileSync(backendPython(REPO), args, {
		cwd: REPO, encoding: 'utf8',
		env: { ...process.env, PYTHONPATH: path.join(REPO, 'backend') }
	});
}

test.beforeAll(() => {
	test.setTimeout(300_000);
	canary = test.info().outputPath('native-canary');
	const digest = path.join(canary, 'digest');
	const state = path.join(canary, 'state');
	python([path.join('backend', 'utilities', 'build_canary_day.py'), '--out', digest, '--state', state]);
	execFileSync(process.execPath, [
		path.join('scripts', 'build-canary.mjs'), '--fixtures-only', '--fixture-root', canary
	], {
		cwd: FRONTEND, env: { ...process.env, IDHAZH_PYTHON: backendPython(REPO) }
	});

	const build = test.info().outputPath('publication');
	mkdirSync(build, { recursive: true });
	execFileSync(process.execPath, [path.join(FRONTEND, 'scripts', 'stage-publication.mjs')], {
		cwd: build, env: { ...process.env, DIGEST_ROOT: digest, STATE_ROOT: state }
	});
	staged = path.join(build, 'static');
});

test('Hardware and the audit prefer one paired observation and keep hosts without a match', async () => {
	const state = path.join(staged, 'state');
	const hosts = await sliceFromDisk(state, platformMixQuery.ledger, {
		...platformMixQuery, from: EARLIER, to: TODAY
	});
	const serving = await sliceFromDisk(state, servingSpeedQuery.ledger, {
		...servingSpeedQuery, from: EARLIER, to: TODAY
	});
	expect([hosts.state, serving.state]).toEqual(['ok', 'ok']);
	expect(hosts.rows).toContainEqual(expect.objectContaining({
		version: '2026-11-26', run_id: `${TODAY}-2`, task_name: 'work',
		server_prompt_tokens: null, server_prompt_seconds: null,
	}));
	expect(serving.rows).toHaveLength(4);
	const jobs = fleetJobs(hosts.rows, serving.rows);
	expect(jobs).toHaveLength(15);
	expect(fleetJobs(hosts.rows)).toHaveLength(jobs.length);
	const work = (run: string) => jobs.filter((job) => job.runId === run &&
		(job.taskName ?? job.job) === 'work').sort((a, b) => a.shard! - b.shard!);
	expect(work(`${TODAY}-2`).map((job) => job.rate)).toEqual([30, 962 / 83.73]);
	expect(work(`${YESTERDAY}-1`).map((job) => job.rate)).toEqual([1300 / 117.74, 860 / 78.18]);
	expect(work(`${TODAY}-1`).map((job) => job.rate)).toEqual([null, null]);
	expect(work(`${EARLIER}-1`).map((job) => job.rate)).toEqual([null, null]);

	const audit = [
		'import json, sys',
		'from pathlib import Path',
		'from idhazh import ledger',
		'from idhazh.contracts.ledger_name import LedgerName',
		'from idhazh.contracts.task_performance import TaskPerformanceRow',
		'from idhazh.telemetry.host_prompt_totals import read_host_prompt_totals',
		'from idhazh.telemetry.publish.console_band import machine_facts',
		'from utilities.reconcile_prefill import reconcile',
		'roots = [Path(sys.argv[1]), Path(sys.argv[2])]',
		'runs = [reconcile(root, run_id=run) for root in roots for run in sys.argv[3:]]',
		'late = ledger.load_days(roots[1], LedgerName.TASK_PERFORMANCE, [sys.argv[6][:10]], model=TaskPerformanceRow)',
		'assert len(late) == 1 and late[0].server_prompt_tokens == 5000',
		'band = machine_facts(read_host_prompt_totals(roots[0], [sys.argv[3][:10]]))',
		'print(json.dumps({',
		'    "audit": [[r.server.tokens, r.server.seconds, r.server.parts] for r in runs],',
		'    "band": [band.read_shards, band.read_spread],',
		'}))'
	].join('\n');
	const expected = [[3362, 80 + 83.73, 2], [2160, 117.74 + 78.18, 2], [0, 0, 0], [0, 0, 0]];
	const proof = JSON.parse(python(['-c', audit, state, path.join(canary, 'state'),
		`${TODAY}-2`, `${YESTERDAY}-1`, `${TODAY}-1`, `${EARLIER}-1`]));
	expect(proof.audit).toEqual([...expected, ...expected]);
	expect(proof.band).toEqual([2, 30 / (962 / 83.73)]);
});

test('the saved throughput SQL binds with or without physical legacy columns', async () => {
	const example = explorerConfig().examples.find(({ id }) => id === 'throughput-by-machine');
	if (example === undefined) throw new Error('The saved throughput question is missing.');
	const engine = await nodeEngine(createRequire(import.meta.url).resolve, engineExtensionRepository());
	const [year, month, day] = TODAY.split('-');
	const file = (ledger: string) => path.join(staged, 'state', 'compact', ledger, 'daily', year, month, `${day}.parquet`);
	const hostPath = file('host-fingerprint');
	const hardwarePath = test.info().outputPath('hardware-only.parquet');
	// Derive the new physical layout from the same staged hosts, not different rows.
	python(['-c', [
		'import sys',
		'import pyarrow.parquet as pq',
		'table = pq.read_table(sys.argv[1])',
		'legacy = ["job_seconds", "model_load_ms", "server_prompt_tokens", "server_prompt_seconds"]',
		'pq.write_table(table.drop_columns(legacy), sys.argv[2])'
	].join('\n'), hostPath, hardwarePath]);
	const host = await engine.register(readFileSync(hostPath));
	const task = await engine.register(readFileSync(file('task-performance')));
	const hardware = await engine.register(readFileSync(hardwarePath));
	try {
		const run = (hostFile: string, empty = false) => engine.rows(`
			WITH "host-fingerprint" AS (SELECT * FROM read_parquet('${hostFile}')),
			     "task-performance" AS (SELECT * FROM read_parquet('${task}') ${empty ? 'WHERE FALSE' : ''})
			SELECT cpu_model, prompt_tokens_per_second, jobs::INTEGER AS jobs FROM (${example.sql})
		`, []);
		const current = { cpu_model: expect.any(String), prompt_tokens_per_second: 30, jobs: 1 };
		expect(await run(host)).toEqual([
			current, { cpu_model: null, prompt_tokens_per_second: 962 / 83.73, jobs: 1 }
		]);
		expect(await run(hardware)).toEqual([current]);
		expect(await run(hardware, true)).toEqual([]);
	} finally {
		await engine.drop([host, task, hardware]);
	}
});
