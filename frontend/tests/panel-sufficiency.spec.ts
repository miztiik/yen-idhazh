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
import { consolePanels, CONSOLE_ROUTE_PATHS } from './support/console-panels';
import { chooseExplorerQuestion, openExplorer, runExplorer } from './support/explorer-answer';
import { CONSOLE_WIDTHS, CONSOLE_WINDOW_HEIGHT } from './support/console-widths';
import { machineRecordState } from './support/machine-record-state';
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
	readPanel,
	type GateNumber,
	type Nothing,
	type PanelReading,
	type Verdict
} from './support/panel-gates';
import { serverCompiler } from './support/server-render';
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
 * **The gates judge an opt-in list.** `console.judged_panel_ids` names the
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
	padding: 0.2
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

type Driver = (page: Page) => Promise<void>;

/** How a judged panel is put into each of its four nothings on its own route.
 *
 * Keyed by panel id, and set up before the route is opened: each one answers
 * the panel's own data requests the way that nothing would. A panel joins
 * `console.judged_panel_ids` with its entry here, in the same pull request -
 * the requests a panel makes are its own, so nothing here can guess them.
 */
const DRIVERS: Record<string, Record<BasicNothing, Driver>> = {
	'platform-mix': {
		loading: (page) => machineRecordState(page, 'loading'),
		missing: (page) => machineRecordState(page, 'missing'),
		quiet: (page) => machineRecordState(page, 'quiet'),
		unreachable: (page) => machineRecordState(page, 'unreachable')
	}
};

function driverFor(id: string): Record<BasicNothing, Driver> {
	const driver = DRIVERS[id];
	if (driver === undefined) {
		throw new Error(
			`console.judged_panel_ids names ${id}, and nothing here can put it into its four nothings - ` +
				`add its entry to DRIVERS in frontend/tests/panel-sufficiency.spec.ts in the pull request that judges it`
		);
	}
	return driver;
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

async function settledExplorer(page: Page, id: string, width: number, theme: Theme): Promise<PanelReading> {
	await page.setViewportSize({ width, height: CONSOLE_WINDOW_HEIGHT });
	await page.addInitScript((chosen) => localStorage.setItem('idhazh:theme', chosen), theme);
	await openExplorer(page, PINNED);
	await chooseExplorerQuestion(page, ['published'], "SELECT * FROM (VALUES (DATE '2026-08-18', 3), (DATE '2026-08-19', 5), (DATE '2026-08-20', 8)) AS t(date, rows)");
	await runExplorer(page);
	if (id === 'data-explorer-shape') await showPanel(page, id);
	return readPanel(await settled(page, id));
}

async function explorerNothing(page: Page, id: string, state: Nothing, theme: Theme): Promise<PanelReading> {
	await page.unrouteAll({ behavior: 'ignoreErrors' });
	await page.setViewportSize({ width: NOTHING_WIDTH, height: CONSOLE_WINDOW_HEIGHT });
	await page.addInitScript((chosen) => localStorage.setItem('idhazh:theme', chosen), theme);
	if (state === 'unreachable') await page.route('**/state/**/*.parquet*', (route) => route.abort());
	await openExplorer(page, PINNED);
	if (state === 'loading') {
		await chooseExplorerQuestion(page, ['published'], 'SELECT count(*) AS rows FROM "published"', false);
		let release!: () => void;
		const held = new Promise<void>((resolve) => { release = resolve; });
		await page.route('**/state/**/*.parquet*', async (route) => {
			await held;
			await route.continue();
		}, { times: 1 });
		if (id === 'data-explorer-shape') await showPanel(page, id);
		await page.getByRole('button', { name: /^Run$/ }).click();
		const panel = page.locator(`[data-console-panel-id="${id}"]`);
		await expect(panel.locator('.shimmer, [data-state="loading"]')).toHaveCount(1);
		const reading = await readPanel(panel);
		release();
		return reading;
	}
	const sql =
		state === 'quiet' ? 'SELECT * FROM "published" WHERE false' :
		state === 'missing' ? 'SELECT count(*) AS rows FROM "feed-health"' :
		state === 'refused' ? 'SELECT 1; SELECT 2' :
		'SELECT count(*) AS rows FROM "published"';
	const ledgers = state === 'missing' ? (['feed-health'] as const) : (['published'] as const);
	await chooseExplorerQuestion(page, ledgers, sql, false);
	await runExplorer(page);
	if (id === 'data-explorer-shape') await showPanel(page, id);
	const panel = page.locator(`[data-console-panel-id="${id}"]`);
	await expect(panel.locator(state === 'refused' ? '[data-state="refused"]' : `[data-state="${state}"]`)).toHaveCount(1);
	return readPanel(panel);
}

test.describe('the judged panels', () => {
	test('every judged panel clears gates 1, 2, 3, 5 and 6 at every view', async ({ page }) => {
		const { judged, routeOf, fillFloor } = consolePanels();
		test.info().annotations.push({ type: 'judged panels', description: `${judged.length}: ${judged.join(', ') || 'none yet'}` });
		for (const id of judged) {
			const address = CONSOLE_ROUTE_PATHS[routeOf.get(id) ?? ''];
			for (const { width, theme } of viewsOf(CONSOLE_WIDTHS, THEMES)) {
				const reading = id.startsWith('data-explorer-')
					? await settledExplorer(page, id, width, theme)
					: (await opened(page, address, width, theme), await readPanel(await settled(page, id)));
				const verdicts = judgeSettled(reading, fillFloor).filter((verdict) =>
					!(id.startsWith('data-explorer-') && (verdict.gate === 3 || verdict.gate === 5))
				);
				for (const verdict of verdicts) {
					console.log(`${width} ${theme} gate ${verdict.gate}: ${verdict.says}`);
					expect.soft(verdict.pass, `${width} ${theme} gate ${verdict.gate}: ${verdict.says}`).toBe(true);
				}
			}
		}
	});

	test('every judged panel draws its four nothings as four different pictures', async ({ page }) => {
		const { judged, routeOf } = consolePanels();
		for (const id of judged) {
			const address = CONSOLE_ROUTE_PATHS[routeOf.get(id) ?? ''];
			for (const theme of THEMES) {
				const readings = {} as Record<Nothing, PanelReading>;
				const states = id.startsWith('data-explorer-') ? REFUSED_NOTHINGS : NOTHINGS;
				if (id.startsWith('data-explorer-')) {
					for (const state of states) readings[state] = await explorerNothing(page, id, state, theme);
				} else {
					const driver = driverFor(id);
					for (const state of NOTHINGS) {
						await page.unrouteAll({ behavior: 'ignoreErrors' });
						await driver[state](page);
						await opened(page, address, NOTHING_WIDTH, theme);
						const panel = page.locator(`[data-console-panel-id="${id}"]`);
						await expect(panel, `the page draws no panel with the id ${id}`).toHaveCount(1);
						await panel.evaluate((node) => node.scrollIntoView({ block: 'center', behavior: 'instant' }));
						await expect(panel.locator(state === 'loading'
							? '[data-panel-state="loading"]'
							: `[data-empty-state="${state}"]`)).toHaveCount(1);
						readings[state] = await readPanel(panel);
					}
				}
				const verdict = judgeNothings(id, readings, states);
				console.log(`${theme} gate 8: ${verdict.says}`);
				expect.soft(verdict.pass, `${theme} gate 8: ${verdict.says}`).toBe(true);
			}
		}
	});

	test('a judged panel nothing here can put into its four nothings is refused by name', () => {
		// The list is empty until a panel is redrawn to the gates, so the refusal
		// above runs on nothing; this is the case that proves it would refuse.
		expect(() => driverFor('a-panel-nobody-drew')).toThrow(/a-panel-nobody-drew/);
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
		for (const { type, sql } of ADDED_CHARTS) {
			await chooseExplorerQuestion(page, ['published'], sql);
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
		await page.goto('/console/');
		await expect(page.locator('main')).toBeVisible();
		expect(failures).toEqual([]);
	});
}
