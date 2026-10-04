import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { existsSync, mkdtempSync, rmSync, writeFileSync, mkdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { CHART_VOCABULARY_PAGE, CONSOLE_MODEL_LABELS_PAGE } from '../doc-test-inputs.ts';
import { FRONTEND_GROUPS, groupedSpecs, groupForSpec } from '../test-groups.ts';
import { changedPaths, ciAnswer, selectPaths, selectionForChange } from '../test-scope.ts';

const FRONTEND = resolve(dirname(fileURLToPath(import.meta.url)), '../..');

test('named frontend specs map to their declared groups', () => {
	assert.equal(groupForSpec('console-machine-data.spec.ts'), 'console');
	for (const name of [
		'console-host-spans', 'console-machine-cards', 'console-machine-split', 'console-machine', 'tokens',
		'console-date-axis', 'console-compression-rows', 'console-model-work', 'console-readout-data'
	]) {
		assert.equal(groupForSpec(`${name}.spec.ts`), 'logic', name);
		assert.deepEqual(selectPaths([`frontend/tests/${name}.spec.ts`]).groups, ['logic'], name);
		assert.equal(ciAnswer([`frontend/tests/${name}.spec.ts`], true).browser, false, name);
	}
	assert.equal(groupForSpec('frame.spec.ts'), 'logic');
	assert.equal(groupForSpec('panel-captures.spec.ts'), 'panels');
	assert.equal(groupForSpec('panel-sufficiency.spec.ts'), 'panels');
	assert.equal(groupForSpec('new-feature.spec.ts'), undefined);
});

test('extracted console logic keeps source changes covered with browser consumers', () => {
	for (const path of [
		'frontend/src/lib/charts/run-history.ts', 'frontend/src/lib/charts/series.ts',
		'frontend/src/lib/server/model-work.ts', 'frontend/src/lib/charts/readout.ts',
		'frontend/src/lib/charts/machine.ts', 'frontend/src/lib/charts/stacked.ts'
	]) {
		assert.deepEqual(selectPaths([path]).groups, [...FRONTEND_GROUPS], path);
		assert.equal(ciAnswer([path], true).browser, true, path);
	}
	assert.equal(groupForSpec('console.spec.ts'), 'console');
	assert.equal(groupForSpec('console-readout.spec.ts'), 'console');
	assert.equal(groupForSpec('console-new-question.spec.ts'), 'console');
});

test('grouped specs follow only the explicit inventory', () => {
	const directory = mkdtempSync(join(tmpdir(), 'idhazh-groups-'));
	try {
		const expected = groupedSpecs(join(FRONTEND, 'tests'));
		for (const names of Object.values(expected)) {
			for (const filename of names) writeFileSync(join(directory, filename), '');
		}
		writeFileSync(join(directory, 'unlisted-feature.spec.ts'), '');
		assert.deepEqual(groupedSpecs(directory), expected);
	} finally {
		rmSync(directory, { recursive: true, force: true });
	}
});

test('a missing named spec fails explicitly', () => {
	const directory = mkdtempSync(join(tmpdir(), 'idhazh-groups-'));
	try {
		assert.throws(
			() => groupedSpecs(directory),
			/Declared test .* is missing; update scripts\/test-groups\.ts\./
		);
	} finally {
		rmSync(directory, { recursive: true, force: true });
	}
});

test('shared styles, layouts and dependencies include console coverage', () => {
	for (const path of [
		'frontend/src/styles/tokens.css', 'frontend/src/routes/+layout.svelte',
		'frontend/package.json', 'frontend/package-lock.json', 'frontend/tests/support/day-loader.ts'
	]) {
		assert.deepEqual(selectPaths([path]).groups, [...FRONTEND_GROUPS], path);
	}
});

test('data helpers select ledger logic and console consumers without unrelated frontend groups', () => {
	for (const path of [
		'frontend/src/lib/data/ledger.ts', 'frontend/src/lib/data/engine.ts',
		'frontend/src/lib/data/nested/query.ts', String.raw`frontend\src\lib\data\page-keeper.ts`
	]) {
		const selection = selectPaths([path]);
		assert.deepEqual(selection.groups, ['logic', 'console', 'panels', 'publishing'], path);
		assert.deepEqual(selection.backendFiles, []);
		assert.equal(selection.contracts, false);
		assert.equal(selection.tooling, false);
		assert.equal(selection.reasons[0].reason, 'ledger queries and console consumers');
		assert.deepEqual(ciAnswer([path], true), {
			browser: true, code: true, modelAbsent: false, console: false, panels: false, robots: false, validateAll: false
		});
	}
});

test('the model-absent build runs for asset dependencies, unknown inputs and every code merge', () => {
	for (const path of [
		'frontend/src/lib/assist/loader.ts', 'frontend/src/routes/archive/+page.svelte',
		'frontend/src/lib/server/payload.ts', 'frontend/src/routes/+layout.svelte',
		'frontend/scripts/copy-visuals.mjs', 'frontend/svelte.config.js',
		'frontend/static/assist/model.json', 'frontend/package.json', 'config/idhazh.json',
		'backend/idhazh/contracts/app_config.py', 'unknown-area/module.ts',
		'unresolved-change-base', 'full-ci-run'
	]) {
		assert.equal(ciAnswer([path], true).modelAbsent, true, path);
	}
	for (const path of [
		'docs/a.md', 'backend/idhazh/discover.py', 'backend/tests/test_discover.py',
		'frontend/tests/console-machine-data.spec.ts', 'frontend/src/routes/console/+page.svelte',
		'frontend/src/lib/charts/frame.ts', 'frontend/src/styles/tokens.css',
		'frontend/src/lib/data/ledger.ts'
	]) {
		assert.equal(ciAnswer([path], true).modelAbsent, false, path);
	}
	assert.equal(ciAnswer(['frontend/src/routes/console/+page.svelte', 'frontend/src/lib/assist/day.ts'], true).modelAbsent, true);
	assert.equal(ciAnswer(['full-ci-run'], false).modelAbsent, true);
	assert.equal(ciAnswer(['docs/a.md'], false).modelAbsent, false);
});

test('the second-interpreter robots job runs only when its tests can have moved', () => {
	for (const path of [
		'backend/idhazh/extract.py', 'backend/idhazh/sanitize.py', 'backend/tests/test_extract.py',
		'pyproject.toml', 'new-area/module.ts', 'full-ci-run', 'unresolved-change-base'
	]) {
		assert.equal(ciAnswer([path], true).robots, true, path);
	}
	for (const path of [
		'docs/a.md', 'frontend/src/routes/+page.svelte', 'backend/idhazh/ledger.py',
		'backend/tests/test_ledger.py'
	]) {
		assert.equal(ciAnswer([path], true).robots, false, path);
	}
});

test('the data mapping preserves broader mixed edits and the unknown-path fallback', () => {
	const data = 'frontend/src/lib/data/slice-reader.ts';
	assert.deepEqual(selectPaths([data, 'docs/a.md']).groups, ['logic', 'console', 'panels', 'publishing']);
	assert.deepEqual(selectPaths([data, 'frontend/src/routes/+layout.svelte']).groups, [...FRONTEND_GROUPS]);
	assert.deepEqual(selectPaths([data, 'new-area/module.ts']).groups, ['backend', ...FRONTEND_GROUPS]);
	assert.deepEqual(selectPaths(['frontend/src/lib/database/query.ts']).groups, [...FRONTEND_GROUPS]);
});

test('unknown inputs and backend contracts fail toward full coverage', () => {
	for (const path of ['new-area/module.ts', 'backend/idhazh/contracts/article.py', '.github/workflows/ci.yml']) {
		assert.deepEqual(selectPaths([path]).groups, ['backend', ...FRONTEND_GROUPS], path);
		assert.equal(selectPaths([path]).backendFiles, null);
	}
});

test('an unmapped backend module buys the whole backend suite and no browser', () => {
	for (const path of ['backend/idhazh/assemble.py', 'backend/idhazh/render/write.py']) {
		assert.deepEqual(selectPaths([path]).groups, ['backend'], path);
		assert.equal(selectPaths([path]).backendFiles, null, path);
		assert.equal(ciAnswer([path], true).browser, false, path);
	}
});

test('documentation alone starts no code suite and cannot hide a mixed edit', () => {
	assert.deepEqual(selectPaths(['docs/reference/pipeline-cost.md', 'TODO/a-plan.md']).groups, []);
	const mixed = selectPaths(['docs/a.md', 'frontend/src/routes/console/+page.svelte']);
	assert.deepEqual(mixed.groups, ['logic', 'console', 'panels', 'publishing']);
	assert.equal(mixed.reasons.length, 2);
});

test('a change carrying no code buys no code job, on a merge as well as a branch', () => {
	for (const isPr of [true, false]) {
		assert.equal(ciAnswer(['docs/reference/pipeline-cost.md', 'TODO/a-plan.md'], isPr).code, false);
		// Anything that is not documentation, including a path nobody classified.
		for (const set of [
			['docs/a.md', 'frontend/src/app.html'],
			['config/idhazh.json'],
			['new-area/module.ts'],
			['full-ci-run'],
			['unresolved-change-base']
		]) {
			assert.equal(ciAnswer(set, isPr).code, true, set.join(' '));
		}
	}
	// Documentation carries no shape a committed day is read through, so a merge
	// that changes only documentation no longer re-reads every day.
	assert.equal(ciAnswer(['docs/a.md'], false).validateAll, false);
	assert.equal(ciAnswer(['docs/a.md'], false).browser, false);
});

test('a document a test reads is that test input, not documentation', () => {
	const page = CONSOLE_MODEL_LABELS_PAGE;
	assert.ok(existsSync(join(FRONTEND, '..', page)), `${page} is gone, so the console spec that reads it cannot pass`);
	assert.deepEqual(selectPaths([page]).groups, ['console']);
	assert.equal(selectPaths([page]).reasons[0].reason, 'documentation a test reads');
	const answer = ciAnswer([page], true);
	assert.equal(answer.code, true);
	assert.equal(answer.browser, true);
	// On the branch, not after the merge: the spec that reads the page is the one
	// an edit to it can break.
	assert.equal(answer.console, true);
});

test('the chart vocabulary page buys the logic spec that reads it, and no browser', () => {
	const page = CHART_VOCABULARY_PAGE;
	assert.ok(existsSync(join(FRONTEND, '..', page)), `${page} is gone, so the spec that reads it cannot pass`);
	assert.deepEqual(selectPaths([page]).groups, ['logic']);
	assert.equal(selectPaths([page]).reasons[0].reason, 'documentation a test reads');
	const answer = ciAnswer([page], true);
	assert.equal(answer.code, true);
	assert.equal(answer.browser, false);
	assert.equal(answer.console, false);
});

test('specific backend modules select existing module and integration tests', () => {
	const selection = selectPaths(['backend/idhazh/discover.py']);
	assert.deepEqual(selection.groups, ['backend']);
	assert.deepEqual(selection.backendFiles, ['backend/tests/pipeline/', 'backend/tests/test_discover.py']);
	assert.deepEqual(selectPaths(['backend/tests/test_ledger.py']).backendFiles, ['backend/tests/test_ledger.py']);
	assert.ok(selectPaths(['backend/idhazh/extract.py']).backendFiles.includes('backend/tests/test_evals.py'));
});

test('a utility nothing else runs selects only its own test module', () => {
	const path = 'backend/utilities/doc_load.py';
	const selection = selectPaths([path]);
	assert.deepEqual(selection.groups, ['backend']);
	assert.deepEqual(selection.backendFiles, ['backend/tests/test_doc_load.py']);
	assert.deepEqual(ciAnswer([path], true), {
		browser: false, code: true, modelAbsent: false, console: false, panels: false, robots: false, validateAll: false
	});
	// A closed list, not a directory rule: the canary build runs this one.
	assert.equal(selectPaths(['backend/utilities/build_canary_day.py']).backendFiles, null);
});

test('a test module inside a package is selected like a flat one', () => {
	// The five biggest test modules became packages. A selector that only knew
	// the flat shape would answer "documentation only" for a change to one of
	// them and run nothing at all.
	const selection = selectPaths(['backend/tests/contracts/test_app_config.py']);
	assert.deepEqual(selection.groups, ['backend']);
	assert.deepEqual(selection.backendFiles, ['backend/tests/contracts/test_app_config.py']);
	assert.equal(selection.reasons[0].reason, 'changed backend test module');
});

test('contract and config changes include both languages and revalidate the archive', () => {
	for (const path of ['config/appearance.json', 'backend/idhazh/contracts/article.py']) {
		const selection = selectPaths([path]);
		assert.deepEqual(selection.groups, ['backend', ...FRONTEND_GROUPS]);
		assert.equal(selection.contracts, true);
	}
});

//: A change, and what the `scope` job has to buy for it on a pull request: the
//: browser half at all, the operator console's own specs inside it, and the
//: panel captures and gates. The backend rows are the trap the allow-list exists
//: to avoid - a module the canary day is built through, and a fixture the attack
//: text is read from, can move a published page without touching `frontend/`.
const PULL_REQUEST_SCOPE = [
	// The console's own files, the only thing that buys its specs before merge.
	['frontend/src/routes/console/+page.svelte', true, true, true],
	['frontend/src/lib/console/window.ts', true, true, true],
	['frontend/src/lib/components/ConsoleNav.svelte', true, true, true],
	['frontend/src/lib/server/console-shell.ts', true, true, true],
	// A console spec moves no panel's picture.
	['frontend/tests/console-voices-feeds.spec.ts', true, true, false],
	// The harness itself, which has to prove itself on every group it selects.
	['frontend/package.json', true, true, true],
	['frontend/package-lock.json', true, true, true],
	['frontend/scripts/test-groups.ts', true, true, true],
	['.github/workflows/ci.yml', true, true, true],
	// What every panel is drawn from, which buys the pictures but not the console.
	['frontend/tests/panel-captures.spec.ts', true, false, true],
	['frontend/tests/fixtures/panels/WitnessPanel.svelte', true, false, true],
	['frontend/tests/support/panel-gates.ts', true, false, true],
	['frontend/src/lib/components/Panel.svelte', true, false, true],
	['frontend/src/lib/components/ChartReadout.svelte', true, false, true],
	['frontend/src/lib/charts/d3/DateSeries.svelte', true, false, true],
	['frontend/src/lib/charts/engine.ts', true, false, true],
	['frontend/src/styles/tokens.css', true, false, true],
	['config/appearance.json', true, false, true],
	// Reaches a published page, but neither the console nor its pictures before merge.
	['frontend/src/lib/components/KpiCard.svelte', true, false, false],
	['frontend/src/lib/server/payload.ts', true, false, false],
	['frontend/src/app.html', true, false, false],
	['frontend/src/routes/+layout.svelte', true, false, false],
	['frontend/src/routes/[date]/+page.svelte', true, false, false],
	['frontend/src/lib/assist/loader.ts', true, false, false],
	['config/idhazh.json', true, false, false],
	['backend/idhazh/contracts/item_health.py', true, false, false],
	['backend/utilities/build_canary_day.py', true, false, false],
	['backend/idhazh/sanitize.py', true, false, false],
	['tests/fixtures/canaries/fake-system-delimiter.json', true, false, false],
	['unknown-area/module.ts', true, false, false],
	// Cannot reach a page at all.
	['frontend/tests/frame.spec.ts', false, false, false],
	['docs/reference/pipeline-cost.md', false, false, false],
	['backend/tests/test_discover.py', false, false, false],
	['backend/idhazh/discover.py', false, false, false],
	// Reaches a page only through the canary build; the merge push settles it.
	['backend/idhazh/render/write.py', false, false, false],
	['TODO/some-plan.md', false, false, false]
];

test('a pull request buys the console specs only for the console or the harness', () => {
	for (const [path, browser, console_] of PULL_REQUEST_SCOPE) {
		const answer = ciAnswer([path], true);
		assert.equal(answer.browser, browser, path);
		assert.equal(answer.console, console_, path);
	}
});

test('a pull request buys the panel pictures for the console, the harness, and what every panel is drawn from', () => {
	for (const [path, , , panels] of PULL_REQUEST_SCOPE) {
		assert.equal(ciAnswer([path], true).panels, panels, path);
	}
});

//: A change, and whether it can invalidate a day that is already committed. A
//: published day is frozen, so only the shape it is read through - or an edit to
//: the day itself - can, and everything else leaves an answer settled when the
//: day was written.
const REVALIDATES_THE_ARCHIVE = [
	'backend/idhazh/contracts/item_health.py',
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
	'docs/reference/pipeline-cost.md'
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
	for (const [path, browser, console_, panels] of PULL_REQUEST_SCOPE) {
		assert.ok(!console_ || browser, `${path} asks for the console with no job`);
		assert.ok(!panels || browser, `${path} asks for the panel pictures with no job`);
	}
});

test('a merge to main runs every group, which is what the deferral leans on', () => {
	// Not a path list: outside a pull request the caller passes this sentinel and
	// the selector answers with full coverage, so nothing deferred can reach a
	// reader without the console specs having run over it first.
	const merged = ciAnswer(['full-ci-run'], false);
	assert.equal(merged.browser, true);
	assert.equal(merged.console, true);
	assert.equal(merged.panels, true);
	const unresolved = ciAnswer(['unresolved-change-base'], true);
	assert.equal(unresolved.browser, true);
	assert.equal(unresolved.console, true);
	assert.equal(unresolved.panels, true);
});

test('one reaching path in a mixed change still buys the browser suite', () => {
	const mixed = ciAnswer(
		['docs/reference/pipeline-cost.md', 'frontend/src/routes/+page.svelte'],
		true
	);
	assert.equal(mixed.browser, true);
	assert.equal(mixed.console, false);
	assert.equal(mixed.panels, false);
	const withConsole = ciAnswer(['docs/a.md', 'frontend/src/routes/console/+page.svelte'], true);
	assert.equal(withConsole.browser, true);
	assert.equal(withConsole.console, true);
	assert.equal(withConsole.panels, true);
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
