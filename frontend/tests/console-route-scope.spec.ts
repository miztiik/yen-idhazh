/** Which named console files cross a route's ownership boundary? */
import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';
import { groupedSpecs } from '../scripts/test-groups';
import { BAND_UNREAD, type RouteId } from '../src/lib/console/band';

const FRONTEND = fileURLToPath(new URL('..', import.meta.url));
const CROSS_ROUTE_SPECS = [
	'console-axis', 'console-band', 'console-chart-lifetime', 'console-chart-pending',
	'console-chrome', 'console-frame', 'console-mark-parity', 'console-model-panels',
	'console-model-rule', 'console-nav', 'console-polarity', 'console-readout',
	'console-shell', 'console-title', 'console-voices', 'console-window', 'console'
] as const;

// Named inputs, not a walk: a new consumer must join this inventory.
const SOURCE_INPUTS: Readonly<Record<string, readonly string[]>> = {
	'': [
		'vite.config.ts', 'svelte.config.js', 'asset-base.js', 'playwright.config.ts',
		'playwright.logic.config.ts', 'playwright.whole-day.config.ts'
	],
	src: ['app.d.ts', 'query-engine-assets.d.ts', 'service-worker.ts'],
	'src/lib': [
		'archive-calendar.ts', 'bands.ts', 'day-shape.ts', 'feed-health.ts', 'format.ts',
		'links.ts', 'offline.generated.ts', 'offline.ts', 'readstate.ts', 'reveal.ts', 'theme.ts'
	],
	'src/lib/assist': [
		'day.ts', 'encoder.ts', 'index.ts', 'loader.ts', 'month.ts', 'search.ts', 'session.ts', 'weights.ts'
	],
	'src/lib/charts': [
		'chart-flow.ts', 'Chart.svelte', 'core.ts', 'cost.ts', 'day-slots.ts', 'engine.ts',
		'extraction-trend.ts', 'fleet.ts', 'frame.ts', 'glance.ts', 'indexed-runs.ts',
		'machine-cards.ts', 'machine-colour.ts', 'machine-name.ts', 'machine-split.ts',
		'machine.ts', 'rank.ts', 'readout.ts', 'run-history.ts', 'run-yield.ts', 'series.ts',
		'skeleton.ts', 'span-track.ts', 'sparkline.ts', 'stacked.ts', 'targetbar.ts',
		'telemetry-hold.ts', 'theme.ts', 'viewport.ts', 'waterfall.ts'
	],
	'src/lib/charts/d3': [
		'axis.ts', 'DateSeries.svelte', 'dateSeries.ts', 'Distribution.svelte', 'distribution.ts',
		'empty.ts', 'EmptyState.svelte', 'Flow.svelte', 'flow.ts', 'motion.ts', 'ordered-colour.ts',
		'overlapTimeline.ts', 'paired.ts', 'PairedScatter.svelte', 'pairedScatter.ts',
		'PartsOfOne.svelte', 'partsOfOne.ts', 'rankedList.ts', 'scale.ts', 'TileStrip.svelte', 'tileStrip.ts'
	],
	'src/lib/components': [
		'ArchiveSearch.svelte', 'BandDistance.svelte', 'ChartReadout.svelte', 'ChoiceTiles.svelte',
		'ConfidenceChip.svelte', 'ConsoleBand.svelte', 'ConsoleNav.svelte', 'DayNotice.svelte',
		'DigestItem.svelte', 'DigestList.svelte', 'EmptyDay.svelte', 'FailureList.svelte',
		'FailurePanels.svelte', 'FilterBar.svelte', 'FoundStories.svelte', 'ItemMeta.svelte',
		'ItemVisual.svelte', 'KpiCard.svelte', 'LeadingStories.svelte', 'LensChips.svelte',
		'MachineCard.svelte', 'MachineSplitGroup.svelte', 'MemoryBoard.svelte', 'MoreDays.svelte',
		'NotHere.svelte', 'Notice.svelte', 'Panel.svelte', 'PanelGroup.svelte', 'PayloadState.svelte',
		'RankedList.svelte', 'RateControl.svelte', 'ReadAloud.svelte', 'Reserved.svelte',
		'RunLengths.svelte', 'RunSquares.svelte', 'RunYield.svelte', 'SearchState.svelte',
		'ShapeSwitch.svelte', 'ShardBoard.svelte', 'SiteFooter.svelte', 'SiteHeader.svelte',
		'SourceCutRange.svelte', 'SourceLink.svelte', 'SourceMark.svelte', 'Sparkline.svelte',
		'StageTimings.svelte', 'StatusChip.svelte', 'SwapDots.svelte', 'TargetBar.svelte',
		'ThemeToggle.svelte', 'ThroughputTrend.svelte', 'TimeHistogram.svelte', 'Viewport.svelte',
		'WindowControl.svelte', 'WindowControlSource.svelte', 'WindowStatus.svelte'
	],
	'src/lib/console': [
		'applied-line.ts', 'band.ts', 'chrome.ts', 'completeness.ts', 'daily-figures.ts',
		'doubt-reasons.ts', 'eval-instruments.ts', 'extraction.ts', 'held-part-note.ts',
		'holdout.ts', 'item-cost.ts', 'merge-line.ts', 'model-cards.ts', 'prompt-cache-subtitle.ts',
		'recording.ts', 'RecordNotes.svelte', 'route-console.ts', 'run-square.ts',
		'settings-moved.ts', 'span-words.ts', 'strip.ts', 'verdict-split.ts', 'waiting.ts', 'window-slot.ts'
	],
	'src/lib/console/explorer': [
		'address.ts', 'answer.ts', 'AnswerTable.svelte', 'chart-roles.ts', 'column-groups.ts',
		'ColumnList.svelte', 'ColumnPicker.svelte', 'ColumnType.svelte', 'CopyAnswer.svelte',
		'days-read.ts', 'floating-list.ts', 'gaps.ts', 'HistoryList.svelte', 'keep.ts',
		'LedgerList.svelte', 'preset-span.ts', 'QueryEditor.svelte', 'QuestionStrip.svelte',
		'registry.ts', 'role-row.ts', 'RunStatus.svelte', 'shape.ts', 'ShapePanel.svelte',
		'status.ts', 'strip-fit.ts', 'type-colour.ts', 'type-family.ts', 'utc-instant.ts'
	],
	'src/lib/console/machine': [
		'article-cost.ts', 'ArticleCostPanel.svelte', 'context-cost.ts', 'ContextCostPanel.svelte',
		'CounterfactualCostPanel.svelte', 'disk-reads.ts', 'DiskReadsPanel.svelte', 'FleetDots.svelte',
		'MachineCardsPanel.svelte', 'MachineSplitPanel.svelte', 'memory-held.ts',
		'MemoryBoardPanel.svelte', 'MemoryHeldPanel.svelte', 'PlatformMixPanel.svelte',
		'processor-lost.ts', 'ProcessorLostPanel.svelte', 'prompt-reuse.ts', 'PromptReusePanel.svelte',
		'ReadAgainstWrittenPanel.svelte', 'refused-runs.ts', 'run-axis.ts', 'ShardBoardPanel.svelte',
		'TailTrendPanel.svelte', 'TwoClocksPanel.svelte'
	],
	'src/lib/data': [
		'ask-reader.ts', 'compact-index.ts', 'engine.ts', 'fetched-bytes.ts', 'ledger-columns.ts',
		'ledger-reach.ts', 'ledger.ts', 'page-keeper.ts', 'raw-day-index.ts', 'site-window.ts',
		'slice-query.ts', 'slice-reader.ts', 'slice-shapes.ts', 'slice.ts', 'statement.ts'
	],
	'src/lib/icons': ['generated.ts', 'Icon.svelte'],
	'src/lib/payload': ['desks.ts', 'drawing.ts', 'lenses.ts', 'project.ts', 'types.ts'],
	'src/lib/server': [
		'chart-days.ts', 'chart-render.ts', 'config.ts', 'cuts-by-run.ts', 'host-fingerprint.ts',
		'ledger-disk.ts', 'ledger-rows.ts', 'machine-counters.ts', 'model-work.ts', 'payload.ts',
		'publication.ts', 'recorded-line.ts', 'run-days.ts', 'run-timeline.ts', 'server-counter-notes.ts',
		'similarity-holdout.ts', 'similarity-ledger.ts', 'source-retiring.ts', 'stage-timing-days.ts', 'window-day.ts'
	],
	'src/lib/visual': ['bar.ts', 'width.ts'],
	'src/routes': ['+error.svelte', '+layout.svelte', '+layout.ts', '+page.server.ts', '+page.svelte'],
	'src/routes/archive': ['+page.server.ts', '+page.svelte'],
	'src/routes/console': [
		'+layout.svelte', '+layout.ts', '+page.server.ts', '+page.svelte',
		'RunHealthPanel.svelte', 'RunTimelinePanel.svelte'
	],
	'src/routes/console/data-explorer': ['+page.svelte', '+page.ts'],
	'src/routes/console/judgement': [
		'+page.server.ts', '+page.svelte', 'HoldoutMargin.svelte', 'JudgeAgreement.svelte',
		'MergedStoriesPanel.svelte', 'MergeLinePlot.svelte', 'RecordGates.svelte', 'VerdictSplit.svelte'
	],
	'src/routes/console/machine': ['+page.server.ts', '+page.svelte'],
	'src/routes/console/model': ['+page.server.ts', '+page.svelte'],
	'src/routes/console/voices': ['+page.server.ts', '+page.svelte'],
	'src/routes/[date]': ['+page.svelte', '+page.ts'],
	'src/routes/[date]/[vertical]': ['+page.svelte', '+page.ts'],
	scripts: [
		'build-canary.mjs', 'build-frame-css.mjs', 'build-icons.mjs', 'build-state.ts',
		'build-worker-switch.mjs', 'bundle-gate.mjs', 'canary-inventory.mjs', 'copy-visuals.mjs',
		'doc-test-inputs.ts', 'duckdb-addon.ts', 'payload-ceilings.mjs', 'published-ledgers.mjs',
		'query-engine-assets.ts', 'raw-listed-through.mjs', 'run-checks.ts', 'setup-duckdb.ts',
		'staged-publication.mjs', 'test-groups.ts', 'test-results.ts', 'test-scope.ts', 'verified-preview.ts'
	],
	'scripts/tests': [
		'build-state.test.mjs', 'canary-inventory.test.mjs', 'duckdb-addon.test.mjs',
		'query-engine-assets.test.mjs', 'run-checks.test.mjs', 'test-results.test.mjs', 'test-scope.test.mjs'
	],
	'tests/support': [
		'backend-python.ts', 'browser.ts', 'canary-config.ts', 'charts-ready.ts', 'check-addons.ts',
		'consecutive-days.ts', 'console-panels.ts', 'console-widths.ts', 'day-drawings.ts',
		'day-loader.ts', 'day-ready.ts', 'explorer-answer.ts', 'in-zone.ts', 'judgement-route.ts',
		'ledger-lifecycle.ts', 'machine-record-state.ts', 'machine-rows.ts', 'model-swap.ts',
		'month-shard.ts', 'panel-gates.ts', 'panel-tab.ts', 'published-site.ts', 'published.ts',
		'range-host.ts', 'reduction-input.ts', 'served-telemetry.ts', 'server-render.ts', 'span-said.ts',
		'telemetry-row.ts', 'views.ts'
	],
	'tests/fixtures/panels': ['WitnessPanel.svelte']
};

const DEFINE_OWNERS = new Set(['vite.config.ts', 'src/app.d.ts', 'src/lib/console/route-console.ts']);

function namedRoutes(source: string): RouteId[] {
	return BAND_UNREAD.routes.filter(({ href }) => {
		const escaped = href.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
		return new RegExp('([\'"`])' + escaped + '\\1').test(source);
	}).map(({ id }) => id);
}

function routeScopeErrors(file: string, source: string): string[] {
	const path = file.replaceAll('\\', '/');
	const routes = namedRoutes(source);
	const errors: string[] = [];
	const owned = /^tests\/support\/(?:console-expect\/[^/]+|panel-drivers)\/([^/]+)\.ts$/.exec(path);
	if (owned) {
		const owner = owned[1];
		const foreign = routes.filter((route) => owner === 'index' || route !== owner);
		if (foreign.length) errors.push(`${path} names routes it does not own: ${foreign.join(', ')}`);
	} else if (/^tests\/[^/]+\.spec\.ts$/.test(path)) {
		const name = path.slice('tests/'.length, -'.spec.ts'.length);
		if ((CROSS_ROUTE_SPECS as readonly string[]).includes(name) && routes.length) {
			errors.push(`${path} is cross-route and names: ${routes.join(', ')}`);
		} else if (name !== 'console-machine-page' && routes.length >= 2) {
			errors.push(`${path} names more than one route: ${routes.join(', ')}`);
		}
	}
	return errors;
}

function defineScopeErrors(file: string, source: string): string[] {
	const path = file.replaceAll('\\', '/');
	const scripts = path.endsWith('.svelte')
		? [...source.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/g)].map((match) => match[1]).join('\n')
		: source;
	const tree = ts.createSourceFile(path, scripts, ts.ScriptTarget.Latest, true);
	const errors = new Set<string>();
	if (path.endsWith('.svelte') && !DEFINE_OWNERS.has(path)) {
		const scanner = ts.createScanner(ts.ScriptTarget.Latest, true, ts.LanguageVariant.Standard, source);
		for (let token = scanner.scan(); token !== ts.SyntaxKind.EndOfFileToken; token = scanner.scan()) {
			if (token === ts.SyntaxKind.Identifier && scanner.getTokenText() === '__CONSOLE__') {
				errors.add(`${path} names __CONSOLE__ outside its three owners`);
			}
		}
	}
	function imported(module: ts.Expression | undefined): void {
		if (!module || !ts.isStringLiteralLike(module)) return;
		if (!/(?:^|\/)route-console(?:\.[jt]s)?$/.test(module.text.split(/[?#]/)[0])) return;
		if (path !== 'src/lib/server/config.ts' && !path.startsWith('src/routes/console/')) {
			errors.add(`${path} imports route-console outside the config loader or console routes`);
		}
	}
	function visit(node: ts.Node): void {
		if (ts.isIdentifier(node) && node.text === '__CONSOLE__' && !DEFINE_OWNERS.has(path)) {
			errors.add(`${path} names __CONSOLE__ outside its three owners`);
		}
		if (ts.isImportDeclaration(node) || ts.isExportDeclaration(node)) imported(node.moduleSpecifier);
		if (ts.isImportEqualsDeclaration(node) && ts.isExternalModuleReference(node.moduleReference)) {
			imported(node.moduleReference.expression);
		}
		if (ts.isImportTypeNode(node) && ts.isLiteralTypeNode(node.argument)) imported(node.argument.literal);
		if (ts.isCallExpression(node) && (
			node.expression.kind === ts.SyntaxKind.ImportKeyword ||
			(ts.isIdentifier(node.expression) && node.expression.text === 'require')
		)) imported(node.arguments[0]);
		ts.forEachChild(node, visit);
	}
	visit(tree);
	return [...errors];
}

function supportFiles(): string[] {
	const routes = BAND_UNREAD.routes.map(({ id }) => id);
	return [
		...CROSS_ROUTE_SPECS.flatMap((name) => ['index', ...routes].map(
			(route) => `tests/support/console-expect/${name}/${route}.ts`
		)),
		...['index', ...routes].map((route) => `tests/support/panel-drivers/${route}.ts`)
	];
}

test('quoted href matching covers all six routes and counts distinct routes only', () => {
	expect(BAND_UNREAD.routes).toHaveLength(6);
	for (const { id, href } of BAND_UNREAD.routes) {
		for (const quote of ["'", '"', '`']) {
			expect(namedRoutes(`${quote}${href}${quote}`)).toEqual([id]);
			expect(namedRoutes(`${quote}${href}${quote}; ${quote}${href}${quote}`)).toEqual([id]);
		}
		expect(namedRoutes(`'${href}"`)).toEqual([]);
		expect(namedRoutes(`'${href}child/'`)).toEqual([]);
		expect(namedRoutes(href)).toEqual([]);
	}
});

test('each route owns only its expectations and drivers, and indexes own no address', () => {
	for (const { id, href } of BAND_UNREAD.routes) {
		for (const directory of ['tests/support/console-expect/console-nav', 'tests/support/panel-drivers']) {
			expect(routeScopeErrors(`${directory}/${id}.ts`, `const href = '${href}';`)).toEqual([]);
			expect(routeScopeErrors(`${directory}/index.ts`, `const href = '${href}';`)).toHaveLength(1);
			for (const other of BAND_UNREAD.routes.filter((route) => route.id !== id)) {
				expect(routeScopeErrors(`${directory}/${id}.ts`, `const href = '${other.href}';`)).toHaveLength(1);
			}
		}
		for (const name of CROSS_ROUTE_SPECS) {
			expect(routeScopeErrors(`tests/${name}.spec.ts`, `const href = '${href}';`)).toHaveLength(1);
		}
	}
	const two = BAND_UNREAD.routes.slice(0, 2).map(({ href }) => `'${href}'`).join(', ');
	expect(routeScopeErrors('tests/console-machine-page.spec.ts', two)).toEqual([]);
	expect(routeScopeErrors('tests/console-machine-data.spec.ts', two)).toHaveLength(1);
	expect(routeScopeErrors(String.raw`tests\console-machine-data.spec.ts`, two)).toHaveLength(1);
});

test('the console define and imports cannot move into shared code or pure-parser specs', () => {
	for (const path of DEFINE_OWNERS) {
		expect(defineScopeErrors(path, 'const chosen = __CONSOLE__;')).toEqual([]);
	}
	for (const path of ['src/lib/components/Panel.svelte', 'tests/appearance-config.spec.ts']) {
		const code = 'const chosen = __CONSOLE__;';
		expect(defineScopeErrors(path, path.endsWith('.svelte') ? `<script lang="ts">${code}</script>` : code)).toHaveLength(1);
	}
	expect(defineScopeErrors('src/lib/components/Panel.svelte', '<p>{__CONSOLE__.shared.chart_height}</p>')).toHaveLength(1);
	const module = '$lib/console/route-console';
	for (const code of [
		`import { routeConsole } from '${module}';`,
		`import type { RouteConsole } from '${module}';`,
		`import '${module}';`,
		`export { routeConsole } from '${module}';`,
		`import value = require('${module}');`,
		`const value = import('${module}');`,
		`type Value = import('${module}').RouteConsole;`,
		`const value = require('${module}');`
	]) {
		expect(defineScopeErrors('src/lib/server/config.ts', code)).toEqual([]);
		expect(defineScopeErrors('src/routes/console/+page.server.ts', code)).toEqual([]);
		expect(defineScopeErrors('tests/appearance-config.spec.ts', code)).toHaveLength(1);
		expect(defineScopeErrors('src/lib/components/Panel.svelte', `<script>${code}</script>`)).toHaveLength(1);
	}
	expect(defineScopeErrors('tests/appearance-config.spec.ts', "import { routeConsolesFrom } from '../src/lib/server/config';")).toEqual([]);
	expect(defineScopeErrors('src/routes/console-other/+page.ts', `import '${module}';`)).toHaveLength(1);
	expect(defineScopeErrors('tests/appearance-config.spec.ts', "import { routeConsolesFrom } from '../src/lib/console/route-console.ts';")).toHaveLength(1);
	expect(defineScopeErrors('tests/console-route-scope.spec.ts', `const sample = "import '${module}';";`)).toEqual([]);
});

test('named expectations, drivers and specs keep route ownership', () => {
	const specs = Object.values(groupedSpecs(join(FRONTEND, 'tests'))).flat();
	const files = [...supportFiles(), ...specs.map((name) => `tests/${name}`), 'tests/whole-day.spec.ts'];
	const errors = files.flatMap((file) => routeScopeErrors(file, readFileSync(join(FRONTEND, file), 'utf8')));
	expect(errors, 'Move quoted addresses to the owning route expectation or driver').toEqual([]);
});

test('named sources expose the console define only through its route boundary', () => {
	const sources = Object.entries(SOURCE_INPUTS).flatMap(([directory, names]) => names.map(
		(name) => directory ? `${directory}/${name}` : name
	));
	const specs = Object.values(groupedSpecs(join(FRONTEND, 'tests'))).flat().map((name) => `tests/${name}`);
	const files = [...sources, ...supportFiles(), ...specs, 'tests/whole-day.spec.ts'];
	const errors = files.flatMap((file) => defineScopeErrors(file, readFileSync(join(FRONTEND, file), 'utf8')));
	expect(errors, 'Pass console values as props; test the parser through the server config loader').toEqual([]);
});
