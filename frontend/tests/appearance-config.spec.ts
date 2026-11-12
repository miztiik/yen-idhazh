/** The appearance config's read-side migration, driven in both directions.
 *
 * `config/appearance.json` was split off `config/idhazh.json` on 2026-08-29.
 * The move is only safe if a checkout that has not been migrated resolves to
 * exactly what it resolved to before, so that is what this file proves. The
 * fixtures set every field to a NON-DEFAULT value: a merge that always
 * returned the defaults would pass a fixture built from them and fail here.
 */

import { expect, test } from '@playwright/test';
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { assistConfig, consoleConfig, explorerConfig, mergeLayers, routeConsoles, routeConsolesFrom } from '../src/lib/server/config';
import ts from 'typescript';
import { runInNewContext } from 'node:vm';
import { BAND_UNREAD, type RouteId } from '../src/lib/console/band';
import { resolveConsoleStyle, type ConsoleStyleConfig } from '../src/lib/console/console-style';
import { renderFrameCss } from '../scripts/build-frame-css.mjs';
import { consolePalette } from '../scripts/console-palette';

const REPO = join(dirname(fileURLToPath(import.meta.url)), '..', '..');

test('the explorer receives the configured positive file limit', () => {
	const appearance = JSON.parse(readFileSync(join(REPO, 'config', 'appearance.json'), 'utf8'));
	expect(explorerConfig().max_files).toBe(appearance.console.explorer_max_files);
});

function routeFiles(): Record<string, { panel_groups: { id: string; title: string; panels: string[] }[]; judged: string[]; knobs: Record<string, number> }> {
	return Object.fromEntries(BAND_UNREAD.routes.map(({ id }) => [id, {
		panel_groups: [{ id, title: '', panels: [`${id}-panel`] }],
		judged: [`${id}-panel`],
		knobs: { floor: 2 }
	}]));
}

test.describe('route-owned console configuration', () => {
	test('preserves the committed six routes and their judged panels', () => {
		const routes = routeConsoles();
		expect(Object.keys(routes).sort()).toEqual(BAND_UNREAD.routes.map(({ id }) => id).sort());
		expect(routes.machine.judged).toEqual([
			'two-clocks', 'slower-machines', 'platform-mix',
			'tail-trend', 'closest-to-memory', 'memory-held', 'context-headroom',
			'article-cost', 'prompt-reuse', 'read-against-written', 'counterfactual-cost'
		]);
		expect(routes.pipelines.judged).toContain('slowest-articles');
		expect(routes['data-explorer'].judged).toEqual(['data-explorer-rows', 'data-explorer-shape']);
		const judgementPanels = [
			'merged-stories', 'merge-line', 'judge-agreement',
			'record-gates', 'verdict-split', 'holdout-margin'
		];
		expect(routes.judgement.panel_groups).toEqual([
			{ id: 'judgement', title: '', panels: judgementPanels }
		]);
		expect(routes.judgement.judged).toEqual(judgementPanels);
		const modelPanels = [
			'model-cards', 'model-throughput', 'call-ending',
			'doubt-reasons', 'faithfulness', 'source-doubts', 'write-cost',
			'score-cost', 'summary-length'
		];
		expect(routes.model.panel_groups).toEqual([
			{ id: 'summaries', title: '', panels: modelPanels }
		]);
		expect(routes.model.judged).toEqual(modelPanels);
		const sources = ['source-health', 'feeds-failed', 'fetch-time', 'retiring', 'source-cuts'];
		const ranking = ['ranking-discount', 'why-chosen', 'watchlist'];
		expect(routes.voices.panel_groups).toEqual([
			{ id: 'what-the-sources-supplied', title: 'What the sources supplied', panels: sources },
			{ id: 'what-the-ranking-did', title: 'What the ranking did', panels: ranking }
		]);
		expect(routes.voices.judged).toEqual([...sources, ...ranking]);
		expect(consoleConfig()).not.toHaveProperty('panel_groups');
		expect(consoleConfig()).not.toHaveProperty('judged_panel_ids');
	});

	test('parses independently supplied files without changing their values', () => {
		const files = routeFiles();
		expect(routeConsolesFrom(files)).toEqual(files);
	});

	test('keeps Run total as the shipped token metric and refuses unsupported configured modes', () => {
		expect(routeConsoles().machine.knobs.read_write_default_metric).toBe(0);
		const files = routeFiles();
		files.machine.knobs.read_write_default_metric = 2;
		expect(() => routeConsolesFrom(files)).toThrow('knobs.read_write_default_metric must be 0 (Run total) or 1 (Median per article)');
	});

	test('refuses a missing route file', () => {
		const files = routeFiles();
		delete files.model;
		expect(() => routeConsolesFrom(files)).toThrow(/config\/console.*model/);
	});

	test('refuses an unknown route file', () => {
		expect(() => routeConsolesFrom({ ...routeFiles(), unknown: {} })).toThrow(/config\/console.*unknown/);
	});

	for (const key of ['panel_groups', 'judged', 'knobs'] as const) {
		test(`refuses missing ${key}`, () => {
			const files: Record<string, unknown> = routeFiles();
			const route = { ...files.machine as Record<string, unknown> };
			delete route[key];
			files.machine = route;
			expect(() => routeConsolesFrom(files)).toThrow(`config/console/machine.json names no ${key}`);
		});
	}

	test('refuses an unknown route key', () => {
		const files = routeFiles();
		expect(() => routeConsolesFrom({ ...files, machine: { ...files.machine, surprise: 1 } }))
			.toThrow('config/console/machine.json names unknown surprise');
	});

	test('refuses partly titled groups', () => {
		const files = routeFiles();
		files.machine.panel_groups.push({ id: 'second', title: 'Second', panels: ['second-panel'] });
		expect(() => routeConsolesFrom(files)).toThrow(/machine.json.*panel_groups.*titles/);
	});

	test('refuses duplicate group ids', () => {
		const files = routeFiles();
		files.machine.panel_groups.push({ id: 'machine', title: '', panels: ['second-panel'] });
		expect(() => routeConsolesFrom(files)).toThrow(/machine.json.*id.*repeats machine/);
	});

	test('refuses a panel repeated on one route', () => {
		const files = routeFiles();
		files.machine.panel_groups[0].panels.push('machine-panel');
		expect(() => routeConsolesFrom(files)).toThrow(/machine.json.*panels.*repeats machine-panel/);
	});

	test('refuses a panel repeated across routes', () => {
		const files = routeFiles();
		files.machine.panel_groups[0].panels.push('pipelines-panel');
		expect(() => routeConsolesFrom(files)).toThrow(/machine.json.*panels.*repeats pipelines-panel/);
	});

	test('refuses an undrawn judged id', () => {
		const files = routeFiles();
		files.machine.judged.push('absent');
		expect(() => routeConsolesFrom(files)).toThrow(/machine.json.*judged.*undrawn absent/);
	});

	test('refuses a repeated judged id', () => {
		const files = routeFiles();
		files.machine.judged.push('machine-panel');
		expect(() => routeConsolesFrom(files)).toThrow(/machine.json.*judged.*repeats machine-panel/);
	});

	for (const value of [NaN, Infinity, -Infinity, '2', null]) {
		test(`refuses nonfinite or nonnumeric knob ${String(value)}`, () => {
			const files = routeFiles();
			files.machine.knobs.floor = value as number;
			expect(() => routeConsolesFrom(files)).toThrow('config/console/machine.json knobs.floor must be a finite number');
		});
	}

	test('accessors name a missing knob without a source default', () => {
		const source = readFileSync(join(REPO, 'frontend', 'src', 'lib', 'console', 'route-console.ts'), 'utf8');
		const compiled = ts.transpileModule(source, {
			compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 }
		}).outputText;
		const exports: Record<string, unknown> = {};
		const defined = { shared: consoleConfig(), routes: routeConsolesFrom(routeFiles()) };
		runInNewContext(compiled, {
			exports,
			require: () => ({ BAND_UNREAD }),
			['__' + 'CONSOLE__']: defined
		});
		const access = exports.routeKnobs as (route: RouteId, keys: readonly string[]) => Record<string, number>;
		expect(access('machine', ['floor'])).toEqual({ floor: 2 });
		expect(() => access('machine', ['missing'])).toThrow('config/console/machine.json names no knobs.missing');
		expect((exports.consoleKnobs as () => unknown)()).toBe(defined.shared);
		expect((exports.routeConsole as (route: RouteId) => unknown)('machine')).toBe(defined.routes.machine);
	});
});

interface Knobs {
	sections: string[];
	archive_page_size: number;
	show_filter: boolean;
	tagline: string;
}

const DEFAULTS: Knobs = {
	sections: ['notice', 'topics', 'leads', 'items'],
	archive_page_size: 25,
	show_filter: true,
	tagline: 'Daily news summaries, with links to their sources.'
};

/** Nothing here equals a default. That is what stops a stub from passing. */
const CHOSEN: Knobs = {
	sections: ['items', 'topics'],
	archive_page_size: 9,
	show_filter: false,
	tagline: 'Chosen, not defaulted.'
};

test.describe('the appearance config migration', () => {
	test('an unmigrated checkout resolves to what the new file resolves to', () => {
		// Before the split: every knob in the legacy block, no appearance file.
		const before = mergeLayers(DEFAULTS, CHOSEN, undefined);
		// After the split: every knob in the new file, legacy block deleted.
		const after = mergeLayers(DEFAULTS, undefined, CHOSEN);

		expect(before).toEqual(after);
		expect(before).toEqual(CHOSEN);
		// And neither is the default, so the assertion above has teeth.
		expect(before).not.toEqual(DEFAULTS);
	});

	test('the new file wins a field the legacy block also sets', () => {
		const resolved = mergeLayers(DEFAULTS, { archive_page_size: 4 }, { archive_page_size: 7 });
		expect(resolved.archive_page_size).toBe(7);
	});

	test('a legacy value survives a new file that does not mention it', () => {
		// The reason the legacy block is a middle layer and not a discarded one:
		// a partly migrated file must not snap a knob back to a default nobody
		// chose.
		const resolved = mergeLayers(DEFAULTS, CHOSEN, { archive_page_size: 7 });
		expect(resolved.tagline).toBe(CHOSEN.tagline);
		expect(resolved.show_filter).toBe(false);
		expect(resolved.archive_page_size).toBe(7);
	});

	test('a fresh clone with neither file runs on the defaults', () => {
		expect(mergeLayers(DEFAULTS, undefined, undefined)).toEqual(DEFAULTS);
	});
});

test.describe('the committed appearance file', () => {
	test('exists and carries every block the surface is drawn from', () => {
		const path = join(REPO, 'config', 'appearance.json');
		expect(existsSync(path)).toBe(true);
		const parsed = JSON.parse(readFileSync(path, 'utf8')) as Record<string, unknown>;
		for (const block of [
			'digest',
			'console',
			'console_style',
			'assist',
			'frame',
			'theme',
			'chart',
			'icons',
			'motion',
			'version'
		]) {
			expect(parsed, `config/appearance.json is missing ${block}`).toHaveProperty(block);
		}
	});

	test('a partial console style keeps per-role defaults and replaces a palette whole', () => {
		const defaults = resolveConsoleStyle();
		const categorical = ['#112231', '#112232', '#112233', '#112234', '#112235', '#112236', '#112237', '#112238'];
		const changed = resolveConsoleStyle({
			colors: { light: { accent: '#145a55', categorical } },
			typography: { small: { weight: 500 } },
			elevation: { light: { panel: { y_px: 2 } } }
		});
		expect(changed.colors.light.categorical).toEqual(categorical);
		expect(changed.colors.dark).toEqual(defaults.colors.dark);
		expect(changed.typography.small).toEqual({ ...defaults.typography.small, weight: 500 });
		expect(changed.elevation.light.panel).toEqual({ ...defaults.elevation.light.panel, y_px: 2 });
	});

	test('the real CSS renderer substitutes a legal nondefault style and is deterministic', () => {
		const fixture: { console_style: ConsoleStyleConfig } = JSON.parse(readFileSync(
			join(REPO, 'tests', 'fixtures', 'contracts', 'appearance-config', 'knobs-set-away-from-the-defaults.json'), 'utf8'
		));
		const generated = renderFrameCss({ console_style: fixture.console_style });
		expect(generated).toBe(renderFrameCss({ console_style: fixture.console_style }));
		const [reader, operator] = generated.split('/* The selector includes the outer canvas');
		expect(reader).not.toContain('--color-bg:');
		expect(reader).not.toContain('--console-');
		expect(operator).toContain('--console-small-size: 0.875rem;');
		expect(operator).toContain('--console-rail-width: 13rem;');
		expect(operator).toContain('--console-chart-grid-dash: 2 4;');
		expect(operator).toContain('--color-bg: #1a1a18;');
	});

	test('PiYG aligns console categories while keeping neutral absence, explicit controls and reader tokens', () => {
		const style = resolveConsoleStyle();
		for (const mode of ['light', 'dark'] as const) {
			const colors = style.colors[mode];
			const before = structuredClone(colors);
			const palette = consolePalette(colors, mode, 'piyg');
			expect(palette.slice(0, 7)).not.toEqual(colors.categorical.slice(0, 7));
			expect(palette[7]).toBe(colors.categorical[7]);
			expect(new Set(palette).size).toBe(8);
			expect(colors).toEqual(before);
		}
		const original = renderFrameCss();
		const aligned = renderFrameCss({
			chart: { palette: 'piyg' },
			console_style: { colors: { light: { accent: '#145a55', focus: '#7d2359', selected: '#e5eee7' } } }
		});
		const marker = '/* The selector includes the outer canvas';
		expect(aligned.split(marker)[0]).toBe(original.split(marker)[0]);
		expect(aligned).toContain('--color-accent: #145a55;');
		expect(aligned).toContain('--color-focus: #7d2359;');
		expect(aligned).toContain('--console-selected: #e5eee7;');
		expect(aligned).toContain('--gradient-wordmark: linear-gradient(to right,');
	});

	test('console font and elevation switches use existing fallbacks without new assets', () => {
		const css = renderFrameCss({ theme: { display_face_enabled: false, elevation_enabled: false } });
		const operator = css.split('/* The selector includes the outer canvas')[1];
		expect(operator).not.toContain('InterVariable');
		expect(operator).not.toContain('rgba(0, 0, 0,');
		expect(operator).toContain('--shadow-sm: none;');
		expect(css).toContain('--font-display: var(--font-reading);');
	});

	test('a numeric console cap remains wider than the reading frame', () => {
		// The bounds live in the Pydantic contract and are enforced at build
		// time. This asserts the COMMITTED values sit inside them, so a hand
		// edit that skipped the contract still fails a gate.
		const parsed = JSON.parse(
			readFileSync(join(REPO, 'config', 'appearance.json'), 'utf8')
		) as { frame: { reading_max_px: number; console_max_px: number | null; measure_ch: number } };

		expect(parsed.frame.reading_max_px).toBeGreaterThanOrEqual(960);
		if (parsed.frame.console_max_px !== null) {
			expect(parsed.frame.console_max_px).toBeGreaterThanOrEqual(parsed.frame.reading_max_px);
		}
		expect(parsed.frame.measure_ch).toBeGreaterThanOrEqual(52);
		expect(parsed.frame.measure_ch).toBeLessThanOrEqual(80);
	});

	test('the server draws a chart no wider than its container can ever be', () => {
		// A server that prerenders wider than the frame is wrong on every first
		// paint and self-corrects only once a script runs, which is the one
		// moment a static site is supposed to be already finished.
		const parsed = JSON.parse(
			readFileSync(join(REPO, 'config', 'appearance.json'), 'utf8')
		) as { frame: { console_max_px: number | null }; chart: { width_px: number } };

		if (parsed.frame.console_max_px !== null) {
			expect(parsed.chart.width_px).toBeLessThanOrEqual(parsed.frame.console_max_px);
		}
	});

	test('the frame producer preserves explicit numeric caps and emits no cap for the full window', () => {
		const capped = renderFrameCss({ frame: { console_max_px: 1600 } });
		const fluid = renderFrameCss({ frame: { console_max_px: null } });
		expect(capped).toContain('--frame-console: 1600px;');
		expect(fluid).toBe(capped.replace('--frame-console: 1600px;', '--frame-console: none;'));
		expect(renderFrameCss()).toBe(fluid);
	});
});

/** The knobs the `assist` block carries that no page may be handed.
 *
 * `config/` keeps eleven keys under `assist` and the browser reads four. The
 * other seven belong to the build and the pipeline: `max_tokens` and
 * `min_readable_letter_share` to the encoder, and the five `model_` keys to
 * `vite.config.ts` and `svelte.config.js`, which read them at BUILD time and
 * put what a tab needs in the bundle rather than in the document. Until
 * 2026-09-05 the whole block was merged straight into the prerendered
 * `/archive/` document - one date and three numbers about the build, shipped to
 * every reader who ever opened the archive. Seven of them now, and about 600
 * bytes of it hex, so the keep-list matters more than it did.
 *
 * The digest block has had this discipline since it was split. This is the same
 * question asked of the block beside it, and the answer had never been checked.
 */
test.describe('the assist block a reader is handed', () => {
const DECLARED = ['archive_search_months', 'result_limit', 'search_min_days', 'search_months', 'similarity_floor'];

function blockOnDisk(file: string): Record<string, unknown> {
const path = join(REPO, 'config', file);
if (!existsSync(path)) return {};
const parsed = JSON.parse(readFileSync(path, 'utf8')) as {
assist?: Record<string, unknown>;
};
return parsed.assist ?? {};
}

test('carries exactly the fields the interface declares', () => {
expect(Object.keys(assistConfig()).sort()).toEqual(DECLARED);
});

test('carries nothing the pipeline put in the same block', () => {
// Named rather than counted. A census fails the day somebody adds a knob
// for a good reason; this fails only when one of these reaches a reader.
const handed = Object.keys(assistConfig());
const onDisk = { ...blockOnDisk('idhazh.json'), ...blockOnDisk('appearance.json') };
const pipelineOwned = Object.keys(onDisk).filter((key) => !DECLARED.includes(key));

expect(pipelineOwned.length).toBeGreaterThan(0);
for (const key of pipelineOwned) expect(handed).not.toContain(key);
});
});

/** Route-owned lists and retired presentation knobs do not reach a console page. */
test.describe('the console block a page is handed', () => {
	const NOT_HANDED = ['panel_groups', 'judged_panel_ids', 'pan_days', 'zoom_factor', 'band_outlier_rows', 'plot_min_fill_share'];

	test('carries none of the route-only lists or retired knobs', () => {
		const onDisk = (
			JSON.parse(readFileSync(join(REPO, 'config', 'appearance.json'), 'utf8')) as {
				console: Record<string, unknown>;
			}
		).console;
		const handed = Object.keys(consoleConfig());
		for (const key of NOT_HANDED) {
			expect(onDisk).not.toHaveProperty(key);
			expect(handed, `consoleConfig() hands every console page console.${key}`).not.toContain(key);
		}
		const legacy = JSON.parse(readFileSync(join(REPO, 'config', 'idhazh.json'), 'utf8')).console;
		for (const key of ['pan_days', 'zoom_factor', 'band_outlier_rows', 'plot_min_fill_share']) {
			expect(legacy).not.toHaveProperty(key);
		}
	});
});
