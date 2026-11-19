import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { existsSync, mkdtempSync, rmSync, writeFileSync, mkdirSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import test from 'node:test';
import { CHART_VOCABULARY_PAGE, CONSOLE_MODEL_LABELS_PAGE } from '../doc-test-inputs.ts';
import { FRONTEND_GROUPS, groupedSpecs, groupForSpec } from '../test-groups.ts';
import { changedPaths, ciAnswer, selectPaths, selectionForChange } from '../test-scope.ts';

const FRONTEND = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
test('pipeline APIs select the native gate and all named module dependants', () => {
	for (const path of ['services/serve-pipeline-apis/src/create-api-app.ts',
		'services/serve-pipeline-apis/src/supervise-http-child.ts',
		'services/feed-ingest-plan/scripts/serve-feed-apis.ts',
		'services/host-probes/src/api/serve-machine-apis.ts',
		'services/host-fingerprints/src/api/server.ts', 'services/host-probes/src/api/server.ts',
		'config/hono-server.json', '.github/workflows/feed-ingest-plan-test.yml']) {
		for (const separator of ['/', '\\']) {
			const selected = selectPaths([path.replaceAll('/', separator)]);
			assert.deepEqual(selected.groups, ['backend']);
			assert.match(selected.reasons[0].reason, /composition, planner, fingerprints and probes/);
			assert.equal(ciAnswer([path.replaceAll('/', separator)]).bun, true);

		}
	}
	assert.deepEqual(selectPaths(['packages/common-contracts/src/schemas/cloud-event.schema.ts']).groups,
		['backend', ...FRONTEND_GROUPS]);
});
test('Pipelines retained and native evidence joins representative groups without a panels matrix', () => {
	for (const separator of ['/', '\\']) {
		for (const path of [
			['frontend', 'src', 'lib', 'console', 'pipelines', 'StageTimings.svelte'],
			['frontend', 'tests', 'support', 'pipelines-ledgers.ts'],
			['frontend', 'tests', 'support', 'retained-telemetry.ts']
		]) {
			assert.deepEqual(selectPaths([path.join(separator)]).groups, ['logic', 'console', 'publishing']);

		}
	}
	for (const name of ['native', 'nothings']) {
		assert.equal(groupForSpec(`console-pipelines-${name}.spec.ts`), 'logic');
	}
	for (const name of ['lifecycle', 'reserved', 'components', 'sufficiency',
		'retained-failure', 'retained-compression', 'retained-item-cost', 'retained-window',
		'cold', 'days', 'timeline-page', 'window-page']) {
		assert.equal(groupForSpec(`console-pipelines-${name}.spec.ts`), 'console');
	}
	assert.equal(FRONTEND_GROUPS.includes('panels'), false);
});
test('Summaries modules and native private fixtures select console consumers without narrowing shared inputs', () => {
	for (const path of ['frontend/src/lib/console/model/Cards.svelte',
		'frontend/src/lib/console/model/model-change.ts', 'frontend/tests/support/model-route.ts']) {
		const selected = selectPaths([path]);
		assert.deepEqual(selected.groups, ['logic', 'console', 'publishing']);
	}
	assert.deepEqual(selectPaths(['frontend/src/lib/components/Sparkline.svelte']).groups, [...FRONTEND_GROUPS]);
	assert.equal(groupForSpec('frontend/tests/console-model-nothings.spec.ts'), 'logic');
	assert.equal(groupForSpec('frontend/tests/console-model-builder.spec.ts'), 'console');
	assert.equal(groupForSpec('frontend/tests/console-model-ledgers.spec.ts'), 'console');
	assert.equal(groupForSpec('frontend/tests/console-model-reductions.spec.ts'), 'logic');
	assert.equal(groupForSpec('frontend/tests/console-model-instruments.spec.ts'), 'logic');
	assert.equal(groupForSpec('frontend/tests/console-model-window.spec.ts'), undefined);
});
function tmpdir() {
	const path = resolve(FRONTEND, '../backend/var/checks/scope-tests');
	mkdirSync(path, { recursive: true });
	return path;
}

test('the browser config keeps the local inventory and offline safety dependency', () => {
	const configUrl = pathToFileURL(join(FRONTEND, 'playwright.config.ts')).href;
	const source = `import config from ${JSON.stringify(configUrl)};
		console.log(JSON.stringify(config.projects.map(({ name, testMatch, dependencies = [] }) =>
			({ name, testMatch, dependencies }))));`;
	const projects = JSON.parse(execFileSync(process.execPath, ['--input-type=module', '-e', source], {
		cwd: FRONTEND, encoding: 'utf8'
	}));
	const inventory = groupedSpecs(join(FRONTEND, 'tests'));
	assert.deepEqual(projects, FRONTEND_GROUPS.filter((group) => group !== 'logic').map((name) => ({
		name,
		testMatch: inventory[name].map((filename) => `**/${filename}`),
		dependencies: ['reader', 'console'].includes(name) ? ['offline'] : []
	})));
});

test('Judgement evidence stays in the real integration tier', () => {
	const inventory = groupedSpecs(join(FRONTEND, 'tests'));
	assert.ok(inventory.logic.includes('judgement-evidence.spec.ts'));
	assert.deepEqual(selectPaths(['frontend/tests/judgement-evidence.spec.ts']).groups, ['logic']);
});

test('a window helper edit selects all its console consumers under either path convention', () => {
	for (const name of ['controls', 'readout', 'server-panels']) {
		for (const separator of ['/', '\\']) {
			const path = ['frontend', 'tests', 'support', 'console-window', `${name}.ts`].join(separator);
			const selection = selectPaths([path]);
			assert.deepEqual(selection.groups, ['logic', 'console', 'publishing'], path);
			assert.equal(selection.reasons[0].reason, 'shared window controls and focused route window consumers', path);

		}
	}
});

test('query foundation checks are registered in their real execution tiers', () => {
	const inventory = groupedSpecs(join(FRONTEND, 'tests'));
	for (const [group, names] of [['logic', [
		'console-canary-host-halves', 'console-drawn-cells', 'console-panel-queries',
		'console-waiting', 'recorded-slices'
	]]]) {
		for (const name of names) {
			assert.ok(inventory[group].includes(`${name}.spec.ts`), name);
			for (const separator of ['/', '\\']) {
				const path = ['frontend', 'tests', `${name}.spec.ts`].join(separator);
				assert.deepEqual(selectPaths([path]).groups, [group], path);
			}
		}
	}
});

test('named frontend specs map to their declared groups', () => {
	assert.equal(groupForSpec('console-machine-data.spec.ts'), 'logic');
	for (const name of [
		'console-host-spans', 'console-machine-split', 'console-machine', 'tokens',
		'console-date-axis', 'console-model-work', 'console-readout-data'
	]) {
		assert.equal(groupForSpec(`${name}.spec.ts`), 'logic', name);
		assert.deepEqual(selectPaths([`frontend/tests/${name}.spec.ts`]).groups, ['logic'], name);
	}
	assert.equal(groupForSpec('frame.spec.ts'), 'logic');
	assert.equal(groupForSpec('panel-captures.spec.ts'), undefined);
	assert.equal(groupForSpec('panel-sufficiency.spec.ts'), undefined);
	for (const retired of ['console-machine-cards', 'console-disk-reads', 'processor-lost']) {
		assert.equal(groupForSpec(`${retired}.spec.ts`), undefined, retired);
	}
	assert.equal(groupForSpec('new-feature.spec.ts'), undefined);
});

test('extracted console logic keeps source changes covered with browser consumers', () => {
	for (const path of [
		'frontend/src/lib/charts/run-history.ts', 'frontend/src/lib/charts/series.ts',
		'frontend/src/lib/server/model-work.ts', 'frontend/src/lib/charts/readout.ts',
		'frontend/src/lib/charts/machine.ts', 'frontend/src/lib/charts/stack-types.ts'
	]) {
		assert.deepEqual(selectPaths([path]).groups, [...FRONTEND_GROUPS], path);
	}
	assert.equal(groupForSpec('console.spec.ts'), 'logic');
	assert.equal(groupForSpec('console-data-explorer-still.spec.ts'), 'console');
	assert.equal(groupForSpec('console-new-question.spec.ts'), undefined);
	assert.equal(groupForSpec('console-built-page.spec.ts'), undefined);
});

test('Voices panel inputs keep narrow route consumers and unknown-path broad coverage', () => {
	for (const name of ['feeds-failed.ts', 'FeedTiles.svelte', 'why-chosen.ts', 'WatchlistPanel.svelte']) {
		for (const separator of ['/', '\\']) {
			const path = ['frontend', 'src', 'lib', 'console', 'voices', name].join(separator);
			assert.deepEqual(selectPaths([path]).groups, ['logic', 'console', 'publishing'], path);

		}
	}
	assert.deepEqual(selectPaths(['frontend/src/lib/console/voices/feeds-failed.ts', 'unknown-area/module.ts']).groups,
		['backend', ...FRONTEND_GROUPS]);
	assert.deepEqual(selectPaths(['frontend/src/lib/console/unmapped/panel.ts']).groups, [...FRONTEND_GROUPS]);
	assert.deepEqual(groupedSpecs(join(FRONTEND, 'tests')).console,
		['console-data-explorer-still.spec.ts', 'console-machine-journey.spec.ts', 'console-model-builder.spec.ts',
			'console-model-ledgers.spec.ts',
			'console-pipelines-cold.spec.ts', 'console-pipelines-components.spec.ts', 'console-pipelines-days.spec.ts',
			'console-pipelines-lifecycle.spec.ts', 'console-pipelines-reserved.spec.ts',
			'console-pipelines-retained-compression.spec.ts', 'console-pipelines-retained-failure.spec.ts',
			'console-pipelines-retained-item-cost.spec.ts',
			'console-pipelines-retained-window.spec.ts', 'console-pipelines-sufficiency.spec.ts',
			'console-pipelines-timeline-page.spec.ts', 'console-pipelines-window-page.spec.ts',
			'console-telemetry-heal.spec.ts', 'console-voices-journey.spec.ts']);
});

test('Hardware native readers and representative boundaries remain in the closed inventory', () => {
	assert.equal(groupForSpec('console-machine-journey.spec.ts'), 'console');
	assert.deepEqual(selectPaths(['frontend/tests/console-machine-journey.spec.ts']).groups, ['console']);

	for (const name of ['records.ts', 'MachineCharts.svelte', 'RecordFrame.svelte']) {
		for (const separator of ['/', '\\']) {
			const path = ['frontend', 'src', 'lib', 'console', 'machine', name].join(separator);
			assert.deepEqual(selectPaths([path]).groups, ['logic', 'console', 'publishing'], path);

		}
	}
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
		assert.deepEqual(selection.groups, ['logic', 'console', 'publishing'], path);
		assert.deepEqual(selection.backendFiles, []);
		assert.equal(selection.contracts, false);
		assert.equal(selection.tooling, false);
		assert.equal(selection.reasons[0].reason, 'ledger queries and console consumers');
	}
});

test('each route-owned config selects local console and contract checks', () => {
	for (const route of ['pipelines', 'model', 'machine', 'voices', 'judgement', 'data-explorer']) {
		for (const path of [
			`config/console/${route}.json`, `config\\console\\${route}.json`
		]) {
			const selection = selectPaths([path]);
			assert.deepEqual(selection.groups, ['logic', 'console', 'publishing'], path);
			assert.equal(selection.contracts, true, path);
			assert.equal(selection.tooling, false, path);
			assert.equal(selection.reasons[0].reason, 'route-owned console config and panel checks', path);



		}
	}
	assert.deepEqual(selectPaths(['docs/a.md', 'config/console/machine.json']).groups, ['logic', 'console', 'publishing']);
	assert.deepEqual(selectPaths(['config/console/machine.json', 'frontend/src/routes/+layout.svelte']).groups, [...FRONTEND_GROUPS]);
	assert.deepEqual(selectPaths(['config/console/machine.json', 'unknown-area/module.ts']).groups, ['backend', ...FRONTEND_GROUPS]);
	assert.deepEqual(selectPaths(['config/console-other/machine.json']).groups, ['backend', ...FRONTEND_GROUPS]);
});

test('route-owned expectations remain console inputs after extraction', () => {
	for (const route of ['pipelines', 'model', 'machine', 'voices', 'judgement', 'data-explorer', 'index']) {
		for (const file of [`frontend/tests/support/console-expect/console-band/${route}.ts`]) {
			for (const path of [file, file.replaceAll('/', '\\')]) {
				assert.deepEqual(selectPaths([path]).groups, ['logic', 'console', 'publishing'], path);

			}
		}
	}

});

test('the shared panel frame reaches all local frontend groups', () => {
	assert.deepEqual(selectPaths(['frontend/src/lib/components/Panel.svelte']).groups, [...FRONTEND_GROUPS]);
});

test('the data mapping preserves broader mixed edits and the unknown-path fallback', () => {
	const data = 'frontend/src/lib/data/slice-reader.ts';
	assert.deepEqual(selectPaths([data, 'docs/a.md']).groups, ['logic', 'console', 'publishing']);
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

test('an unmapped backend module selects the whole backend suite locally', () => {
	for (const path of ['backend/idhazh/assemble.py', 'backend/idhazh/render/write.py']) {
		assert.deepEqual(selectPaths([path]).groups, ['backend'], path);
		assert.equal(selectPaths([path]).backendFiles, null, path);
	}
});

test('documentation alone starts no code suite and cannot hide a mixed edit', () => {
	assert.deepEqual(selectPaths(['docs/reference/pipeline-cost.md', 'TODO/a-plan.md']).groups, []);
	const mixed = selectPaths(['docs/a.md', 'frontend/src/routes/console/+page.svelte']);
	assert.deepEqual(mixed.groups, ['logic', 'console', 'publishing']);
	assert.equal(mixed.reasons.length, 2);
});

test('CI selects only applicable extra suites on top of the checks for any code change', () => {
	const cases = [
		[['docs/a.md', 'TODO/a-plan.md'], false, false, false, false],
		[['backend/idhazh/discover.py'], true, false, false, false],
		[['frontend/src/routes/+page.svelte'], true, false, true, false],
		[['frontend/scripts/build-canary.mjs'], true, false, true, true],
		[['docs/a.md', 'packages/common-contracts/src/config.ts'], true, true, true, false],
		[['config/hono-server.json'], true, true, false, false],
		[['tests/fixtures/feed-ingest-plan/entry-points/response.json'], true, true, true, false],
		[['backend/idhazh/contracts/article.py'], true, true, true, false],
		[['.github/workflows/ci.yml'], true, true, true, true],
		[['full-ci-run'], true, true, true, true],
		[['unresolved-change-base'], true, true, true, true]
	];
	for (const [paths, code, bun, logic, tooling] of cases) {
		assert.deepEqual(ciAnswer(paths), { code, bun, logic, tooling }, paths.join(', '));
	}
});

test('the protected model-label document selects its logic contract', () => {
	const page = CONSOLE_MODEL_LABELS_PAGE;
	assert.ok(existsSync(join(FRONTEND, '..', page)));
	assert.deepEqual(selectPaths([page]).groups, ['logic']);
	assert.equal(selectPaths([page]).reasons[0].reason, 'documentation a test reads');
	const answer = ciAnswer([page]);
	assert.equal(answer.code, true);
	assert.equal(answer.logic, true);
});

test('the chart vocabulary page selects the logic spec that reads it', () => {
	const page = CHART_VOCABULARY_PAGE;
	assert.ok(existsSync(join(FRONTEND, '..', page)), `${page} is gone, so the spec that reads it cannot pass`);
	assert.deepEqual(selectPaths([page]).groups, ['logic']);
	assert.equal(selectPaths([page]).reasons[0].reason, 'documentation a test reads');
	const answer = ciAnswer([page]);
	assert.equal(answer.code, true);
	assert.equal(answer.logic, true);
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

test('contract and config changes include both languages', () => {
	for (const path of ['config/appearance.json', 'backend/idhazh/contracts/article.py']) {
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
