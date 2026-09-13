import { test, expect } from '@playwright/test';

/** Every source panel is on exactly one route.
 *
 * Row #13 moved four panels off `/console/` onto `/console/voices/` and the
 * ruling was that Pipelines keeps none of them. A move done by copy is the
 * failure this file exists to catch, and it is the one that looks fine: both
 * pages render, both pass their own assertions, and an operator reads two
 * copies of one census that disagree the moment one of them is edited. Nothing
 * else in the suite would notice - every other console spec visits one route
 * and asks what is on it, so a panel on two routes passes twice.
 *
 * It counts across all five built routes rather than checking Pipelines alone,
 * because "not on Pipelines" is the weaker half of the claim. The stronger half
 * is that the panel is somewhere, exactly once.
 *
 * The counts come from the built canary, which is what `playwright.config.ts`
 * serves. Nothing here opens a committed ledger file: the archive grows on
 * every run, and a test whose cost grows with it is the defect Guardrail #12
 * names (`CLAUDE.md` section 13).
 */

/** Every console route, in strip order. Typed out rather than read from
 * `band.ts`, because a panel that vanished along with a route id would still
 * pass a count taken over a list the same edit shortened. */
const ROUTES = [
	'/console/',
	'/console/model/',
	'/console/machine/',
	'/console/judgement/',
	'/console/voices/'
] as const;

/** The four panels the row moved, each named by an attribute its own markup
 * carries in every state it can be in.
 *
 * Two of the four draw a named absence when the pipeline has published nothing
 * for them, and the absence is a different element from the figure. Both are
 * listed, so the oracle counts the panel rather than counting whether the
 * canary happened to fill it - a selector that only matched the filled state
 * would read a duplicated but empty panel as no panel at all.
 */
const PANELS = [
	{
		name: 'the source census',
		selector: '[data-source-health-lead], [data-source-health="absent"]'
	},
	{
		name: 'the ranking weight',
		selector: '[data-voices="reliability"], [data-console-empty="voices"]'
	},
	{ name: 'the feed failure record', selector: '[data-window-exempt="feeds"]' },
	{ name: 'the truncation cap cost', selector: '[data-windowed="source-cuts"]' }
] as const;

for (const panel of PANELS) {
	test(`THE ORACLE: ${panel.name} is on exactly one console route`, async ({ page }) => {
		const found: string[] = [];
		for (const route of ROUTES) {
			const answered = await page.goto(route);
			expect(answered?.status(), `${route} did not answer`).toBe(200);
			const drawn = await page.locator(panel.selector).count();
			if (drawn > 0) found.push(`${route} x${drawn}`);
		}

		// One route, one copy. The message names both halves, because "x2" on the
		// right route and "x1" on two routes are different defects with the same
		// symptom on the page.
		expect(found, `${panel.name} is not on exactly one route, once`).toEqual([
			'/console/voices/ x1'
		]);
	});
}

test('THE ORACLE: Pipelines kept no attribute the moved panels own', async ({ page }) => {
	// The panel count above would still pass if a stray row, note or axis had
	// been left behind on Pipelines - a panel is its wrapper, and the wrapper is
	// what moved. This is the sweep under it: every attribute prefix the four
	// panels write, counted on the route they left.
	//
	// `data-source-domain` is not here and belongs to the chart component rather
	// than to the route, so it travels with the panel wherever the panel is.
	const OWNED = [
		'[data-feed]',
		'[data-feeds]',
		'[data-feed-result]',
		'[data-feed-reliability]',
		'[data-feed-clean-name]',
		'[data-feed-ineligible-name]',
		'[data-feed-strip]',
		'[data-feed-axis]',
		'[data-rested]',
		'[data-source-health]',
		'[data-source-health-lead]',
		'[data-source-state]',
		'[data-source-note]',
		'[data-source-cut]',
		'[data-source-cuts-intro]',
		'[data-windowed="source-cuts"]',
		'[data-windowed="feed-outcomes"]',
		'[data-window-exempt="feeds"]',
		'[data-window-exempt="source-health"]'
	];

	await page.goto('/console/');
	const left: string[] = [];
	for (const selector of OWNED) {
		const drawn = await page.locator(selector).count();
		if (drawn > 0) left.push(`${selector} x${drawn}`);
	}
	expect(left, 'Pipelines still draws part of a panel it gave away').toEqual([]);

	// And the same sweep on Voices finds them, so a suite that passed because
	// every selector had been renamed out of existence fails here instead.
	await page.goto('/console/voices/');
	const arrived: string[] = [];
	for (const selector of OWNED) {
		if ((await page.locator(selector).count()) > 0) arrived.push(selector);
	}
	expect(
		arrived.length,
		'none of the moved attributes is on Voices either, so the sweep above proves nothing'
	).toBe(OWNED.length);
});
