import { existsSync } from 'node:fs';
import { basename, join } from 'node:path';

export const FRONTEND_GROUPS = [
	'logic', 'reader', 'offline', 'console', 'panels', 'archive', 'model-search', 'publishing'
] as const;

export type FrontendGroup = (typeof FRONTEND_GROUPS)[number];

const FILES: Record<FrontendGroup, readonly string[]> = {
	console: [
		'console', 'console-article-cost', 'console-axis', 'console-band',
		'console-chart-lifetime', 'console-chart-pending', 'console-charts-rule',
		'console-chrome', 'console-cold-load', 'console-compression', 'console-coverage',
		'console-data-explorer', 'console-data-explorer-still', 'console-data-explorer-window',
		'console-disk-reads', 'console-doubt', 'console-explorer-rails', 'console-extraction', 'console-failure',
		'console-failures', 'console-flow', 'console-frame',
		'console-item-cost', 'console-judgement-agreement', 'console-judgement-holdout',
		'console-judgement-line', 'console-judgement-merges', 'console-judgement-verdict',
		'console-machine-data', 'console-machine-page',
		'console-machine-panels', 'console-machine-reuse',
		'console-mark-parity', 'console-memory-board',
		'console-memory-held', 'console-model-instruments', 'console-model-panels',
		'console-model-reasons', 'console-model-rule', 'console-model', 'console-nav',
		'console-pipeline-timeline', 'console-polarity', 'console-processor-lost',
		'console-published', 'console-query-door', 'console-ranked', 'console-readout',
		'console-reserved', 'console-run-health', 'console-run-yield',
		'console-shard-board', 'console-shell', 'console-site-size',
		'console-telemetry-heal', 'console-throughput', 'console-timings', 'console-title',
		'console-voices-cuts', 'console-voices-feeds', 'console-voices-retiring',
		'console-voices-sources', 'console-voices', 'console-window-claims', 'console-window'
	],
	logic: [
		'appearance-config', 'archive-scope', 'asset-base', 'assist-guard', 'browser-selection', 'chart-vocabulary', 'day-list', 'day-metrics', 'day-search',
		'console-data-explorer-address', 'console-data-explorer-cells', 'console-data-explorer-examples', 'console-data-explorer-gaps', 'console-data-explorer-keep', 'console-data-explorer-shape',
		'explorer-column-groups', 'explorer-strip-fit', 'explorer-type-colour', 'explorer-type-family',
		'console-host-spans', 'console-machine-cards', 'console-machine-split', 'console-machine',
		'console-chart-days', 'console-cuts-by-run', 'console-date-axis', 'console-compression-rows', 'console-model-work', 'console-readout-data',
		'console-stage-timing-days',
		'day-shards',
		'extraction-trend', 'extraction-window', 'frame',
		'glance-and-rank', 'holdout', 'holdout-domain', 'layout-overflow', 'ledger-copy', 'ledger-door', 'ledger-lifecycle', 'ledger-rows', 'memory-held', 'merge-line', 'model-cards',
		'one-pass-reductions',
		'platform-mix', 'preview-port',
		'processor-lost', 'prompt-reuse',
		'publication',
		'run-axis', 'run-yield',
		'settings-moved', 'statement', 'raw-listed-through',
		'telemetry-header', 'telemetry-hold', 'throughput-window', 'time-split',
		'tokens', 'verdict-split', 'vocabulary',
		'weights'
	],
	reader: [
		'dated-day', 'day-states', 'filter-bar', 'footer-facts', 'item-card', 'item-meta',
		'item-time', 'item-visual', 'item-zones', 'layout', 'leading-stories',
		'lenses', 'manifest', 'payload-state', 'reading-page', 'readstate', 'source-mark',
		'theme', 'topic-day', 'topics', 'whole-day'
	],
	// Alone, because it rewrites the kill switch the whole served site shares and
	// `reading-page` installs the worker that reads it. See `playwright.config.ts`.
	offline: ['service-worker'],
	// The console's panels as a reviewer sees them, and the gates a selector can
	// decide about them. Apart from `console` so a change to what every panel is
	// drawn from can buy these two without the console's hundreds of tests.
	panels: ['panel-captures', 'panel-sufficiency'],
	archive: ['archive', 'archive-calendar'],
	'model-search': ['search'],
	publishing: [
		'canaries', 'charts', 'day-seam', 'empty-day', 'icons',
		'explorer-boundary', 'ledger-ranges', 'malformed-day', 'payload-weight', 'published-ledgers', 'served-day', 'staged-day'
	]
};

export function groupForSpec(filename: string): FrontendGroup | undefined {
	const name = basename(filename).replace(/\.spec\.ts$/, '');
	for (const [group, names] of Object.entries(FILES)) {
		if (names.includes(name)) return group as FrontendGroup;
	}
	if (/^console(?:-|$)/.test(name)) return 'console';
	return undefined;
}

export function groupedSpecs(directory: string): Record<FrontendGroup, string[]> {
	const groups: Record<FrontendGroup, string[]> = {
		logic: [], reader: [], offline: [], console: [], panels: [], archive: [], 'model-search': [], publishing: []
	};
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
