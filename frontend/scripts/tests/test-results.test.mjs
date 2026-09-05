import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { existsSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';
import { REPO } from '../build-state.ts';
import { playwrightCounts, pytestCounts, requireExecuted } from '../test-results.ts';

test('no test, all-skipped, failed and malformed reports cannot pass', () => {
	assert.throws(() => requireExecuted({}), /invalid counts/);
	assert.throws(() => requireExecuted({ passed: 1, failed: 0 }), /invalid counts/);
	assert.throws(() => requireExecuted(null), /invalid counts/);
	assert.throws(() => requireExecuted({ passed: 0, failed: 0, skipped: 0 }), /No tests executed/);
	assert.throws(() => requireExecuted({ passed: 0, failed: 0, skipped: 8 }), /No tests executed/);
	assert.throws(() => requireExecuted({ passed: 1, failed: 1, skipped: 0 }), /tests failed/);
	assert.throws(() => requireExecuted({ passed: NaN, failed: 0, skipped: 0 }), /invalid counts/);
});

test('a Playwright report preserves skips and rejects collection errors', () => {
	const directory = mkdtempSync(join(tmpdir(), 'idhazh-playwright-report-'));
	try {
		const file = join(directory, 'report.json');
		const report = { stats: { expected: 5, unexpected: 0, flaky: 0, skipped: 2 }, errors: [] };
		writeFileSync(file, JSON.stringify(report));
		assert.deepEqual(playwrightCounts(file), { passed: 5, failed: 0, skipped: 2 });
		writeFileSync(file, JSON.stringify({ ...report, errors: [{ message: 'collection failed' }] }));
		assert.throws(() => playwrightCounts(file), /complete successful report/);
	} finally { rmSync(directory, { recursive: true, force: true }); }
});

test('real pytest collection output is not executed-test evidence', () => {
	const directory = mkdtempSync(join(tmpdir(), 'idhazh-pytest-report-'));
	const local = join(REPO, process.platform === 'win32' ? '.venv/Scripts/python.exe' : '.venv/bin/python');
	const python = process.env.IDHAZH_PYTHON || (existsSync(local) ? local : 'python');
	const env = { ...process.env };
	delete env.PYTEST_ADDOPTS;
	try {
		const file = join(directory, 'test_example.py');
		const report = join(directory, 'report.xml');
		writeFileSync(file, 'def test_example():\n    assert True\n');
		const args = ['-m', 'pytest', '-o', 'addopts=', '-q', '--junitxml', report, file];
		execFileSync(python, [...args, '--collect-only'], { cwd: directory, env, stdio: 'pipe' });
		assert.throws(() => pytestCounts(python, report, env), /No tests executed/);
		execFileSync(python, args, { cwd: directory, env, stdio: 'pipe' });
		assert.deepEqual(pytestCounts(python, report, env), { passed: 1, failed: 0, skipped: 0 });
	} finally { rmSync(directory, { recursive: true, force: true }); }
});
