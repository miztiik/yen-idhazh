import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, readdirSync, rmSync, writeFileSync, mkdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { FRONTEND_GROUPS, groupedSpecs, groupForSpec } from '../test-groups.ts';
import { changedPaths, ciAnswer, selectPaths, selectionForChange } from '../test-scope.ts';

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

//: A change, and what the `scope` job has to buy for it on a pull request: the
//: browser half at all, and the operator console's own specs inside it. The
//: backend rows are the trap the allow-list exists to avoid - a module the
//: canary day is built through, and a fixture the attack text is read from, can
//: move a published page without touching `frontend/`.
const PULL_REQUEST_SCOPE = [
	// The console's own files, the only thing that buys its specs before merge.
	['frontend/src/routes/console/+page.svelte', true, true],
	['frontend/src/lib/console/window.ts', true, true],
	['frontend/src/lib/components/ConsoleNav.svelte', true, true],
	['frontend/src/lib/server/console-shell.ts', true, true],
	['frontend/tests/console-feeds.spec.ts', true, true],
	// The harness itself, which has to prove itself on every group it selects.
	['frontend/package.json', true, true],
	['frontend/package-lock.json', true, true],
	['frontend/scripts/test-groups.ts', true, true],
	['.github/workflows/ci.yml', true, true],
	// Reaches a published page, but not the console before merge.
	['frontend/src/lib/charts/engine.ts', true, false],
	['frontend/src/lib/components/KpiCard.svelte', true, false],
	['frontend/src/lib/server/payload.ts', true, false],
	['frontend/src/app.html', true, false],
	['frontend/src/styles/tokens.css', true, false],
	['frontend/src/routes/+layout.svelte', true, false],
	['frontend/src/routes/[date]/+page.svelte', true, false],
	['frontend/src/lib/assist/loader.ts', true, false],
	['config/idhazh.json', true, false],
	['backend/idhazh/contracts/item_health.py', true, false],
	['backend/utilities/build_canary_day.py', true, false],
	['backend/idhazh/render/write.py', true, false],
	['backend/idhazh/sanitize.py', true, false],
	['tests/fixtures/canaries/fake-system-delimiter.json', true, false],
	['unknown-area/module.ts', true, false],
	// Cannot reach a page at all.
	['frontend/tests/frame.spec.ts', false, false],
	['docs/reference/measurements.md', false, false],
	['backend/tests/test_discover.py', false, false],
	['backend/idhazh/discover.py', false, false],
	['TODO/some-plan.md', false, false]
];

test('a pull request buys the console specs only for the console or the harness', () => {
	for (const [path, browser, console_] of PULL_REQUEST_SCOPE) {
		const answer = ciAnswer([path], true);
		assert.equal(answer.browser, browser, path);
		assert.equal(answer.console, console_, path);
	}
});

//: A change, and whether it can invalidate a day that is already committed. A
//: published day is frozen, so only the shape it is read through - or an edit to
//: the day itself - can, and everything else leaves an answer settled when the
//: day was written.
const REVALIDATES_THE_ARCHIVE = [
	'backend/idhazh/contracts/item_health.py',
	'schemas/digest-day.schema.json',
	'config/idhazh.json',
	'pyproject.toml',
	'frontend/package.json',
	'frontend/scripts/test-groups.ts',
	'.github/workflows/ci.yml',
	'frontend/public/digest/2026/08/26/digest.json',
	'frontend/public/telemetry/2026-08.csv',
	'frontend/public/assist/index/2026-08.json'
];

const LEAVES_THE_ARCHIVE_ALONE = [
	'frontend/src/routes/console/+page.svelte',
	'frontend/src/lib/charts/engine.ts',
	'frontend/src/styles/tokens.css',
	'backend/idhazh/discover.py',
	'backend/tests/test_discover.py',
	'docs/reference/measurements.md'
];

test('only a change that can invalidate a committed day re-reads every day', () => {
	for (const path of REVALIDATES_THE_ARCHIVE) {
		assert.equal(ciAnswer([path], true).validateAll, true, path);
	}
	for (const path of LEAVES_THE_ARCHIVE_ALONE) {
		assert.equal(ciAnswer([path], true).validateAll, false, path);
	}
	// One path in a mixed change is enough, and a merge always re-reads.
	assert.equal(ciAnswer(['docs/a.md', 'config/idhazh.json'], true).validateAll, true);
	assert.equal(ciAnswer(['full-ci-run'], false).validateAll, true);
	assert.equal(ciAnswer(['unresolved-change-base'], true).validateAll, true);
});

test('the console half is never bought without the browser half', () => {
	for (const [path, browser, console_] of PULL_REQUEST_SCOPE) {
		assert.ok(!console_ || browser, `${path} asks for the console with no job`);
	}
});

test('a merge to main runs every group, which is what the deferral leans on', () => {
	// Not a path list: outside a pull request the caller passes this sentinel and
	// the selector answers with full coverage, so nothing deferred can reach a
	// reader without the console specs having run over it first.
	const merged = ciAnswer(['full-ci-run'], false);
	assert.equal(merged.browser, true);
	assert.equal(merged.console, true);
	const unresolved = ciAnswer(['unresolved-change-base'], true);
	assert.equal(unresolved.browser, true);
	assert.equal(unresolved.console, true);
});

test('one reaching path in a mixed change still buys the browser suite', () => {
	const mixed = ciAnswer(
		['docs/reference/measurements.md', 'frontend/src/routes/+page.svelte'],
		true
	);
	assert.equal(mixed.browser, true);
	assert.equal(mixed.console, false);
	const withConsole = ciAnswer(['docs/a.md', 'frontend/src/routes/console/+page.svelte'], true);
	assert.equal(withConsole.browser, true);
	assert.equal(withConsole.console, true);
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
