/** Which fixed source inputs do the console boundary oracles read? */
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parse } from 'svelte/compiler';
import ts from 'typescript';

export const FRONTEND = fileURLToPath(new URL('../..', import.meta.url));

// Named inputs, not a walk: a new consumer must join this inventory.
export const SOURCE_INPUTS: Readonly<Record<string, readonly string[]>> = {
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
		'empty.ts', 'EmptyState.svelte', 'Flow.svelte', 'flow.ts', 'model-rule.ts', 'motion.ts', 'ordered-colour.ts',
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
		'RankedList.svelte', 'RateControl.svelte', 'ReadAloud.svelte', 'Reserved.svelte', 'RouteStatus.svelte',
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
		'holdout.ts', 'item-cost.ts', 'judgement-evidence.ts', 'merge-line.ts', 'model-cards.ts', 'prompt-cache-subtitle.ts',
		'query-state.ts', 'rates.ts', 'recording.ts', 'RecordNotes.svelte', 'route-console.ts', 'run-square.ts', 'series-tokens.ts',
		'settings-moved.ts', 'span-words.ts', 'strip.ts', 'verdict-split.ts', 'waiting.ts', 'window-slot.ts'
	],
	'src/lib/console/queries': ['machine.ts', 'model.ts', 'pipelines.ts', 'shared.ts', 'voices.ts', 'window.ts'],
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
		'ledger-reach.ts', 'ledger.ts', 'page-keeper.ts', 'raw-day-index.ts', 'read-session.ts', 'site-window.ts',
		'slice-query.ts', 'slice-reader.ts', 'slice-shapes.ts', 'slice.ts', 'statement.ts'
	],
	'src/lib/icons': ['generated.ts', 'Icon.svelte'],
	'src/lib/payload': ['desks.ts', 'drawing.ts', 'lenses.ts', 'project.ts', 'types.ts'],
	'src/lib/server': [
		'chart-days.ts', 'chart-render.ts', 'config.ts', 'cuts-by-run.ts', 'host-fingerprint.ts',
		'ledger-disk.ts', 'ledger-rows.ts', 'machine-counters.ts', 'model-work.ts', 'payload.ts',
		'publication.ts', 'recorded-line.ts', 'run-days.ts', 'run-timeline.ts', 'server-counter-notes.ts',
		'content-similarity-holdout.ts', 'content-similarity-judge.ts', 'source-retiring.ts', 'stage-timing-days.ts', 'window-day.ts'
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
		'backend-python.ts', 'browser.ts', 'door-page.ts', 'canary-config.ts', 'charts-ready.ts', 'check-addons.ts',
		'consecutive-days.ts', 'console-panels.ts', 'console-sources.ts', 'console-widths.ts', 'day-drawings.ts',
		'day-loader.ts', 'day-ready.ts', 'explorer-answer.ts', 'in-zone.ts', 'judgement-route.ts',
		'ledger-lifecycle.ts', 'machine-record-state.ts', 'machine-rows.ts', 'model-swap.ts',
		'month-shard.ts', 'panel-gates.ts', 'panel-tab.ts', 'published-site.ts', 'published.ts',
		'range-host.ts', 'reduction-input.ts', 'served-telemetry.ts', 'server-render.ts', 'span-said.ts',
		'telemetry-row.ts', 'views.ts'
	],
	'tests/fixtures/panels': ['WitnessPanel.svelte'],
	'tests/support/console-window': [
		'controls.ts', 'readout.ts', 'judgement-fixtures.ts', 'machine-spans.ts',
		'client-render.ts', 'server-panels.ts'
	]
};

export function sourceFiles(): string[] {
	return Object.entries(SOURCE_INPUTS).flatMap(([directory, names]) =>
		names.map((name) => directory ? `${directory}/${name}` : name));
}

export function drawnSourceFiles(): string[] {
	return sourceFiles().filter((file) =>
		/^src\/(?:lib\/(?:console|charts|components)\/|routes\/console\/)/.test(file));
}

export function readSource(file: string): string {
	return readFileSync(join(FRONTEND, file), 'utf8');
}

export function scriptTree(file: string, source: string): ts.SourceFile {
	if (!file.endsWith('.svelte')) return ts.createSourceFile(join(FRONTEND, file), source, ts.ScriptTarget.Latest, true);
	const root = parse(source, { modern: true });
	const scripts = [root.module, root.instance].flatMap((script) =>
		script == null ? [] : [source.slice(source.indexOf('>', script.start) + 1,
			source.lastIndexOf('</script', script.end))]);
	return ts.createSourceFile(join(FRONTEND, file), scripts.join('\n'), ts.ScriptTarget.Latest, true);
}

export function resolveSource(module: string, tree: ts.SourceFile): ts.SourceFile | null {
	const resolved = ts.resolveModuleName(module, tree.fileName, {
		moduleResolution: ts.ModuleResolutionKind.Bundler, baseUrl: FRONTEND,
		paths: { '$lib/*': ['src/lib/*'] }
	}, ts.sys).resolvedModule;
	return resolved ? ts.createSourceFile(resolved.resolvedFileName,
		readFileSync(resolved.resolvedFileName, 'utf8'), ts.ScriptTarget.Latest, true) : null;
}
