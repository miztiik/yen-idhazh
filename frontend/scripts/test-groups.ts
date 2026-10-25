import { existsSync } from 'node:fs';
import { basename, join } from 'node:path';

export const FRONTEND_GROUPS = [
	'logic', 'reader', 'offline', 'console', 'archive', 'model-search', 'publishing'
] as const;

export type FrontendGroup = (typeof FRONTEND_GROUPS)[number];

const FILES: Record<FrontendGroup, readonly string[]> = {
	logic: [
		'appearance-config', 'applied-line', 'archive-calendar', 'archive-scope', 'asset-base',
		'assist-guard', 'chart-types', 'chart-vocabulary', 'charts', 'console',
		'console-article-cost', 'console-band', 'console-canary-host-halves',
		'console-chart-days', 'console-charts-rule', 'console-chrome', 'console-compression',
		'console-compression-rows', 'console-coverage', 'console-cuts-by-run',
		'console-data-explorer', 'console-data-explorer-address', 'console-data-explorer-cells',
		'console-data-explorer-examples', 'console-data-explorer-gaps',
		'console-data-explorer-keep', 'console-data-explorer-shape', 'console-date-axis',
		'console-disk-reads', 'console-doubt', 'console-drawn-cells', 'console-failure',
		'console-failures', 'console-flow', 'console-frame', 'console-host-spans',
		'console-item-cost', 'console-judgement-nothings', 'console-machine',
		'console-machine-cards', 'console-machine-data', 'console-machine-split', 'console-model',
		'console-memory-board',
		'console-model-instruments', 'console-model-nothings', 'console-model-panels',
		'console-model-reasons', 'console-model-reductions',
		'console-model-rule', 'console-model-work', 'console-nav', 'console-panel-queries',
		'console-pipelines-window', 'console-polarity',
		'console-pipelines-native', 'console-pipelines-nothings',
		'console-published', 'console-ranked', 'console-readout-data',
		'console-run-health', 'console-shard-board', 'console-shell', 'console-site-size',
		'console-stage-timing-days', 'console-timings', 'console-voices', 'console-voices-cuts',
		'console-voices-fetch-time',
		'console-voices-feeds', 'console-voices-retiring', 'console-voices-sources',
		'console-waiting', 'console-window', 'day-list',
		'day-metrics', 'day-seam', 'day-search', 'day-states', 'duration-cohort', 'empty-day',
		'explorer-status',
		'explorer-column-groups', 'explorer-strip-fit', 'explorer-type-colour',
		'explorer-type-family', 'extraction-trend', 'extraction-window', 'filter-bar',
		'frame', 'glance-and-rank', 'holdout', 'holdout-domain', 'icons',
		'indexed-runs', 'item-meta', 'item-time', 'item-visual', 'judgement-evidence',
		'layout-overflow', 'ledger-catalog', 'ledger-copy', 'ledger-door', 'ledger-lifecycle', 'ledger-rows',
		'lenses', 'manifest', 'memory-held', 'merge-line', 'model-cards',
		'number-format', 'one-pass-reductions', 'payload-ceilings',
		'platform-mix', 'preview-port', 'processor-lost', 'prompt-reuse',
		'publication', 'recorded-line',
		'recorded-slices', 'run-axis', 'run-yield', 'served-day', 'settings-moved',
		'source-classification-binding',
		'similarity-ledgers', 'span-sentences', 'span-words', 'statement',
		'telemetry-header', 'telemetry-hold', 'throughput-window', 'time-split', 'tokens',
		'topics', 'verdict-split', 'vocabulary', 'weights'
	],
	reader: ['payload-state', 'reading-page', 'visual-legibility'],
	offline: ['service-worker'],
	console: [
		'console-data-explorer-still', 'console-machine-journey', 'console-model-builder', 'console-model-ledgers',
		'console-telemetry-heal', 'console-voices-journey',
		'console-pipelines-lifecycle', 'console-pipelines-components',
		'console-pipelines-cold', 'console-pipelines-days', 'console-pipelines-reserved',
		'console-pipelines-retained-compression', 'console-pipelines-retained-failure',
		'console-pipelines-retained-failures', 'console-pipelines-retained-item-cost',
		'console-pipelines-retained-window', 'console-pipelines-sufficiency',
		'console-pipelines-timeline-page', 'console-pipelines-window-page'
	],
	archive: ['archive'],
	'model-search': ['search'],
	publishing: ['canaries', 'explorer-boundary', 'malformed-day']
};

export function groupForSpec(filename: string): FrontendGroup | undefined {
	const name = basename(filename).replace(/\.spec\.ts$/, '');
	for (const [group, names] of Object.entries(FILES)) {
		if (names.includes(name)) return group as FrontendGroup;
	}
	return undefined;
}

export function groupedSpecs(directory: string): Record<FrontendGroup, string[]> {
	const groups = Object.fromEntries(FRONTEND_GROUPS.map((group) => [group, []])) as unknown as Record<
		FrontendGroup,
		string[]
	>;
	for (const group of FRONTEND_GROUPS) {
		for (const name of FILES[group]) {
			const filename = `${name}.spec.ts`;
			if (!existsSync(join(directory, filename))) {
				throw new Error(`Declared test ${filename} is missing; update scripts/test-groups.ts.`);
			}
			groups[group].push(filename);
		}
		groups[group].sort();
	}
	return groups;
}
