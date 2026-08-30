import { expect, test, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { monthsToFetch, stepPreset, windowOfDays } from '../src/lib/charts/viewport';

/**
 * One window, and every section that follows it saying the same number.
 *
 * The console used to let each section pick its own span: the viewport opened
 * on whatever fitted the rows, the source table hard-coded seven days, and
 * nothing on the page said either number out loud. Two charts on two windows
 * cannot be compared, which is the question an operator came here to ask.
 *
 * The oracle below is the row's whole point. It drives the control to each
 * preset in turn and asserts that every windowed surface reports that same day
 * count in its own description. A surface that disagrees with the control fails.
 */

const CONFIG = JSON.parse(
	readFileSync(resolve(process.cwd(), '..', 'config', 'appearance.json'), 'utf8')
) as { console?: { window_presets?: number[]; default_window_days?: number } };

const PRESETS = CONFIG.console?.window_presets ?? [7, 14, 30, 90];
const DEFAULT_DAYS = CONFIG.console?.default_window_days ?? 30;

/** The span the retirement rule is stated over, from the module that owns it. */
const RULE_DAYS = 14;

async function hydrated(page: Page) {
	// Disabled in the prerendered document and enabled on mount, so waiting for
	// it is waiting for the control to be able to do anything at all.
	await expect(page.locator(`[data-window-preset="${DEFAULT_DAYS}"] input`)).toBeEnabled();
}

async function setWindow(page: Page, days: number) {
	// The label is the target, not the 1px input inside it - that is what a
	// person clicks and what a thumb can hit.
	await page.locator(`[data-window-preset="${days}"]`).click();
	await expect(page.locator('[data-window-control]')).toHaveAttribute(
		'data-window-days',
		String(days)
	);
}

/** Every surface that claims to follow the window, and what it says it shows. */
async function windowed(page: Page) {
	return page.locator('[data-windowed]').evaluateAll((nodes) =>
		nodes.map((node) => ({
			name: node.getAttribute('data-windowed') ?? '',
			days: Number(node.getAttribute('data-window-days')),
			// A label where there is one, and the words on the surface otherwise.
			// Both are what somebody reading the page is given.
			says: `${node.getAttribute('aria-label') ?? ''} ${node.textContent ?? ''}`.replace(
				/\s+/g,
				' '
			)
		}))
	);
}

test('a window of N days is exactly N days, whatever the ledger holds', () => {
	// It used to shrink to the rows it found. That was invisible while nothing
	// named the span and a lie the moment a control does: a page reading 90 while
	// the charts draw 2 cannot be trusted about anything else.
	const short = ['2026-08-27', '2026-08-28'];
	expect(windowOfDays(short, '2026-08-28', 30, 'right')).toEqual({
		start: '2026-07-30',
		end: '2026-08-28'
	});
	expect(windowOfDays(short, '2026-08-28', 7, 'right')).toEqual({
		start: '2026-08-22',
		end: '2026-08-28'
	});
	// With nothing on record at all it hangs off the build clock instead.
	expect(windowOfDays([], '2026-08-28', 7, 'right')).toEqual({
		start: '2026-08-22',
		end: '2026-08-28'
	});
	// Centred pushes the end past the newest day, which is the anchor's whole
	// purpose: room on the right for days that have not happened yet.
	expect(windowOfDays(short, '2026-08-28', 7, 'centre').end).toBe('2026-08-31');
});

test('a step lands on a preset, and stops at the ends rather than wrapping', () => {
	expect(stepPreset(30, PRESETS, 1)).toBe(90);
	expect(stepPreset(30, PRESETS, -1)).toBe(14);
	expect(stepPreset(90, PRESETS, 1)).toBe(90);
	expect(stepPreset(7, PRESETS, -1)).toBe(7);
	// A span that is not a preset still steps to the neighbouring one, so a
	// window left by a pan cannot strand the keys.
	expect(stepPreset(21, PRESETS, 1)).toBe(30);
	expect(stepPreset(21, PRESETS, -1)).toBe(14);
});

test('the cost of widening is the months not already in hand, and never a 404', () => {
	const available = ['2026-06', '2026-07', '2026-08'];
	expect(
		monthsToFetch({ start: '2026-08-01', end: '2026-08-28' }, available, ['2026-08'])
	).toEqual([]);
	expect(
		monthsToFetch({ start: '2026-06-15', end: '2026-08-28' }, available, ['2026-08'])
	).toEqual(['2026-06', '2026-07']);
	// A month the pipeline never published is not a cost. Asking for it would
	// only produce a 404 and a gap the charts already draw.
	expect(
		monthsToFetch({ start: '2026-04-01', end: '2026-08-28' }, available, ['2026-08'])
	).toEqual(['2026-06', '2026-07']);
});

test('THE ORACLE: every windowed surface reports the day count the control does', async ({
	page
}) => {
	await page.goto('/console/');
	await hydrated(page);

	// Four presets and at least four surfaces, or the loop below is a formality.
	expect(PRESETS.length, 'a control with one option cannot disagree with anything').toBeGreaterThan(
		1
	);
	const found = await windowed(page);
	expect(
		found.map((surface) => surface.name).sort(),
		'the page publishes no windowed surfaces, so the oracle asserts nothing'
	).toEqual([
		'chart-arm',
		'router-cost',
		'run-health',
		'site-size-movement',
		'source-cuts',
		'telemetry-viewport'
	]);

	for (const preset of PRESETS) {
		await setWindow(page, preset);
		const surfaces = await windowed(page);
		expect(surfaces.length, 'a surface stopped declaring itself windowed').toBe(found.length);
		for (const surface of surfaces) {
			expect(surface.days, `${surface.name} is drawing a different window`).toBe(preset);
			expect(surface.says, `${surface.name} never says how many days it is showing`).toContain(
				`${preset} days`
			);
		}
	}
});

/** The three numbers the source section prints about its own window. */
async function cutFacts(page: Page) {
	const intro = (
		await page.locator('[data-windowed="source-cuts"] p').first().innerText()
	).replace(/\s+/g, ' ');
	const more = (await page.locator('[data-source-cuts-more]').innerText()).replace(/\s+/g, ' ');
	const cost = (await page.locator('[data-source-cuts-cost]').innerText()).replace(/\s+/g, ' ');
	return {
		articles: Number(/, (\d+) articles between them/.exec(intro)?.[1]),
		tailSources: Number(/(\d+) more sources/.exec(more)?.[1]),
		cut: Number(/(\d+) articles were cut short/.exec(cost)?.[1])
	};
}

test('the source table follows the window, and drops what falls outside it', async ({ page }) => {
	await page.goto('/console/');
	await hydrated(page);

	// The canary writes one cut ten days back, under a source with a single cut.
	// Seven days cannot reach it and every wider preset can, so the section's own
	// counts move with the control rather than only its heading. They are read
	// rather than typed: a number written here goes stale the day the fixture
	// grows a row, and it goes stale silently.
	await setWindow(page, 7);
	const narrow = await cutFacts(page);
	await setWindow(page, 90);
	const wide = await cutFacts(page);

	expect(narrow.articles, 'the section prints no denominator').toBeGreaterThan(0);
	expect(wide.articles, 'widening reached no further article').toBeGreaterThan(narrow.articles);
	expect(wide.cut, 'widening reached no further cut').toBeGreaterThan(narrow.cut);
	// The older cut belongs to a source with one cut, so it lands in the tail
	// rather than the printed ten. The tail is where it has to show up.
	expect(wide.tailSources, 'the tail did not gain the older source').toBeGreaterThan(
		narrow.tailSources
	);

	// And the denominator is on the page, because at seven days it runs as low
	// as six articles and a share over six is not a rate. `\s+` rather than a
	// space: the sentence wraps in the template, and a regex reads the raw text.
	await expect(page.locator('[data-windowed="source-cuts"]')).toContainText(
		/\d+\s+articles between/
	);
});

test('a rule stated over 14 days prints no median in a 7-day window', async ({ page }) => {
	await page.goto('/console/');
	await hydrated(page);

	const card = page.locator('[data-windowed="router-cost"]');
	await setWindow(page, RULE_DAYS);
	await expect(card.locator('[data-window-too-narrow="router-cost"]')).toHaveCount(0);

	await setWindow(page, 7);
	// The exact sentence, because a median of the wrong span is the same figure
	// with a different meaning and nothing on the page to say which one it is.
	await expect(card.locator('[data-window-too-narrow="router-cost"]')).toHaveText(
		'The rule reads 14 days. Widen the window to see it.'
	);
	await expect(card.locator('svg')).toHaveCount(0);
});

test('two surfaces do not follow the window, and each says so', async ({ page }) => {
	await page.goto('/console/');
	await hydrated(page);

	// A windowed quarantine count would disagree with the resting the pipeline
	// actually performed, so the feed table counts every run and states it.
	const feeds = page.locator('[data-window-exempt="feeds"]');
	await expect(feeds).toContainText('does not follow the window');
	await expect(feeds).not.toHaveAttribute('data-window-days', /.*/);

	// The site size is a level, not a rate. The number stays absolute at every
	// preset; only the movement under it moves.
	const size = page.locator('[data-windowed="site-size-movement"]');
	const before = await size.locator('.kpi-value').textContent();
	await setWindow(page, 7);
	await expect(size.locator('.kpi-value')).toHaveText((before ?? '').trim());
	await expect(size).toContainText("Latest run's size");
});

test('the prerendered page opens on the configured window, whatever was stored', async ({
	page
}) => {
	await page.goto('/console/');
	await hydrated(page);
	await setWindow(page, PRESETS.at(-1) as number);

	// Read on mount and never during prerender: the document a browser is handed
	// is always the window the server drew, so first paint cannot flicker.
	const document = await (await page.request.get('/console/')).text();
	expect(document).toContain('data-window-control');
	expect(document).toContain(`data-window-days="${DEFAULT_DAYS}"`);

	await page.reload();
	await hydrated(page);
	await expect(page.locator('[data-window-control]')).toHaveAttribute(
		'data-window-days',
		String(PRESETS.at(-1))
	);
});

test('the control names the window it is holding, and is inert before a script runs', async ({
	page
}) => {
	await page.goto('/console/');

	const status = page.locator('[data-window-status]');
	await hydrated(page);
	await expect(status).toContainText(`showing ${DEFAULT_DAYS} days`);
	await expect(page.locator('[data-window-control]')).toHaveAttribute('data-window-busy', 'false');

	// Every preset is on the page at once. A menu would hide the wide one, which
	// is the one with a cost worth reading before it is paid.
	for (const preset of PRESETS) {
		await expect(page.locator(`[data-window-preset="${preset}"]`)).toBeVisible();
	}

	// And the prerendered document says it needs a script rather than offering a
	// control that would do nothing when clicked.
	const document = await (await page.request.get('/console/')).text();
	expect(document).toContain('This control needs JavaScript');
	expect(document).toMatch(/<input[^>]*name="console-window"[^>]*disabled/);
});
