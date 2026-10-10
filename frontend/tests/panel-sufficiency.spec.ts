import { expect, test, type Page } from './support/browser';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { render } from 'svelte/server';

import { frame, noModelRuleNote } from '../src/lib/charts/frame';
import { dateSeries } from '../src/lib/charts/d3/dateSeries';
import { flow } from '../src/lib/charts/d3/flow';
import {
	emptyState,
	missingSentence,
	quietSentence,
	unreachableSentence,
	type EmptyDrawing
} from '../src/lib/charts/d3/empty';
import { BAND_UNREAD, type RouteId } from '../src/lib/console/band';
import { consolePanels, type ConsolePanels } from './support/console-panels';
import { BY_ROUTE, type PanelDrivers, type RouteDrivers } from './support/panel-drivers';
import { chooseExplorerQuestion, openExplorer, runExplorer } from './support/explorer-answer';
import { CONSOLE_WIDTHS, CONSOLE_WINDOW_HEIGHT } from './support/console-widths';
import { viewsOf } from './support/views';
import {
	judgeComparison,
	judgeFill,
	judgeLede,
	judgeNothings,
	judgeSettled,
	NOTHINGS,
	REFUSED_NOTHINGS,
	type BasicNothing,
	type Driver,
	readPanel,
	type GateNumber,
	type Nothing,
	type PanelReading,
	type Verdict
} from './support/panel-gates';
import { serverCompiler } from './support/server-render';
import { explorerConfig } from '../src/lib/server/config';
import { showPanel } from './support/panel-tab';

const PINNED = '2026-08-20';

/**
 * THE ORACLE for the sufficiency gates a selector can decide: each one clears
 * a good panel and fails a bad one, and the panels the console has opted in
 * are held to all six.
 *
 * Six of the ten gates in `docs/concepts/design-system.md` are arithmetic over
 * a drawn panel - 1 uses the screen, 2 separates figure from ground, 3 lands
 * one thing first, 5 names its comparison, 6 carries its confounders and 8
 * tells its four nothings apart - and they are judged by
 * `support/panel-gates.ts`, the same code for a real panel and for the witness.
 *
 * **The gates judge an opt-in list.** Each route's console file names the
 * panels held to them, and a panel joins it in the pull request that redraws
 * it: the attributes three of the gates read exist on no panel yet, so judging
 * every panel would make the gates red on the day they landed, and a gate that
 * is red on arrival is a gate people learn to skip.
 *
 * **So the gates are proven on a witness first.** `fixtures/panels/WitnessPanel.svelte`
 * draws the real panel frame, the real trend and the real empty states. One
 * set of props clears all six gates at every width in both themes, and each
 * bad set moves one thing a real panel could get wrong - and fails that gate
 * and no other, which is checked rather than claimed. A gate that no input can
 * fail, or that a bad input fails for the wrong gate's reason, shows up here.
 */

const here = path.dirname(fileURLToPath(import.meta.url));
const frontend = path.resolve(here, '..');

const THEMES = ['light', 'dark'] as const;
type Theme = (typeof THEMES)[number];

/** The width the four nothings are compared at: the narrowest, where a box
 * standing in for a chart has the least room to say which nothing it is. */
const NOTHING_WIDTH = CONSOLE_WIDTHS[CONSOLE_WIDTHS.length - 1];

// --- The witness ---------------------------------------------------------

const DAYS = 14;
const minutes = Array.from({ length: DAYS }, (_, at) => ({
	date: `2026-09-${String(at + 1).padStart(2, '0')}`,
	value: 3 + ((at * 7) % 5) / 2
}));
const trend = dateSeries([{ label: 'Minutes', token: '--chart-1', points: minutes }], {
	frame: frame(760, 220),
	density: 6,
	valueTicks: 4,
	padding: 0.2,
	rule: { changes: [], note: null }
});

/** Every nothing drawn the way `waiting.ts` words it. */
const FOUR_NOTHINGS: Record<BasicNothing, EmptyDrawing> = {
	loading: emptyState('loading'),
	quiet: emptyState('quiet', quietSentence(DAYS, 30)),
	missing: emptyState('missing', missingSentence(['2026-08'])),
	unreachable: emptyState('unreachable', unreachableSentence(['2026-09'], 0))
};

interface Witness {
	props: Record<string, unknown>;
	/** Paint the page the colour of a panel, which no console page does. */
	flatPage?: boolean;
	nothings: Record<BasicNothing, EmptyDrawing>;
}

const GOOD: Witness = {
	props: {
		id: 'witness',
		title: 'Minutes to write one summary',
		note: 'The last fourteen days, one line a day.',
		geometry: trend,
		lede: '4.2 min',
		comparison: 'minutes to write one summary this fortnight against the fortnight before',
		ruleNote: noModelRuleNote(DAYS)
	},
	nothings: FOUR_NOTHINGS
};

const moved = (props: Record<string, unknown>, extra: Partial<Witness> = {}): Witness => ({
	...GOOD,
	...extra,
	props: { ...GOOD.props, ...props }
});

/** One change each, and the one gate each change must fail. The plot's
 * share is set against the floor the config names, so the bad input stays
 * under it wherever the floor is moved to. */
const BAD: { gate: GateNumber; what: string; witness: (floor: number) => Witness }[] = [
	{ gate: 1, what: 'a plot drawn across too little of the panel', witness: (floor) => moved({ plotShare: floor * 0.7 }) },
	{ gate: 2, what: 'a panel the colour of the page under it', witness: () => moved({}, { flatPage: true }) },
	{ gate: 2, what: 'a ground of its own under the plot', witness: () => moved({ plotTinted: true }) },
	{ gate: 3, what: 'two elements marked to land first', witness: () => moved({ ledes: 2 }) },
	{
		gate: 5,
		what: 'a subject where the comparison should be',
		witness: () => moved({ comparison: 'minutes to write one summary' })
	},
	{ gate: 6, what: 'a trend with no settings-change declaration', witness: () => moved({ ruleNote: null }) },
	{
		gate: 8,
		what: 'a failed fetch drawn through the quiet branch',
		witness: () => moved({}, { nothings: { ...FOUR_NOTHINGS, unreachable: FOUR_NOTHINGS.quiet } })
	}
];

test.describe('the witness panel', () => {
	let witness: (props: Record<string, unknown>) => string;
	let styles = '';

	test.beforeAll(async ({}, testInfo) => {
		// One directory a worker: these tests may run side by side, and a module
		// rewritten while another worker imports it is read half-written.
		const built = path.join(frontend, 'test-results', 'panel-witness', String(testInfo.workerIndex));
		const compiled = serverCompiler(built);
		await compiled('src/lib/components/Reserved.svelte', 'Reserved', []);
		await compiled('src/lib/charts/d3/EmptyState.svelte', 'EmptyState', [
			['$lib/components/Reserved.svelte', './Reserved.server.mjs']
		]);
		await compiled('src/lib/components/ChartReadout.svelte', 'ChartReadout', []);
		await compiled('src/lib/charts/d3/DateSeries.svelte', 'DateSeries', [
			['./EmptyState.svelte', './EmptyState.server.mjs'],
			['$lib/components/ChartReadout.svelte', './ChartReadout.server.mjs']
		]);
		await compiled('src/lib/components/Panel.svelte', 'Panel', []);
		const module = await compiled('tests/fixtures/panels/WitnessPanel.svelte', 'WitnessPanel', [
			['$lib/components/Panel.svelte', './Panel.server.mjs'],
			['$lib/charts/d3/DateSeries.svelte', './DateSeries.server.mjs']
		]);
		const loaded = await import(pathToFileURL(module).href);
		witness = (props) => render(loaded.default, { props }).body;
		// The real tokens and the real page ground, then each component's own CSS.
		// `app.css` is read as written: the browser skips the at-rules only the
		// build understands and keeps the ones that paint the page.
		styles = [
			readFileSync(path.join(frontend, 'src', 'styles', 'tokens.css'), 'utf8'),
			readFileSync(path.join(frontend, 'src', 'styles', 'app.css'), 'utf8'),
			...compiled.css.values()
		].join('\n');
	});

	async function mounted(
		page: Page,
		props: Record<string, unknown>,
		width: number,
		theme: Theme,
		flatPage = false
	): Promise<PanelReading> {
		await page.setViewportSize({ width, height: CONSOLE_WINDOW_HEIGHT });
		const flatGround = flatPage ? 'html { background-color: var(--color-surface); }' : '';
		await page.setContent(
			`<!doctype html><html data-theme="${theme}"><head><meta charset="utf-8">` +
				`<style>${styles}</style><style>.witness-page { padding: var(--space-4); } ${flatGround}</style>` +
				`</head><body><main class="witness-page">${witness(props)}</main></body></html>`,
			{ waitUntil: 'domcontentloaded' }
		);
		return readPanel(page.locator('[data-console-panel-id="witness"]'));
	}

	/** Every decidable gate over one witness: the settled panel at every view
	 * `viewsOf` names, and its four nothings at the narrowest width in both themes. */
	async function judged(page: Page, input: Witness, floor: number): Promise<Verdict[]> {
		const verdicts: Verdict[] = [];
		for (const { width, theme } of viewsOf(CONSOLE_WIDTHS, THEMES)) {
			const reading = await mounted(page, { ...input.props, empty: input.nothings.quiet }, width, theme, input.flatPage);
			verdicts.push(...judgeSettled(reading, floor));
		}
		for (const theme of THEMES) {
			const readings = {} as Record<Nothing, PanelReading>;
			for (const state of NOTHINGS) {
				readings[state] = await mounted(
					page,
					{ ...input.props, geometry: null, empty: input.nothings[state] },
					NOTHING_WIDTH,
					theme,
					input.flatPage
				);
			}
			verdicts.push(judgeNothings('witness', readings));
		}
		return verdicts;
	}

	const failed = (verdicts: Verdict[]): GateNumber[] =>
		[...new Set(verdicts.filter((verdict) => !verdict.pass).map((verdict) => verdict.gate))].sort((a, b) => a - b);

	test('the good witness clears every decidable gate at every view', async ({ page }) => {
		const verdicts = await judged(page, GOOD, consolePanels().fillFloor);
		for (const verdict of verdicts) console.log(`gate ${verdict.gate}: ${verdict.says}`);
		expect(
			verdicts.filter((verdict) => !verdict.pass).map((verdict) => `gate ${verdict.gate}: ${verdict.says}`),
			'the good witness failed a gate'
		).toEqual([]);
		// Every gate spoke, so a gate that returned nothing cannot pass here.
		expect([...new Set(verdicts.map((verdict) => verdict.gate))].sort((a, b) => a - b)).toEqual([1, 2, 3, 5, 6, 8]);
	});

	for (const bad of BAD) {
		test(`${bad.what} fails gate ${bad.gate} and no other`, async ({ page }) => {
			const floor = consolePanels().fillFloor;
			const verdicts = await judged(page, bad.witness(floor), floor);
			for (const verdict of verdicts.filter((one) => !one.pass)) console.log(`gate ${verdict.gate}: ${verdict.says}`);
			expect(failed(verdicts), `${bad.what} should fail gate ${bad.gate} alone`).toEqual([bad.gate]);
		});
	}
});

// --- The panels the console has opted in ---------------------------------

function declarationFor(
	route: RouteId,
	id: string,
	byRoute: Readonly<Record<RouteId, RouteDrivers>> = BY_ROUTE
): PanelDrivers | null {
	const { DRIVERS, BUILD_TIME } = byRoute[route];
	const driven = Object.hasOwn(DRIVERS, id);
	const built = BUILD_TIME.includes(id);
	if (driven === built) {
		throw new Error(
			`config/console/${route}.json judges ${id}, and panel-drivers/${route}.ts declares it in ` +
				`${driven ? 'both DRIVERS and BUILD_TIME' : 'neither DRIVERS nor BUILD_TIME'}`
		);
	}
	return driven ? DRIVERS[id] : null;
}

/** Every judged id has one owner and one complete declaration before any gate runs. */
function validateDrivers(
	panels: ConsolePanels,
	byRoute: Readonly<Record<RouteId, RouteDrivers>> = BY_ROUTE
): void {
	const drivenOn = new Map<string, RouteId>();
	for (const { id: route } of BAND_UNREAD.routes) {
		for (const id of Object.keys(byRoute[route].DRIVERS)) {
			const other = drivenOn.get(id);
			if (other !== undefined) {
				throw new Error(`${id} is driven twice, by panel-drivers/${other}.ts and panel-drivers/${route}.ts`);
			}
			drivenOn.set(id, route);
		}
	}
	for (const { key: route, judged } of panels.routes) {
		const { DRIVERS, BUILD_TIME } = byRoute[route];
		if (new Set(BUILD_TIME).size !== BUILD_TIME.length) {
			throw new Error(`panel-drivers/${route}.ts repeats an id in BUILD_TIME`);
		}
		for (const id of [...Object.keys(DRIVERS), ...BUILD_TIME]) {
			if (!judged.includes(id)) {
				throw new Error(`panel-drivers/${route}.ts declares ${id}, which config/console/${route}.json does not judge`);
			}
		}
		for (const id of judged) {
			const driver = declarationFor(route, id, byRoute);
			if (driver === null) continue;
			for (const state of NOTHINGS) {
				if (typeof driver[state] !== 'function') {
					throw new Error(`panel-drivers/${route}.ts names ${id} but has no ${state} driver`);
				}
			}
		}
	}
}

async function opened(page: Page, address: string, width: number, theme: Theme): Promise<void> {
	await page.setViewportSize({ width, height: CONSOLE_WINDOW_HEIGHT });
	await page.addInitScript((chosen) => localStorage.setItem('idhazh:theme', chosen), theme);
	await page.goto(address);
	await expect(page.locator('html')).toHaveAttribute('data-theme', theme);
}

/** The panel, near enough to be drawn and done waiting for its rows. */
async function settled(page: Page, id: string) {
	const panel = page.locator(`[data-console-panel-id="${id}"]`);
	await expect(panel, `the page draws no panel with the id ${id}`).toHaveCount(1);
	await panel.evaluate((node) => node.scrollIntoView({ block: 'center', behavior: 'instant' }));
	await expect(
		panel.locator('[data-chart="waiting"], [data-panel-state="loading"], [data-empty-state="loading"]'),
		`${id} is still waiting for its rows`
	).toHaveCount(0, { timeout: 20_000 });
	return panel;
}

async function settledExplorer(page: Page, width: number, theme: Theme): Promise<void> {
	await page.setViewportSize({ width, height: CONSOLE_WINDOW_HEIGHT });
	await page.addInitScript((chosen) => localStorage.setItem('idhazh:theme', chosen), theme);
	await openExplorer(page, PINNED);
	await expect(page.locator('html')).toHaveAttribute('data-theme', theme);
	await chooseExplorerQuestion(page, ['published'], "SELECT * FROM (VALUES (DATE '2026-08-18', 3), (DATE '2026-08-19', 5), (DATE '2026-08-20', 8)) AS t(date, rows)");
	await runExplorer(page);
}

test.describe('the judged panels', () => {
	test('every judged panel has exactly one complete state declaration on its own route', () => {
		validateDrivers(consolePanels());
	});

	for (const { id: route, href: address } of BAND_UNREAD.routes) {
		for (const { width, theme } of CONSOLE_WIDTHS.flatMap((width) => THEMES.map((theme) => ({ width, theme })))) {
			test(`every ${route} judged panel clears gates 1, 2, 3, 5 and 6 at ${width} in ${theme}`, async ({ page }) => {
				const panels = consolePanels();
				validateDrivers(panels);
				const { judged } = panels.routes.find((one) => one.key === route)!;
				test.info().annotations.push({ type: 'judged panels', description: `${judged.length}: ${judged.join(', ') || 'none yet'}` });
				test.skip(judged.length === 0, `config/console/${route}.json judges no panels`);
				if (route === 'data-explorer') await settledExplorer(page, width, theme);
				else await opened(page, address, width, theme);
				for (const id of judged) {
					await showPanel(page, id);
					const reading = await readPanel(await settled(page, id));
					const verdicts = judgeSettled(reading, panels.fillFloor).filter((verdict) =>
						!(id.startsWith('data-explorer-') && (verdict.gate === 3 || verdict.gate === 5))
					);
					for (const verdict of verdicts) {
						console.log(`${width} ${theme} gate ${verdict.gate}: ${verdict.says}`);
						expect.soft(verdict.pass, `${width} ${theme} gate ${verdict.gate}: ${verdict.says}`).toBe(true);
					}
				}
			});
		}

		if (Object.keys(BY_ROUTE[route].DRIVERS).length === 0) continue;
		for (const theme of THEMES) {
			test(`every ${route} driven panel draws distinct nothings in ${theme}`, async ({ page }) => {
				const panels = consolePanels();
				validateDrivers(panels);
				const { judged } = panels.routes.find((one) => one.key === route)!;
				const driven = judged.filter((id) => declarationFor(route, id) !== null);
				test.skip(driven.length === 0, `config/console/${route}.json judges no driven panels`);
				const readings = new Map(driven.map((id) => [id, {} as Record<Nothing, PanelReading>]));
				// Keep the explorer's fifth state on the last load: a refused question is not a failed fetch.
				const states = route === 'data-explorer' ? REFUSED_NOTHINGS : NOTHINGS;
				for (const state of states) {
					const prepared: Awaited<ReturnType<Driver>>[] = [];
					try {
						await page.unrouteAll({ behavior: 'ignoreErrors' });
						const drivers = new Set<Driver>();
						for (const id of driven) {
							const driver = declarationFor(route, id)![state];
							if (typeof driver !== 'function') throw new Error(`panel-drivers/${route}.ts names ${id} but has no ${state} driver`);
							drivers.add(driver);
						}
						for (const driver of drivers) prepared.push(await driver(page));
						if (state !== 'refused') await opened(page, address, NOTHING_WIDTH, theme);
						for (const driver of prepared) await driver?.afterOpen?.();
						for (const id of driven) {
							const panel = page.locator(`[data-console-panel-id="${id}"]`);
							await expect(panel, `the page draws no panel with the id ${id}`).toHaveCount(1);
							await showPanel(page, id);
							await panel.evaluate((node) => node.scrollIntoView({ block: 'center', behavior: 'instant' }));
							const selector = route === 'data-explorer'
								? state === 'loading' ? '.shimmer, [data-state="loading"]' : `[data-state="${state}"]`
								: state === 'loading' ? '[data-panel-state="loading"]' : `[data-empty-state="${state}"]`;
							await expect(panel.locator(selector)).toHaveCount(1);
							readings.get(id)![state] = await readPanel(panel);
						}
					} finally {
						for (const driver of prepared) await driver?.afterRead?.();
					}
				}
				for (const id of driven) {
					const verdict = judgeNothings(id, readings.get(id)!, states);
					console.log(`${theme} gate 8: ${verdict.says}`);
					expect.soft(verdict.pass, `${theme} gate 8: ${verdict.says}`).toBe(true);
				}
			});
		}
	}

	test('a judged panel nothing here can put into its four nothings is refused by name', () => {
		expect(() => declarationFor('pipelines', 'a-panel-nobody-drew')).toThrow(/a-panel-nobody-drew/);
	});

	test('a judged panel declared as both driven and build-time is refused by name', () => {
		const byRoute = { ...BY_ROUTE, machine: { ...BY_ROUTE.machine, BUILD_TIME: ['platform-mix'] } };
		expect(() => declarationFor('machine', 'platform-mix', byRoute)).toThrow(/platform-mix.*both DRIVERS and BUILD_TIME/);
	});

	test('a panel two route modules drive is refused by name', () => {
		const byRoute = {
			...BY_ROUTE,
			voices: { ...BY_ROUTE.voices, DRIVERS: { 'platform-mix': BY_ROUTE.machine.DRIVERS['platform-mix'] } }
		};
		expect(() => validateDrivers(consolePanels(), byRoute)).toThrow(/platform-mix is driven twice/);
	});
});

// --- The Data explorer's chart once the reader has chosen -----------------

/** One answer each of the four charts can draw: a row a UTC day, a name a row, three numbers. */
const EVERY_CHART_SQL = "SELECT DATE '2026-01-01' + i::INTEGER AS day, 'n' || i::VARCHAR AS name, i AS across, 200 - i AS up, 2 * i AS other FROM range(0, 170) AS t(i)";

/** A choice the page would not make, for each chart: its tile, then a column its role does not open on. */
const CHOICES = [
	{ type: 'dateSeries', role: 'lines', column: 'other', said: 'Lines: across, up' },
	{ type: 'rankedList', role: 'rankBy', column: 'up', said: 'Rank by: up' },
	{ type: 'pairedScatter', role: 'across', column: 'other', said: 'Across: other' },
	{ type: 'distribution', role: 'values', column: 'other', said: 'Values: other' }
] as const;

test('T10: after a choice the page would not make, each of the four charts passes gates 1, 3, 4, 5 and 9 at every width, in both themes', async ({ page }) => {
	const { fillFloor } = consolePanels();
	for (const { width, theme } of viewsOf(CONSOLE_WIDTHS, THEMES)) {
		await page.setViewportSize({ width, height: CONSOLE_WINDOW_HEIGHT });
		await page.addInitScript((chosen) => localStorage.setItem('idhazh:theme', chosen), theme);
		await openExplorer(page, PINNED);
		await chooseExplorerQuestion(page, ['published'], EVERY_CHART_SQL);
		await runExplorer(page);
		await showPanel(page, 'data-explorer-shape');
		const panel = page.locator('[data-console-panel-id="data-explorer-shape"]');
		for (const { type, role, column, said } of CHOICES) {
			const label = `${width} ${theme} ${type}`;
			await page.locator(`[data-shape-choice="${type}"]`).click();
			const pill = panel.locator(`[data-chart-roles] .column-picker[data-role="${role}"]`);
			await pill.locator('summary').click();
			await pill.locator(`[data-column="${column}"] input`).click();
			if (await pill.locator('[data-pill-list]').isVisible()) await page.keyboard.press('Escape');
			await expect(pill.locator('summary'), `${label}: the choice was not made`).toHaveAttribute('aria-label', said);
			await expect(panel.locator(`[data-chart-type="${type}"]`), `${label}: the chart was not drawn`).toHaveCount(1);
			const reading = await readPanel(panel);
			for (const verdict of [judgeFill(reading, fillFloor), judgeLede(reading), judgeComparison(reading)]) {
				console.log(`${label} gate ${verdict.gate}: ${verdict.says}`);
				expect.soft(verdict.pass, `${label} gate ${verdict.gate}: ${verdict.says}`).toBe(true);
			}
			// Gate 4, as far as a selector can read it: no native tooltip on a mark.
			await expect.soft(panel.locator('[title], title'), `${label} gate 4: a mark carries a native tooltip`).toHaveCount(0);
			// Gate 9: the readout strip is declared and drawn.
			await expect.soft(panel.locator('[data-readout] [data-readout-row]').first(), `${label} gate 9: no readout strip is drawn`).toBeVisible();
		}
	}
});

const ADDED_CHARTS = [
	{ type: 'partsOfOne', sql: "SELECT * FROM (VALUES ('first', 10, 8, 2), ('last', 8, 6, 2)) AS t(stage, arrived, went, lost)" },
	{ type: 'tileStrip', sql: "SELECT * FROM (VALUES (DATE '2026-08-17', true), (DATE '2026-08-18', false), (DATE '2026-08-19', NULL::BOOLEAN), (DATE '2026-08-20', true)) AS t(day, ok)" },
	{ type: 'flow', sql: "SELECT * FROM (VALUES ('first', 10, 8, 2), ('last', 8, 6, 2)) AS t(stage, arrived, went, lost)" }
] as const;

for (const width of [390, 768, 1024, 1440]) for (const theme of THEMES) {
	test(`row20: three real reused charts pass sufficiency and keyboard readouts at ${width}px in ${theme}`, async ({ page }, info) => {
		await page.setViewportSize({ width, height: width === 390 ? 844 : width === 768 ? 1024 : 900 });
		await page.addInitScript((chosen) => localStorage.setItem('idhazh:theme', chosen), theme);
		await openExplorer(page, PINNED);
		const failures: string[] = [];
		page.on('pageerror', (error) => failures.push(error.message));
		page.on('console', (message) => { if (message.type() === 'error') failures.push(message.text()); });
		page.on('response', (response) => { if (response.status() === 404) failures.push(`404 ${new URL(response.url()).pathname}`); });
		const panel = page.locator('[data-console-panel-id="data-explorer-shape"]');
		await chooseExplorerQuestion(page, ['published'], ADDED_CHARTS[0].sql);
		for (const [index, { type, sql }] of ADDED_CHARTS.entries()) {
			if (index > 0) {
				await page.locator('#explorer-sql').fill(sql);
				await expect(page.getByRole('button', { name: /^Run$/ })).toBeEnabled({ timeout: 60_000 });
			}
			await runExplorer(page);
			await showPanel(page, 'data-explorer-shape');
			await page.locator(`[data-shape-choice="${type}"]`).click();
			const plot = panel.locator(`[data-chart-type="${type}"]`);
			await expect(plot).toBeVisible();
			for (const verdict of [judgeFill(await readPanel(panel), consolePanels().fillFloor), judgeLede(await readPanel(panel)), judgeComparison(await readPanel(panel))]) {
				expect(verdict.pass, verdict.says).toBe(true);
			}
			await expect(panel.locator('[title], title')).toHaveCount(0);
			await expect(panel.locator('[data-readout]')).toBeVisible();
			if (type === 'tileStrip') {
				await expect(panel.locator('[data-model-rule="no"]')).toHaveAttribute('data-model-rule-none', 'this page does not know which settings changed inside your span');
				await expect(plot.locator('[data-tile-state]')).toHaveCount(4);
				await expect(plot.locator('[data-tile-state="absent"]')).toHaveCount(1);
				await plot.focus();
				await page.keyboard.press('Home');
				await expect(panel.locator('[data-readout]')).toContainText('true');
				await page.keyboard.press('ArrowRight');
				await expect(panel.locator('[data-readout]')).toContainText('false');
				await page.keyboard.press('ArrowRight');
				await expect(panel.locator('[data-readout]')).toContainText('null');
			} else if (type === 'partsOfOne') {
				await expect(plot).toHaveAttribute('data-parts-overlapping', 'yes');
				await expect(plot.locator('.parts-total')).toHaveCount(0);
				await plot.locator('ol').focus();
				await page.keyboard.press('End');
				await expect(panel.locator('[data-readout-subject]')).toContainText('last');
			} else {
				const expected = await plot.evaluate((node) => node.getBoundingClientRect().width < 640 ? 'stepped' : 'diagram');
				await expect(plot).toHaveAttribute('data-flow-shape', expected);
				if (expected === 'diagram') {
					const dimensions = { width: Number(await plot.getAttribute('width')), height: Number(await plot.getAttribute('height')) };
					const shared = flow([{ label: 'first', arrived: 10, left: 8, drops: [{ label: 'lost', count: 2 }] }, { label: 'last', arrived: 8, left: 6, drops: [{ label: 'lost', count: 2 }] }], { frame: frame(dimensions.width, dimensions.height), narrow: false, nodeWidth: 12, nodeGap: 8 });
					expect(shared?.kind).toBe('diagram');
					if (shared?.kind === 'diagram') {
						const drawn = await plot.locator('rect').evaluateAll((nodes) => nodes.map((node) => ['x', 'y', 'width', 'height'].map((name) => Number(node.getAttribute(name)))));
						expect(drawn).toEqual(shared.nodes.map((node) => [node.x, node.y, node.width, node.height]));
					}
					expect(await plot.locator('rect').first().getAttribute('width')).toBe('12');
					if (width === 1440) {
						await panel.evaluate((node) => { (node as HTMLElement).style.setProperty('--space-3', '1rem'); (node as HTMLElement).style.setProperty('--space-2', '0.75rem'); });
						await expect(plot.locator('rect').first()).toHaveAttribute('width', '16');
						await panel.evaluate((node) => { (node as HTMLElement).style.removeProperty('--space-3'); (node as HTMLElement).style.removeProperty('--space-2'); });
						await expect(plot.locator('rect').first()).toHaveAttribute('width', '12');
					}
					await plot.focus();
				} else await plot.locator('ol').focus();
				await page.keyboard.press('End');
				await expect(panel.locator('[data-readout-subject]')).toContainText('last');
			}
			await panel.screenshot({ path: info.outputPath(`row20-${type}-${width}-${theme}.png`) });
		}
		// The module's own counts-not-one-flow fallback, even on a wide window.
		await chooseExplorerQuestion(page, ['published'], "SELECT * FROM (VALUES ('first', 10, 9, 2), ('last', 8, 6, 2)) AS t(stage, arrived, went, lost)");
		await runExplorer(page);
		await expect(panel.locator('[data-flow-shape="stepped"]')).toBeVisible();
		await expect(panel).toContainText('first counts 10 arriving and 11 leaving, so the counts are not one flow and the stages are listed rather than drawn.');
		await expect(panel.locator('[data-lede]')).toHaveText('last: 6 went');
		await panel.screenshot({ path: info.outputPath(`row20-flow-list-${width}-${theme}.png`) });
		if (width === 1440) {
			await chooseExplorerQuestion(page, ['published'], "SELECT 'Only stage' AS stage, 10 AS arrived, 10 AS went, 0 AS lost");
			await runExplorer(page);
			const single = panel.locator('[data-flow-shape="diagram"]');
			await expect(single).toBeVisible();
			const label = single.locator('text');
			await expect(label).toHaveText('Only stage 10');
			const plotBox = (await single.boundingBox())!;
			const labelBox = (await label.boundingBox())!;
			expect(labelBox.x).toBeGreaterThanOrEqual(plotBox.x);
			expect(labelBox.x + labelBox.width).toBeLessThanOrEqual(plotBox.x + plotBox.width);
		}
		const cap = explorerConfig().rank_max;
		await chooseExplorerQuestion(page, ['published'], `SELECT i::VARCHAR AS stage, CASE WHEN i < ${cap} THEN 0 ELSE 10 END AS arrived, 0 AS went FROM range(0, ${cap + 1}) AS t(i)`);
		await runExplorer(page);
		await page.locator('[data-shape-choice="partsOfOne"]').click();
		await expect(panel.locator('[data-shape-none]')).toHaveText(`Nothing here to draw: every bar you checked is 0 or null in the first ${cap} rows. The remaining rows are in the table.`);
		await page.goto('/console/');
		await expect(page.locator('main')).toBeVisible();
		expect(failures).toEqual([]);
	});
}
