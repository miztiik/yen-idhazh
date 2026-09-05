import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, readdirSync, rmSync, writeFileSync, mkdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { FRONTEND_GROUPS, groupedSpecs, groupForSpec } from '../test-groups.ts';
import { changedPaths, selectPaths, selectionForChange } from '../test-scope.ts';

const FRONTEND = resolve(dirname(fileURLToPath(import.meta.url)), '../..');

test('every frontend spec belongs to exactly one group', () => {
	const groups = groupedSpecs(join(FRONTEND, 'tests'));
	const assigned = Object.values(groups).flat();
	const discovered = readdirSync(join(FRONTEND, 'tests'), { recursive: true })
		.filter((name) => name.endsWith('.spec.ts')).map((name) => name.replaceAll('\\', '/')).sort();
	assert.deepEqual(assigned.toSorted(), discovered);
	assert.equal(new Set(assigned).size, discovered.length);
	assert.equal(groupForSpec('console-machine-data.spec.ts'), 'console');
	assert.equal(groupForSpec('frame.spec.ts'), 'logic');
});

test('a new unowned spec fails the inventory instead of disappearing', () => {
	const directory = mkdtempSync(join(tmpdir(), 'idhazh-groups-'));
	try {
		writeFileSync(join(directory, 'new-feature.spec.ts'), '');
		assert.throws(() => groupedSpecs(directory), /No test group owns/);
	} finally {
		rmSync(directory, { recursive: true, force: true });
	}
});

test('nested specs are included in the inventory and require an owner', () => {
	const directory = mkdtempSync(join(tmpdir(), 'idhazh-nested-groups-'));
	try {
		mkdirSync(join(directory, 'nested'));
		writeFileSync(join(directory, 'nested', 'console-extra.spec.ts'), '');
		assert.deepEqual(groupedSpecs(directory).console, ['nested/console-extra.spec.ts']);
		writeFileSync(join(directory, 'nested', 'new-feature.spec.ts'), '');
		assert.throws(() => groupedSpecs(directory), /No test group owns nested\/new-feature/);
	} finally { rmSync(directory, { recursive: true, force: true }); }
});

test('shared styles, layouts and dependencies include console coverage', () => {
	for (const path of [
		'frontend/src/styles/tokens.css', 'frontend/src/routes/+layout.svelte',
		'frontend/package.json', 'frontend/package-lock.json', 'frontend/tests/support/day-loader.ts'
	]) {
		assert.deepEqual(selectPaths([path]).groups, [...FRONTEND_GROUPS], path);
	}
});

test('unknown inputs and backend subpackages fail toward full coverage', () => {
	for (const path of ['new-area/module.ts', 'backend/idhazh/render/write.py', '.github/workflows/ci.yml']) {
		assert.deepEqual(selectPaths([path]).groups, ['backend', ...FRONTEND_GROUPS], path);
		assert.equal(selectPaths([path]).backendFiles, null);
	}
});

test('documentation alone starts no code suite and cannot hide a mixed edit', () => {
	assert.deepEqual(selectPaths(['docs/reference/measurements.md', 'TODO/a-plan.md']).groups, []);
	const mixed = selectPaths(['docs/a.md', 'frontend/src/routes/console/+page.svelte']);
	assert.deepEqual(mixed.groups, ['logic', 'console', 'publishing']);
	assert.equal(mixed.reasons.length, 2);
});

test('specific backend modules select existing module and integration tests', () => {
	const selection = selectPaths(['backend/idhazh/discover.py']);
	assert.deepEqual(selection.groups, ['backend']);
	assert.deepEqual(selection.backendFiles, ['backend/tests/test_discover.py', 'backend/tests/test_pipeline.py']);
	assert.deepEqual(selectPaths(['backend/tests/test_ledger.py']).backendFiles, ['backend/tests/test_ledger.py']);
	assert.ok(selectPaths(['backend/idhazh/extract.py']).backendFiles.includes('backend/tests/test_evals.py'));
});

test('contract and config changes include both languages and drift checks', () => {
	for (const path of ['config/appearance.json', 'schemas/article.schema.json', 'backend/idhazh/contracts/article.py']) {
		const selection = selectPaths([path]);
		assert.deepEqual(selection.groups, ['backend', ...FRONTEND_GROUPS]);
		assert.equal(selection.contracts, true);
	}
});

test('changed paths include commits, staged, unstaged, untracked and both rename sides', () => {
	const root = mkdtempSync(join(tmpdir(), 'idhazh-changes-'));
	const git = (...args) => execFileSync('git', ['-C', root, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', ...args], { encoding: 'utf8' });
	try {
		git('init', '--quiet');
		for (const name of ['seed', 'old-name', 'unstaged']) writeFileSync(join(root, name), 'original\n');
		git('add', 'seed', 'old-name', 'unstaged');
		git('commit', '--quiet', '-m', 'seed');
		const base = git('rev-parse', 'HEAD').trim();
		writeFileSync(join(root, 'seed'), 'committed\n');
		git('add', 'seed');
		git('commit', '--quiet', '-m', 'change');
		git('mv', 'old-name', 'new-name');
		writeFileSync(join(root, 'unstaged'), 'dirty\n');
		mkdirSync(join(root, 'untracked'));
		writeFileSync(join(root, 'untracked', 'file'), 'new\n');
		assert.deepEqual(changedPaths(root, base), ['new-name', 'old-name', 'seed', 'unstaged', 'untracked/file']);
		assert.deepEqual(changedPaths(root, base, 'HEAD', false), ['seed']);
		assert.deepEqual(selectionForChange(root, 'missing-ref').groups, ['backend', ...FRONTEND_GROUPS]);
	} finally {
		rmSync(root, { recursive: true, force: true });
	}
});
