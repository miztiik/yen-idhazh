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
import { assistConfig, consoleConfig, mergeLayers, routeConsoles, routeConsolesFrom } from '../src/lib/server/config';
import ts from 'typescript';
import { runInNewContext } from 'node:vm';
import { BAND_UNREAD, type RouteId } from '../src/lib/console/band';

const REPO = join(dirname(fileURLToPath(import.meta.url)), '..', '..');

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
		expect(routes.machine.judged).toEqual(['platform-mix']);
		expect(routes['data-explorer'].judged).toEqual(['data-explorer-rows', 'data-explorer-shape']);
		for (const id of ['model', 'voices', 'judgement'] as const) {
			expect(routes[id].panel_groups).toEqual([]);
			expect(routes[id].judged).toEqual([]);
		}
		expect(consoleConfig()).not.toHaveProperty('panel_groups');
		expect(consoleConfig()).not.toHaveProperty('judged_panel_ids');
	});

	test('parses independently supplied files without changing their values', () => {
		const files = routeFiles();
		expect(routeConsolesFrom(files)).toEqual(files);
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
	sections: ['notice', 'leads', 'topics', 'items'],
	archive_page_size: 25,
	show_filter: true,
	tagline: 'A daily digest that checks its own work.'
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

	test('the frame is wide enough to be a frame, and the console is wider', () => {
		// The bounds live in the Pydantic contract and are enforced at build
		// time. This asserts the COMMITTED values sit inside them, so a hand
		// edit that skipped the contract still fails a gate.
		const parsed = JSON.parse(
			readFileSync(join(REPO, 'config', 'appearance.json'), 'utf8')
		) as { frame: { reading_max_px: number; console_max_px: number; measure_ch: number } };

		expect(parsed.frame.reading_max_px).toBeGreaterThanOrEqual(960);
		expect(parsed.frame.console_max_px).toBeGreaterThanOrEqual(parsed.frame.reading_max_px);
		expect(parsed.frame.measure_ch).toBeGreaterThanOrEqual(52);
		expect(parsed.frame.measure_ch).toBeLessThanOrEqual(80);
	});

	test('the server draws a chart no wider than its container can ever be', () => {
		// A server that prerenders wider than the frame is wrong on every first
		// paint and self-corrects only once a script runs, which is the one
		// moment a static site is supposed to be already finished.
		const parsed = JSON.parse(
			readFileSync(join(REPO, 'config', 'appearance.json'), 'utf8')
		) as { frame: { console_max_px: number }; chart: { width_px: number } };

		expect(parsed.chart.width_px).toBeLessThanOrEqual(parsed.frame.console_max_px);
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
const DECLARED = ['result_limit', 'search_min_days', 'search_months', 'similarity_floor'];

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

/** Route-owned lists leave the shared block; the gate-only floor stays on disk. */
test.describe('the console block a page is handed', () => {
	const NOT_HANDED = ['panel_groups', 'judged_panel_ids', 'plot_min_fill_share'];

	test('carries none of the keys only a route or the gate specs read', () => {
		const onDisk = (
			JSON.parse(readFileSync(join(REPO, 'config', 'appearance.json'), 'utf8')) as {
				console: Record<string, unknown>;
			}
		).console;
		const handed = Object.keys(consoleConfig());
		for (const key of NOT_HANDED) {
			if (key === 'plot_min_fill_share') expect(onDisk).toHaveProperty(key);
			else expect(onDisk).not.toHaveProperty(key);
			expect(handed, `consoleConfig() hands every console page console.${key}`).not.toContain(key);
		}
	});
});