import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { existsSync, mkdtempSync, rmSync, writeFileSync, mkdirSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import test from 'node:test';
import { CHART_VOCABULARY_PAGE, CONSOLE_MODEL_LABELS_PAGE } from '../doc-test-inputs.ts';
import { FRONTEND_GROUPS, groupedSpecs, groupForSpec } from '../test-groups.ts';
import { options, selection } from '../run-checks.ts';
import { changedPaths, ciAnswer, selectPaths, selectionForChange } from '../test-scope.ts';

const FRONTEND = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
test('Pipelines retained and native evidence joins representative groups without a panels matrix', () => {
	for (const separator of ['/', '\\']) {
		for (const path of [
			['frontend', 'src', 'lib', 'console', 'pipelines', 'StageTimings.svelte'],
			['frontend', 'tests', 'support', 'pipelines-ledgers.ts'],
			['frontend', 'tests', 'support', 'retained-telemetry.ts']
		]) {
			assert.deepEqual(selectPaths([path.join(separator)]).groups, ['logic', 'console', 'publishing']);
			assert.equal(ciAnswer([path.join(separator)], true).console, true);
		}
	}
	for (const name of ['native', 'nothings']) {
		assert.equal(groupForSpec(`console-pipelines-${name}.spec.ts`), 'logic');
	}
	for (const name of ['lifecycle', 'reserved', 'components', 'sufficiency',
		'retained-failure', 'retained-failures', 'retained-compression', 'retained-item-cost', 'retained-window',
		'cold', 'days', 'timeline-page', 'window-page']) {
		assert.equal(groupForSpec(`console-pipelines-${name}.spec.ts`), 'console');
	}
	assert.equal(FRONTEND_GROUPS.includes('panels'), false);
});
test('isolated comparison inputs select their exact evidence consumers without browser builds', () => {
	for (const path of [
		'.github/workflows/rust-host-telemetry.yml',
		'config/host-telemetry-comparison.json',
		'backend/idhazh/contracts/host_evidence.py',
		'backend/idhazh/telemetry/host_evidence_inputs.py',
		'backend/idhazh/telemetry/host_evidence_comparison.py',
		'backend/idhazh/telemetry/host_evidence_artifacts.py',
		'backend/idhazh/telemetry/host_evidence_samples.py',
		'backend/utilities/host_telemetry_workload.py',
		'backend/utilities/host_telemetry_reference.py',
		'backend/utilities/host_telemetry_session.py',
		'backend/utilities/compare_host_telemetry.py'
	]) {
		const selected = selectPaths([path]);
		assert.deepEqual(selected.groups, ['backend']);
		assert.equal(selected.rust, true);
		assert.ok(selected.backendFiles.includes('backend/tests/test_compare_host_telemetry.py'));
		assert.ok(selected.backendFiles.includes('backend/tests/workflows/test_rust_host_telemetry_workflow.py'));
		assert.equal(ciAnswer([path], true).browser, false);
	}
	const cost = selectPaths(['backend/utilities/host_telemetry_measurement.py']);
	assert.equal(cost.rust, true);
	assert.deepEqual(cost.groups, ['backend']);
	const shared = selectPaths(['config/host-telemetry-experiment.json']);
	assert.ok(shared.backendFiles.includes('backend/tests/test_host_fingerprint_migration.py'));
});

test('Summaries modules and native private fixtures select console consumers without narrowing shared inputs', () => {
	for (const path of ['frontend/src/lib/console/model/Cards.svelte',
		'frontend/src/lib/console/model/model-change.ts', 'frontend/tests/support/model-route.ts']) {
		const selected = selectPaths([path]);
		assert.deepEqual(selected.groups, ['logic', 'console', 'publishing']);
		assert.equal(selected.rust, false);
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

function configuredBrowserProjects(skipConsole, args = []) {
	const configUrl = pathToFileURL(join(FRONTEND, 'playwright.config.ts')).href;
	const source = `import config from ${JSON.stringify(configUrl)};
		console.log(JSON.stringify(config.projects.map(({ name, testMatch, dependencies = [] }) =>
			({ name, testMatch, dependencies }))));`;
	return JSON.parse(execFileSync(process.execPath, ['--input-type=module', '-e', source, '--', ...args], {
		cwd: FRONTEND, encoding: 'utf8',
		env: { ...process.env, CI: 'false', PREVIEW_PORT: '4173', PLAYWRIGHT_WORKERS: '1',
			SKIP_CONSOLE_SUITE: skipConsole }
	}));
}

test('the actual browser config defers only console and preserves its offline safety dependency', () => {
	const inventory = groupedSpecs(join(FRONTEND, 'tests'));
	const expected = FRONTEND_GROUPS.filter((group) => group !== 'logic').map((name) => ({
		name,
		testMatch: inventory[name].map((filename) => `**/${filename}`),
		dependencies: ['reader', 'console'].includes(name) ? ['offline'] : []
	}));
	for (const value of ['', 'false', '0']) {
		assert.deepEqual(configuredBrowserProjects(value), expected, value);
	}
	assert.deepEqual(configuredBrowserProjects('true'), expected.filter(({ name }) => name !== 'console'));
	for (const [path, isPr] of [
		['frontend/src/styles/tokens.css', true],
		['frontend/src/routes/console/+page.svelte', true],
		['full-ci-run', false]
	]) {
		const answer = ciAnswer([path], isPr);
		assert.equal(answer.browser, true);
		assert.deepEqual(configuredBrowserProjects(String(!answer.console)),
			expected.filter(({ name }) => name !== 'console' || answer.console), path);
	}
});

test('test:changed explicit groups stay authoritative even with a CI console deferral in the environment', () => {
	const selected = selection(FRONTEND, options(['--group', 'console']));
	assert.deepEqual(selected.groups, ['console']);
	for (const args of [
		selected.groups.map((group) => `--project=${group}`),
		['--project', 'console']
	]) {
		const projects = configuredBrowserProjects('true', args);
		assert.ok(projects.some(({ name }) => name === 'console'));
		assert.deepEqual(projects.find(({ name }) => name === 'console').dependencies, ['offline']);
	}
});

test('historical host dry-run paths select bounded Python fixtures without native preparation', () => {
	for (const path of [
		'backend/idhazh/contracts/host_migration.py',
		'backend/idhazh/telemetry/host_history_files.py',
		'backend/idhazh/telemetry/host_history_migration.py',
		'backend/idhazh/telemetry/host_history_bundle.py',
		'backend/idhazh/telemetry/host_history_paths.py',
		'backend/utilities/migrate_host_fingerprints.py',
		'config/host-history-migration.json',
		'tests/fixtures/host-events/history-migration.json'
	]) {
		const selected = selectPaths([path]);
		assert.deepEqual(selected.groups, ['backend']);
		assert.deepEqual(selected.backendFiles, [
			'backend/tests/contracts/test_host_migration.py',
			'backend/tests/test_host_fingerprint_migration.py'
		]);
		assert.equal(selected.rust, false);
		assert.equal(selected.contracts, false);
	}
	const config = selectPaths(['config/host-telemetry-experiment.json']);
	assert.ok(config.backendFiles.includes('backend/tests/test_host_fingerprint_migration.py'));
});

test('native Rust and its actual file fixture select focused checks without browser preparation', () => {
	for (const path of ['backend/rust/host-telemetry/src/codec/parquet.rs',
		'backend/rust/host-telemetry/rust-toolchain.toml', 'backend/rust/host-telemetry/Cargo.lock',
		'tests/fixtures/host-events/file-parity.json', 'backend/tests/contracts/test_rust_host_file_parity.py',
		'backend/rust/host-telemetry/src/ledger/store.rs', 'backend/tests/test_rust_host_store_parity.py',
		'backend/rust/host-telemetry/src/probe_inputs/hierarchy.rs', 'backend/tests/contracts/test_host_event_rust_parity.py',
		'backend/rust/host-telemetry/src/monitor/session.rs', 'backend/tests/test_host_event_resource_parity.py']) {
		const selected = selectPaths([path]);
		assert.deepEqual(selected.groups, ['backend']);
		assert.equal(selected.rust, true);
		assert.equal(selected.contracts, false);
		assert.deepEqual(selected.backendFiles, path === 'tests/fixtures/host-events/file-parity.json'
			? ['backend/tests/contracts/test_rust_host_file_parity.py']
			: ['backend/tests/contracts/test_host_event_rust_parity.py', 'backend/tests/contracts/test_rust_host_file_parity.py', 'backend/tests/test_rust_host_receipts.py',
				'backend/tests/test_rust_host_store_parity.py', 'backend/tests/test_host_event_resource_parity.py',
				'backend/tests/test_compare_host_telemetry.py', 'backend/tests/workflows/test_rust_host_telemetry_workflow.py'].sort());
		assert.equal(ciAnswer([path], true).browser, false);
		assert.equal(ciAnswer([path], true).modelAbsent, false);
		assert.equal(ciAnswer([path], true).robots, false);
	}
	const storage = selectPaths(['tests/fixtures/host-events/storage-parity.json']);
	assert.equal(storage.rust, true);
	assert.deepEqual(storage.groups, ['backend']);
	assert.deepEqual(storage.backendFiles, ['backend/tests/test_rust_host_store_parity.py']);
	const receipts = selectPaths(['tests/fixtures/host-events/publication-parity.json']);
	assert.equal(receipts.rust, true);
	assert.deepEqual(receipts.groups, ['backend']);
	assert.deepEqual(receipts.backendFiles, ['backend/tests/test_rust_host_receipts.py']);
	const resources = selectPaths(['tests/fixtures/host-events/resource-windows.json']);
	assert.equal(resources.rust, true);
	assert.deepEqual(resources.groups, ['backend']);
	assert.deepEqual(resources.backendFiles, ['backend/tests/test_host_event_resource_parity.py',
		'backend/tests/test_host_readings.py', 'backend/tests/test_memory_sampler.py']);
	for (const path of ['tests/fixtures/host-events/probe-clock.json',
		'tests/fixtures/runtime/2026-08-29-3-shard-0.server-head.txt',
		'tests/fixtures/runtime/2026-08-26-5-shard-0.prom']) {
		const producer = selectPaths([path]);
		assert.equal(producer.rust, true);
		assert.deepEqual(producer.groups, ['backend']);
		assert.deepEqual(producer.backendFiles, ['backend/tests/contracts/test_host_event_rust_parity.py']);
	}
});

test('isolated host contracts and verification have finite consumers; unknowns stay broad', () => {
	for (const path of ['backend/idhazh/contracts/host_events.py',
		'backend/idhazh/contracts/host_output.py', 'backend/idhazh/telemetry/host_output_verify.py',
		'backend/idhazh/telemetry/host_parquet_admission.py', 'config/host-telemetry-experiment.json']) {
		const selected = selectPaths([path]);
		assert.deepEqual(selected.groups, ['backend']);
		assert.equal(selected.rust, true);
		assert.equal(selected.contracts, false);
		assert.ok(selected.backendFiles.includes('backend/tests/contracts/test_rust_host_file_parity.py'));
	}
	const transport = selectPaths(['backend/idhazh/telemetry/host_event_files.py']);
	assert.equal(transport.rust, false);
	assert.deepEqual(transport.backendFiles, ['backend/tests/test_host_event_files.py']);
	for (const path of ['backend/rust/new-crate/src/lib.rs', 'config/host-unknown.json',
		'backend/idhazh/contracts/host-unknown.py', 'tests/fixtures/host-events/unknown.json']) {
		const selected = selectPaths([path]);
		assert.deepEqual(selected.groups, ['backend', ...FRONTEND_GROUPS]);
		assert.equal(selected.backendFiles, null);
		assert.equal(selected.rust, true);
	}
});

test('Judgement evidence stays in the real integration tier', () => {
	const inventory = groupedSpecs(join(FRONTEND, 'tests'));
	assert.ok(inventory.logic.includes('judgement-evidence.spec.ts'));
	assert.deepEqual(selectPaths(['frontend/tests/judgement-evidence.spec.ts']).groups, ['logic']);
});

test('a window helper edit selects all its console consumers under either path convention', () => {
	for (const name of ['controls', 'readout', 'judgement-fixtures', 'server-panels']) {
		for (const separator of ['/', '\\']) {
			const path = ['frontend', 'tests', 'support', 'console-window', `${name}.ts`].join(separator);
			const selection = selectPaths([path]);
			assert.deepEqual(selection.groups, ['logic', 'console', 'publishing'], path);
			assert.equal(selection.reasons[0].reason, 'shared window controls and focused route window consumers', path);
			assert.equal(ciAnswer([path], true).console, true, path);
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
		'console-host-spans', 'console-machine-cards', 'console-machine-split', 'console-machine', 'tokens',
		'console-date-axis', 'console-compression-rows', 'console-model-work', 'console-readout-data'
	]) {
		assert.equal(groupForSpec(`${name}.spec.ts`), 'logic', name);
		assert.deepEqual(selectPaths([`frontend/tests/${name}.spec.ts`]).groups, ['logic'], name);
		assert.equal(ciAnswer([`frontend/tests/${name}.spec.ts`], true).browser, false, name);
	}
	assert.equal(groupForSpec('frame.spec.ts'), 'logic');
	assert.equal(groupForSpec('panel-captures.spec.ts'), undefined);
	assert.equal(groupForSpec('panel-sufficiency.spec.ts'), undefined);
	assert.equal(groupForSpec('new-feature.spec.ts'), undefined);
});

test('extracted console logic keeps source changes covered with browser consumers', () => {
	for (const path of [
		'frontend/src/lib/charts/run-history.ts', 'frontend/src/lib/charts/series.ts',
		'frontend/src/lib/server/model-work.ts', 'frontend/src/lib/charts/readout.ts',
		'frontend/src/lib/charts/machine.ts', 'frontend/src/lib/charts/stack-types.ts'
	]) {
		assert.deepEqual(selectPaths([path]).groups, [...FRONTEND_GROUPS], path);
		assert.equal(ciAnswer([path], true).browser, true, path);
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
			assert.equal(ciAnswer([path], true).console, true, path);
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
			'console-pipelines-retained-failures.spec.ts', 'console-pipelines-retained-item-cost.spec.ts',
			'console-pipelines-retained-window.spec.ts', 'console-pipelines-sufficiency.spec.ts',
			'console-pipelines-timeline-page.spec.ts', 'console-pipelines-window-page.spec.ts',
			'console-telemetry-heal.spec.ts', 'console-voices-journey.spec.ts']);
});

test('Hardware native readers and representative boundaries remain in the closed inventory', () => {
	assert.equal(groupForSpec('console-machine-journey.spec.ts'), 'console');
	assert.deepEqual(selectPaths(['frontend/tests/console-machine-journey.spec.ts']).groups, ['console']);
	assert.equal(ciAnswer(['frontend/tests/console-machine-journey.spec.ts'], true).console, true);
	for (const name of ['records.ts', 'MachineCharts.svelte', 'RecordFrame.svelte']) {
		for (const separator of ['/', '\\']) {
			const path = ['frontend', 'src', 'lib', 'console', 'machine', name].join(separator);
			assert.deepEqual(selectPaths([path]).groups, ['logic', 'console', 'publishing'], path);
			assert.equal(ciAnswer([path], true).console, true, path);
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
		assert.deepEqual(ciAnswer([path], true), {
			browser: true, code: true, modelAbsent: false, console: false, robots: false, validateAll: false
		});
	}
});

test('each route-owned config buys console checks on a pull request', () => {
	for (const route of ['pipelines', 'model', 'machine', 'voices', 'judgement', 'data-explorer']) {
		for (const path of [
			`config/console/${route}.json`, `config\\console\\${route}.json`
		]) {
			const selection = selectPaths([path]);
			assert.deepEqual(selection.groups, ['logic', 'console', 'publishing'], path);
			assert.equal(selection.contracts, true, path);
			assert.equal(selection.tooling, false, path);
			assert.equal(selection.reasons[0].reason, 'route-owned console config and panel checks', path);
			const answer = ciAnswer([path], true);
			assert.equal(answer.browser, true, path);
			assert.equal(answer.console, true, path);
			assert.equal(answer.validateAll, true, path);
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
				assert.equal(ciAnswer([path], true).console, true, path);
			}
		}
	}
	assert.equal(ciAnswer(['frontend/tests/support/console-expect-other/machine.ts'], true).console, false);
	assert.equal(ciAnswer(['frontend/tests/support/panel-gates.ts'], true).console, false);
});

test('the shared panel frame uses the representative browser selection', () => {
	for (const path of [
		'frontend/src/lib/components/Panel.svelte', String.raw`frontend\src\lib\components\Panel.svelte`
	]) {
		assert.deepEqual(selectPaths([path]).groups, [...FRONTEND_GROUPS], path);
		assert.equal(ciAnswer([path], true).console, true, path);
	}
	for (const path of [
		'frontend/src/lib/components/PanelGroup.svelte', 'frontend/src/lib/components/ChartReadout.svelte'
	]) {
		assert.equal(ciAnswer([path], true).console, false, path);
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
	assert.deepEqual(mixed.groups, ['logic', 'console', 'publishing']);
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

test('the protected model-label document selects its logic contract and no browser journey', () => {
	const page = CONSOLE_MODEL_LABELS_PAGE;
	assert.ok(existsSync(join(FRONTEND, '..', page)));
	assert.deepEqual(selectPaths([page]).groups, ['logic']);
	assert.equal(selectPaths([page]).reasons[0].reason, 'documentation a test reads');
	const answer = ciAnswer([page], true);
	assert.equal(answer.code, true);
	assert.equal(answer.browser, false);
	assert.equal(answer.console, false);
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
		browser: false, code: true, modelAbsent: false, console: false, robots: false, validateAll: false
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
//: browser half at all and the representative operator-console journey. The
//: backend rows are the trap the allow-list exists
//: to avoid - a module the canary day is built through, and a fixture the attack
//: text is read from, can move a published page without touching `frontend/`.
const PULL_REQUEST_SCOPE = [
	// The console's own files, the only thing that buys its specs before merge.
	['frontend/src/routes/console/+page.svelte', true, true],
	['frontend/src/lib/console/window.ts', true, true],
	['frontend/src/lib/components/ConsoleNav.svelte', true, true],
	['frontend/src/lib/server/console-shell.ts', true, true],
	// A deterministic console rule needs no browser.
	['frontend/tests/console-voices-feeds.spec.ts', false, false],
	// The harness itself, which has to prove itself on every group it selects.
	['frontend/package.json', true, true],
	['frontend/package-lock.json', true, true],
	['frontend/scripts/test-groups.ts', true, true],
	['.github/workflows/ci.yml', true, true],
	// The shared panel frame reaches every console route (known defect 45).
	['frontend/src/lib/components/Panel.svelte', true, true],
	['config/console/machine.json', true, true],
	// Deterministic panel rules and fixtures stay below the browser.
	['frontend/tests/fixtures/panels/WitnessPanel.svelte', false, false],
	['frontend/tests/support/panel-gates.ts', true, false],
	['frontend/src/lib/components/ChartReadout.svelte', true, false],
	['frontend/src/lib/charts/d3/DateSeries.svelte', true, false],
	['frontend/src/lib/charts/readout.ts', true, false],
	['frontend/src/styles/tokens.css', true, false],
	['config/appearance.json', true, false],
	// Reaches a published page, but not the console before merge.
	['frontend/src/lib/components/KpiCard.svelte', true, false],
	['frontend/src/lib/server/payload.ts', true, false],
	['frontend/src/app.html', true, false],
	['frontend/src/routes/+layout.svelte', true, false],
	['frontend/src/routes/[date]/+page.svelte', true, false],
	['frontend/src/lib/assist/loader.ts', true, false],
	['config/idhazh.json', true, false],
	['backend/idhazh/contracts/item_health.py', true, false],
	['backend/utilities/build_canary_day.py', true, false],
	['backend/idhazh/sanitize.py', true, false],
	['tests/fixtures/canaries/fake-system-delimiter.json', true, false],
	['unknown-area/module.ts', true, false],
	// Cannot reach a page at all.
	['frontend/tests/frame.spec.ts', false, false],
	['docs/reference/pipeline-cost.md', false, false],
	['backend/tests/test_discover.py', false, false],
	['backend/idhazh/discover.py', false, false],
	// Reaches a page only through the canary build; the merge push settles it.
	['backend/idhazh/render/write.py', false, false],
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
	'frontend/src/lib/charts/readout.ts',
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
		['docs/reference/pipeline-cost.md', 'frontend/src/routes/+page.svelte'],
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
