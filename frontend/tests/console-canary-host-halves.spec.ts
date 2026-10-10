/** Do a native probe and whole completion remain one job in the Hardware view? */
import { expect, test } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { fleetJobs, fleetView } from '../src/lib/charts/fleet';
import { machineKeys, machineRamp } from '../src/lib/charts/machine-colour';
import { platformMixQuery } from '../src/lib/console/queries/machine';
import type { Row, SliceResult } from '../src/lib/data/slice-shapes';
import { consoleConfig } from '../src/lib/server/config';
import { sliceFromDisk } from '../src/lib/server/ledger-disk';
import { backendPython } from './support/backend-python';

const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
let canary: string;

function python(args: string[]): string {
	return execFileSync(backendPython(REPO), args, {
		cwd: REPO, encoding: 'utf8',
		env: { ...process.env, PYTHONPATH: path.join(REPO, 'backend') }
	});
}

test.beforeAll(() => {
	test.setTimeout(300_000);
	canary = test.info().outputPath('native-canary');
	python([
		path.join('backend', 'utilities', 'build_canary_day.py'),
		'--out', path.join(canary, 'digest'), '--state', path.join(canary, 'state')
	]);
	execFileSync(process.execPath, [
		path.join('scripts', 'build-canary.mjs'), '--fixtures-only', '--fixture-root', canary
	], {
		cwd: path.join(REPO, 'frontend'), encoding: 'utf8',
		env: { ...process.env, IDHAZH_PYTHON: backendPython(REPO) }
	});
});

// Re-file the real fixture rows, not fake parquet or a hand-written compact index.
const FILE_HOSTS = [
	'import csv, json, sys',
	'from datetime import date, timedelta',
	'from pathlib import Path',
	'from idhazh import ledger',
	'from idhazh.contracts.host_fingerprint import HostFingerprintRow',
	'from idhazh.contracts.ledger_name import LedgerName',
	'from idhazh.ledger import parquet',
	'from utilities import build_canary_day as canary',
	'source, root = map(Path, sys.argv[1:3])',
	'which = LedgerName.HOST_FINGERPRINT',
	'oldest = (date.fromisoformat(canary.DATE) - timedelta(days=40)).isoformat()',
	'days = [oldest, canary.YESTERDAY, canary.DATE]',
	'rows = ledger.load_days(source / "state", which, days, model=HostFingerprintRow)',
	'if len(sys.argv) == 3:',
	'    assert len(rows) == 15',
	'by_day = {}',
	'for row in rows:',
	'    by_day.setdefault(row.date, []).append(row)',
	'if len(sys.argv) > 3:',
	'    by_day = {rows[-1].date: [rows[-1], rows[-1]]}',
	'staged = root / "fixture-rows"',
	'for day, held in by_day.items():',
	'    folder = staged / which.value / day.replace("-", "/")',
	'    folder.mkdir(parents=True)',
	'    with (folder / "fixture.csv").open("w", encoding="utf-8", newline="") as handle:',
	'        writer = csv.DictWriter(handle, fieldnames=list(HostFingerprintRow.model_fields), lineterminator="\\n")',
	'        writer.writeheader()',
	'        writer.writerows(row.model_dump(mode="json") for row in held)',
	'if len(sys.argv) > 3:',
	'    try:',
	'        canary.file_fixture_rows(root / "state", staged)',
	'    except ValueError as error:',
	'        assert "a second time" in str(error)',
	'        assert not ledger.list_raw_files(root / "state", which)',
	'        print(json.dumps({"duplicate_refused": True}))',
	'    else:',
	'        raise AssertionError("a duplicate staged record was accepted")',
	'    sys.exit(0)',
	'filed = canary.file_fixture_rows(root / "state", staged)',
	'files = ledger.list_raw_files(root / "state", which)',
	'raw = []',
	'units = {}',
	'for file in files:',
	'    identity = file.envelope.identity',
	'    assert identity.producer == "telemetry.silicon" and identity.attempt == 1',
	'    held = parquet.read(file.path.read_bytes())[1]',
	'    assert len(held) == 1',
	'    record = held[0]',
	'    assert (identity.run_id, identity.job, identity.shard) == (record["run_id"], record["job"], record["shard"])',
	'    units[file.envelope.unit_id] = units.get(file.envelope.unit_id, 0) + 1',
	'    raw.extend(held)',
	'assert filed[which] == 15 and len(raw) == 16',
	'assert sorted(units.values()) == [1] * 14 + [2]',
	'halves = [row for row in raw if row["date"] == canary.DATE and row["run_id"] == canary.DATE + "-2" and row["job"] == "work" and row["shard"] == 0]',
	'assert len(halves) == 2',
	'assert any(row["cpu_model"] is not None and row["job_seconds"] is None for row in halves)',
	'assert any(row["cpu_model"] == "INTEL(R) XEON(R) PLATINUM 8573C" and row["fingerprint"] == "c81d9e0a1b2c3d4e" and row["job_seconds"] == 900 for row in halves)',
	'probe = next(row for row in halves if row["job_seconds"] is None)',
	'completion = next(row for row in halves if row["job_seconds"] == 900)',
	'clocks = {"model_load_ms": 2470.828, "job_seconds": 900, "server_prompt_tokens": 1700, "server_prompt_seconds": 73.72}',
	'assert all(probe[name] is None and completion[name] == value for name, value in clocks.items())',
	'assert {name: value for name, value in completion.items() if name not in clocks} == {name: value for name, value in probe.items() if name not in clocks}',
	'settled = ledger.load_days(root / "state", which, days, model=HostFingerprintRow)',
	'assert len(settled) == 15',
	'expected_siblings = {("plan", 0), ("work", 0), ("work", 1), ("assemble", 0)}',
	'assert {(row.job, row.shard) for row in settled if row.date == canary.DATE and row.run_id == canary.DATE + "-2"} == expected_siblings',
	'assert sorted(row.to_json() for row in settled) == sorted(row.to_json() for row in rows)',
	'canary.pack_fixture_ledgers(root / "state", Path.cwd())',
	'packed = ledger.load_days(root / "state", which, days, model=HostFingerprintRow)',
	'assert len(packed) == 15 and not ledger.list_raw_files(root / "state", which)',
	'assert sorted(row.to_json() for row in packed) == sorted(row.to_json() for row in rows)',
	'merged = [row for row in packed if row.date == canary.DATE and row.run_id == canary.DATE + "-2" and row.job == "work" and row.shard == 0]',
	'assert len(merged) == 1',
	'print(json.dumps({"from": oldest, "through": canary.DATE, "logical": len(packed), "raw_records": len(raw), "merged": merged[0].model_dump(mode="json")}))'
].join('\n');

test('16 native records settle to 15 jobs and Hardware keeps both halves of work shard zero', async () => {
	const root = test.info().outputPath('host-halves');
	const proof: {
		from: string; through: string; logical: number; raw_records: number; merged: Row
	} = JSON.parse(python(['-c', FILE_HOSTS, canary, root]).trim().split('\n').at(-1)!);
	expect([proof.raw_records, proof.logical]).toEqual([16, 15]);
	expect(proof.merged).toMatchObject({
		cpu_model: 'INTEL(R) XEON(R) PLATINUM 8573C', fingerprint: 'c81d9e0a1b2c3d4e',
		flags: expect.stringContaining('avx512f'), job_seconds: 900,
		model_load_ms: 2470.828, server_prompt_tokens: 1700, server_prompt_seconds: 73.72
	});
	const answer = await sliceFromDisk(path.join(root, 'state'), platformMixQuery.ledger, {
		columns: platformMixQuery.columns, from: proof.from, to: proof.through
	});
	expect(answer.state).toBe('ok');
	expect(answer.rows).toHaveLength(15);
	const sameJob = (row: Row) => row.date === proof.through &&
		row.run_id === `${proof.through}-2` && row.job === 'work' && row.shard === 0;
	const jobs = fleetJobs(answer.rows);
	const merged = jobs.filter((job) => job.date === proof.through &&
		job.runId === `${proof.through}-2` && job.job === 'work' && job.shard === 0);
	expect(merged).toHaveLength(1);
	expect(merged[0]).toMatchObject({
		cpuModel: proof.merged.cpu_model, fingerprint: proof.merged.fingerprint, seconds: 900
	});
	expect(merged[0].rate).toBeCloseTo(1700 / 73.72, 10);
	const knobs = consoleConfig();
	const keys = machineKeys(jobs.map((job) => ({ fingerprint: job.fingerprint, cpuModel: job.cpuModel })));
	const ramp = machineRamp(jobs.map((job) => ({
		machine: keys({ fingerprint: job.fingerprint, cpuModel: job.cpuModel }), rate: job.rate
	})), { stops: knobs.machine_colour_stops, floor: knobs.machine_colour_floor_share });
	const view = fleetView(jobs, {
		ramp, start: proof.from, end: proof.through, windowDays: 41,
		minRows: knobs.fleet_min_rows, topKinds: knobs.fleet_top_kinds, recording: true
	});
	expect(view.placements).toBe(15);
	const lines = view.lines.flat().filter((line) => line.runId === `${proof.through}-2` &&
		line.job === 'work' && line.shard === 0);
	expect(lines).toHaveLength(1);
	expect(lines[0]).toMatchObject({ seconds: 900 });
	expect(lines[0].machine).toContain('8573C');
	expect(lines[0].rate).toBeCloseTo(1700 / 73.72, 10);
	// An independent committed answer is read inside this test.
	const recorded: SliceResult = JSON.parse(readFileSync(path.join(
		REPO, 'tests', 'fixtures', 'console', 'machine', 'platformMixQuery.json'
	), 'utf8'));
	expect(recorded.rows.filter(sameJob)).toEqual(answer.rows.filter(sameJob));
});

test('native host half-writing does not excuse a duplicate staged fixture record', () => {
	const root = test.info().outputPath('duplicate-host');
	const proof: { duplicate_refused: boolean } = JSON.parse(
		python(['-c', FILE_HOSTS, canary, root, 'duplicate']).trim().split('\n').at(-1)!
	);
	expect(proof.duplicate_refused).toBe(true);
});
