import { readdirSync } from 'node:fs';
import { basename } from 'node:path';

export const FRONTEND_GROUPS = [
	'logic', 'reader', 'offline', 'console', 'archive', 'model-search', 'publishing'
] as const;

export type FrontendGroup = (typeof FRONTEND_GROUPS)[number];

const FILES: Record<Exclude<FrontendGroup, 'console'>, readonly string[]> = {
	logic: [
		'appearance-config', 'archive-scope', 'asset-base', 'frame', 'one-pass-reductions',
		'preview-port', 'vocabulary'
	],
	reader: [
		'dated-day', 'day-states', 'filter-bar', 'footer-facts', 'item-card', 'item-meta',
		'item-visual', 'item-zones', 'layout', 'layout-overflow', 'leading-stories', 'lenses', 'manifest',
		'payload-state', 'reading-page', 'readstate', 'source-mark',
		'theme', 'time-rail', 'tokens', 'topic-day', 'topics', 'whole-day'
	],
	// Alone, because it rewrites the kill switch the whole served site shares and
	// `reading-page` installs the worker that reads it. See `playwright.config.ts`.
	offline: ['service-worker'],
	archive: ['archive', 'archive-calendar'],
	'model-search': ['search'],
	publishing: [
		'assist-guard', 'canaries', 'charts', 'day-seam', 'empty-day', 'icons',
		'malformed-day', 'payload-weight', 'prerender-guard', 'served-day', 'staged-day'
	]
};

export function groupForSpec(filename: string): FrontendGroup | undefined {
	const name = basename(filename).replace(/\.spec\.ts$/, '');
	if (/^console(?:-|$)/.test(name)) return 'console';
	for (const [group, names] of Object.entries(FILES)) {
		if (names.includes(name)) return group as FrontendGroup;
	}
	return undefined;
}

export function groupedSpecs(directory: string): Record<FrontendGroup, string[]> {
	const groups: Record<FrontendGroup, string[]> = {
		logic: [], reader: [], offline: [], console: [], archive: [], 'model-search': [], publishing: []
	};
	for (const filename of readdirSync(directory, { recursive: true, encoding: 'utf8' })
		.filter((name) => name.endsWith('.spec.ts')).map((name) => name.replaceAll('\\', '/')).sort()) {
		const group = groupForSpec(filename);
		if (!group) throw new Error(`No test group owns ${filename}; add it to scripts/test-groups.ts.`);
		groups[group].push(filename);
	}
	return groups;
}
