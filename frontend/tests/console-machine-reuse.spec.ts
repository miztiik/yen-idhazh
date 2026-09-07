import { expect, test, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

/**
 * The Hardware route prepares its run context and its latency curves once a
 * span, and reuses them while the window only resizes.
 *
 * Finding 108 (Rule #12): the route used to rebuild the caption columns, the
 * boundary set, the plotted domain and every polyline on each preset AND each
 * resize - so a drag that moved pixels re-ran work that only a new span can
 * change. The fix splits the data-only preparation (a function of the runs in
 * the span) from the geometry (a function of the width). A resize now moves the
 * pixels and reuses the preparation.
 *
 * The oracle is parity, not speed. The reuse itself is invisible in the DOM, so
 * these tests assert what the reuse must PRESERVE: the retained extent and the
 * run population hold still across a resize, and still rebuild across a preset.
 * The `data-context-domain` / `data-tail-domain` attributes are the retained
 * extents made visible. The base tree does not publish them, so a run of this
 * spec against the base tree fails on the first `parseDomain` - that absence is
 * the honest red-before-green signal, because a pure drawn-mark parity check
 * passes on the base tree (hand-written SVG already reflows correctly).
 */

const CONFIG = JSON.parse(
	readFileSync(resolve(process.cwd(), '..', 'config', 'appearance.json'), 'utf8')
) as { console?: { window_presets?: number[]; default_window_days?: number } };

const PRESETS = CONFIG.console?.window_presets ?? [1, 7, 14, 30, 90];
const DEFAULT_DAYS = CONFIG.console?.default_window_days ?? 30;
const WIDEST = Math.max(...PRESETS);
const NARROWEST = Math.min(...PRESETS);

/** The control is disabled in the prerendered document and enabled on mount, so
 * waiting for it is waiting for the route to be able to change its own span. */
async function hydrated(page: Page) {
	await expect(page.locator(`[data-window-preset="${DEFAULT_DAYS}"] input`)).toBeEnabled();
}

async function setWindow(page: Page, days: number) {
	await page.locator(`[data-window-preset="${days}"]`).click();
	await expect(page.locator('[data-window-control]')).toHaveAttribute(
		'data-window-days',
		String(days)
	);
}

/** A published extent is a finite pair. `parseDomain(null)` is the assertion the
 * base tree fails on, because the base tree publishes no extent at all. */
function parseDomain(raw: string | null, which: string): [number, number] {
	expect(raw, `the ${which} panel published no retained extent`).not.toBeNull();
	const parsed = JSON.parse(raw as string) as unknown;
	expect(
		Array.isArray(parsed) && parsed.length === 2,
		`the ${which} extent is not a pair: ${raw}`
	).toBe(true);
	const pair = parsed as [number, number];
	expect(
		Number.isFinite(pair[0]) && Number.isFinite(pair[1]),
		`the ${which} extent is not finite: ${raw}`
	).toBe(true);
	return pair;
}

const contextPanel = (page: Page) => page.locator('[data-windowed="machine-context"]');
const latencyPanel = (page: Page) => page.locator('[data-windowed="machine-latency"]');

test('the run-context and latency panels publish the extent they were drawn against', async ({
	page
}) => {
	await page.goto('/console/machine/');
	await hydrated(page);

	const [contextLow, contextHigh] = parseDomain(
		await contextPanel(page).getAttribute('data-context-domain'),
		'run-context'
	);
	const [tailLow, tailHigh] = parseDomain(
		await latencyPanel(page).getAttribute('data-tail-domain'),
		'latency'
	);

	// The context plot is zero-anchored and the window is its upper bound, so the
	// span is never a point. The latency plot can be flat on a quiet day, so it
	// is only required not to invert.
	expect(contextHigh, 'the run-context extent collapsed to a point').toBeGreaterThan(contextLow);
	expect(tailHigh, 'the latency extent inverted').toBeGreaterThanOrEqual(tailLow);
});

test('a resize moves the pixels and reuses the extents, it does not recompute them', async ({
	page
}) => {
	await page.setViewportSize({ width: 1440, height: 1000 });
	await page.goto('/console/machine/');
	await hydrated(page);
	// The widest preset, so the latency panel has runs to draw an extent from.
	await setWindow(page, WIDEST);

	const spare = page.locator('[data-context-series="spare"]');
	const wideSpare = await spare.getAttribute('points');
	const wideContext = await contextPanel(page).getAttribute('data-context-domain');
	const wideTail = await latencyPanel(page).getAttribute('data-tail-domain');
	const wideRuns = await page.locator('[data-context-run]').count();
	parseDomain(wideContext, 'run-context');
	parseDomain(wideTail, 'latency');
	expect(wideSpare, 'the run-context panel drew no spare-capacity line').not.toBeNull();

	// Narrow the viewport. The polyline is drawn in pixels off the width, so its
	// points MUST move - that is the proof the resize was processed rather than
	// swallowed, and it is the work the fix keeps doing.
	await page.setViewportSize({ width: 560, height: 1000 });
	await expect(
		spare,
		'the run-context polyline did not reflow, so the resize changed nothing to reason about'
	).not.toHaveAttribute('points', wideSpare ?? '');

	// The pixels moved. The extents, the population and the caption domain are a
	// function of the span alone, so they must be byte-identical to before.
	expect(
		await contextPanel(page).getAttribute('data-context-domain'),
		'the run-context extent was recomputed on a resize'
	).toBe(wideContext);
	expect(
		await latencyPanel(page).getAttribute('data-tail-domain'),
		'the latency extent was recomputed on a resize'
	).toBe(wideTail);
	expect(
		await page.locator('[data-context-run]').count(),
		'the run population changed on a resize'
	).toBe(wideRuns);
});

test('a new window still rebuilds the population, so the reuse is a cache and not a freeze', async ({
	page
}) => {
	// The danger in reusing across a resize is reusing across a preset too. The
	// canary puts one run forty days back, so the widest span reaches a run the
	// narrowest cannot - the counts are read off the page, never typed here, so
	// the test cannot go stale when the fixture grows a row.
	await page.goto('/console/machine/');
	await hydrated(page);

	await setWindow(page, WIDEST);
	const wideRuns = await page.locator('[data-context-run]').count();
	await setWindow(page, NARROWEST);
	const narrowRuns = await page.locator('[data-context-run]').count();

	expect(wideRuns, 'the widest window reached no further run than the narrowest').toBeGreaterThan(
		narrowRuns
	);
});
