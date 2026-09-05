import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';
import { writeRecord } from '../build-state.ts';
import { command, options, pythonModulesFor, readResult, recordRun, selection, waitForResult } from '../run-checks.ts';
import { selectPaths } from '../test-scope.ts';

test('a logic-only change neither probes backend packages nor selects pytest tooling', () => {
	const selected = selectPaths(['frontend/tests/frame.spec.ts']);
	assert.equal(selected.tooling, false);
	assert.deepEqual(pythonModulesFor(selected), []);
});

test('the tooling self-tests are selected only for their own inputs', () => {
	assert.equal(selectPaths(['frontend/src/routes/console/+page.svelte']).tooling, false);
	for (const path of ['frontend/scripts/run-checks.ts', 'frontend/playwright.config.ts', '.github/workflows/ci.yml']) {
		const selected = selectPaths([path]);
		assert.equal(selected.tooling, true);
		assert.ok(pythonModulesFor(selected).includes('pytest'));
	}
});

test('ambiguous group/spec selection is rejected before preparation', () => {
	assert.throws(() => options(['--group', 'console', '--spec', 'archive.spec.ts']), /Choose --group or --spec/);
	assert.deepEqual(options(['--spec', 'frame.spec.ts', '--spec', 'archive.spec.ts']).specs,
		['frame.spec.ts', 'archive.spec.ts']);
});

test('whole-day checks cannot be mixed with canary or other spec selections', () => {
	assert.throws(() => options(['--spec', 'whole-day.spec.ts']), /alone with --mode real/);
	assert.throws(() => options(['--mode', 'real', '--spec', 'whole-day.spec.ts', '--spec', 'reading-page.spec.ts']), /alone with --mode real/);
	assert.deepEqual(options(['--mode', 'real', '--spec', 'whole-day.spec.ts']).specs, ['whole-day.spec.ts']);
});

test('an explicit all selection includes schema and tooling checks', () => {
	const directory = mkdtempSync(join(tmpdir(), 'idhazh-explicit-all-'));
	try {
		const selected = selection(directory, options(['--group', 'all']));
		assert.equal(selected.contracts, true);
		assert.equal(selected.tooling, true);
		assert.equal(selected.backendFiles, null);
		assert.ok(selected.groups.includes('backend'));
	} finally { rmSync(directory, { recursive: true, force: true }); }
});

test('an identical completed check is reused instead of launching its command twice', async () => {
	const directory = mkdtempSync(join(tmpdir(), 'idhazh-check-record-'));
	try {
		const output = join(directory, 'executions');
		const work = async () => [await command('fixture process', process.execPath,
			['-e', 'require("node:fs").appendFileSync(process.argv[1], "run\\n")', output], directory, process.env)];
		const first = await recordRun(directory, 'same-inputs', work);
		const second = await recordRun(directory, 'same-inputs', work);
		assert.deepEqual(second, first);
		assert.equal(readFileSync(output, 'utf8'), 'run\n');
		await recordRun(directory, 'changed-inputs', work);
		assert.equal(readFileSync(output, 'utf8'), 'run\nrun\n');
	} finally {
		rmSync(directory, { recursive: true, force: true });
	}
});

test('a waiter receives the existing result, including a failure', async () => {
	const directory = mkdtempSync(join(tmpdir(), 'idhazh-check-wait-'));
	try {
		const file = join(directory, 'in-progress.json');
		const waiting = waitForResult(file, 'in-progress', process.pid);
		const result = await recordRun(directory, 'in-progress', async () => [
			await command('failing fixture', process.execPath, ['-e', 'process.exitCode = 7'], directory, process.env)
		]);
		assert.equal(result.exitCode, 7);
		assert.deepEqual(await waiting, result);
		assert.equal(readResult(file, 'other-inputs'), undefined);
		assert.equal(readResult(file, 'in-progress').exitCode, 7);
	} finally {
		rmSync(directory, { recursive: true, force: true });
	}
});

test('invalid records cannot be read as successful tests', () => {
	const directory = mkdtempSync(join(tmpdir(), 'idhazh-check-invalid-'));
	try {
		const file = join(directory, 'invalid.json');
		writeRecord(file, { id: 'invalid', exitCode: 0 });
		assert.equal(readResult(file, 'invalid'), undefined);
		writeRecord(file, { id: 'invalid', attempt: 'one', exitCode: 0, started: 1, finished: 2,
			steps: [{ name: 'failed check', exitCode: 1, milliseconds: 1 }] });
		assert.equal(readResult(file, 'invalid'), undefined);
		for (const tests of [undefined, {}, { passed: 0, failed: 0, skipped: 4 }]) {
			writeRecord(file, { id: 'invalid', attempt: 'one', exitCode: 0, started: 1, finished: 2,
				steps: [{ name: 'pytest', exitCode: 0, milliseconds: 1, tests }] });
			assert.equal(readResult(file, 'invalid'), undefined);
		}
	} finally {
		rmSync(directory, { recursive: true, force: true });
	}
});

test('fresh repeats a finished run but a queued duplicate reuses its result', async () => {
	const directory = mkdtempSync(join(tmpdir(), 'idhazh-check-fresh-'));
	try {
		const work = async () => [{ name: 'fixture', exitCode: 0, milliseconds: 0 }];
		const first = await recordRun(directory, 'inputs', work);
		const repeated = await recordRun(directory, 'inputs', work, { fresh: true, requested: first.finished + 1 });
		const joined = await recordRun(directory, 'inputs', work, { fresh: true, requested: first.started });
		assert.deepEqual(joined, repeated);
	} finally {
		rmSync(directory, { recursive: true, force: true });
	}
});

test('joining a fresh attempt cannot return an older successful result', async () => {
	const directory = mkdtempSync(join(tmpdir(), 'idhazh-check-attempt-'));
	try {
		const old = await recordRun(directory, 'inputs', async () => [{ name: 'old', exitCode: 0, milliseconds: 1 }]);
		const file = join(directory, 'inputs.json');
		const waiting = waitForResult(file, 'inputs', process.pid, 'new-attempt');
		const current = { ...old, attempt: 'new-attempt', exitCode: 3, steps: [{ name: 'current', exitCode: 3, milliseconds: 1 }] };
		writeRecord(file, current);
		assert.equal((await waiting).exitCode, 3);
	} finally {
		rmSync(directory, { recursive: true, force: true });
	}
});

test('an empty execution cannot certify a change', async () => {
	const directory = mkdtempSync(join(tmpdir(), 'idhazh-check-empty-'));
	try {
		assert.equal((await recordRun(directory, 'inputs', async () => [])).exitCode, 1);
	} finally {
		rmSync(directory, { recursive: true, force: true });
	}
});

test('a queued caller cannot reuse a result whose build was invalidated', async () => {
	const directory = mkdtempSync(join(tmpdir(), 'idhazh-check-invalid-build-'));
	try {
		const first = await recordRun(directory, 'inputs', async () => [{ name: 'old build', exitCode: 0, milliseconds: 1 }]);
		const current = await recordRun(directory, 'inputs', async () => [{ name: 'current build', exitCode: 0, milliseconds: 1 }], {
			fresh: true, requested: first.started, reusable: () => false
		});
		assert.notEqual(current.attempt, first.attempt);
		assert.equal(current.steps[0].name, 'current build');
	} finally {
		rmSync(directory, { recursive: true, force: true });
	}
});

test('run records name the tested source and selection', async () => {
	const directory = mkdtempSync(join(tmpdir(), 'idhazh-check-selection-'));
	try {
		const selection = { source: 'fixture-fingerprint', groups: ['logic'], backendFiles: [], specs: ['frame.spec.ts'], mode: 'canary' };
		await recordRun(directory, 'inputs', async () => [{ name: 'fixture', exitCode: 0, milliseconds: 1 }], { selection });
		assert.deepEqual(readResult(join(directory, 'inputs.json'), 'inputs').selection, selection);
	} finally { rmSync(directory, { recursive: true, force: true }); }
});
