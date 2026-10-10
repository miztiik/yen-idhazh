import { test, expect } from './support/door-page';
import { BAND_UNREAD, type RouteId } from '../src/lib/console/band';
import { BY_ROUTE } from './support/console-expect/console-voices';
import { reliabilityPublished, type SourceHealthView } from '../src/lib/server/payload';

/** Every source panel is on exactly one route.
 *
 * Row #13 moved four panels off Pipelines onto Voices and the
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

function routeHref(id: RouteId): string {
	const route = BAND_UNREAD.routes.find((route) => route.id === id);
	if (!route) throw new Error(`The console names no route ${id}`);
	return route.href;
}

/** The four panels the row moved, each named by an attribute its own markup
 * carries in every state it can be in.
 *
 * Two of the four draw a named absence when the pipeline has published nothing
 * for them, and the absence is a different element from the figure. Both are
 * listed, so the oracle counts the panel rather than counting whether the
 * canary happened to fill it - a selector that only matched the filled state
 * would read a duplicated but empty panel as no panel at all.
 */
const PANELS = BY_ROUTE.voices!.panels;

for (const panel of PANELS) {
	test(`THE ORACLE: ${panel.name} is on exactly one console route`, async ({ page }) => {
		const found: string[] = [];
		for (const id of Object.keys(BY_ROUTE) as RouteId[]) {
			if (BY_ROUTE[id] === null) continue;
			const route = routeHref(id);
			const answered = await page.goto(route);
			expect(answered?.status(), `${route} did not answer`).toBe(200);
			const drawn = await page.locator(panel.selector).count();
			if (drawn > 0) found.push(`${route} x${drawn}`);
		}

		// One route, one copy. The message names both halves, because "x2" on the
		// right route and "x1" on two routes are different defects with the same
		// symptom on the page.
		expect(found, `${panel.name} is not on exactly one route, once`).toEqual(
			Object.values(BY_ROUTE)
				.filter((expected) => expected !== null && expected.panelCopies > 0)
				.map((expected) => `${expected!.href} x${expected!.panelCopies}`)
		);
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
	const OWNED = BY_ROUTE.voices!.ownedSelectors;

	await page.goto(routeHref('pipelines'));
	const left: string[] = [];
	for (const selector of OWNED) {
		const drawn = await page.locator(selector).count();
		if (drawn > 0) left.push(`${selector} x${drawn}`);
	}
	expect(left, 'Pipelines still draws part of a panel it gave away').toEqual([]);

	// And the same sweep on Voices finds them, so a suite that passed because
	// every selector had been renamed out of existence fails here instead.
	await page.goto(routeHref('voices'));
	const arrived: string[] = [];
	for (const selector of OWNED) {
		if ((await page.locator(selector).count()) > 0) arrived.push(selector);
	}
	expect(
		arrived.length,
		'none of the moved attributes is on Voices either, so the sweep above proves nothing'
	).toBe(OWNED.length);
});

/** A view the way the producer writes it today, built rather than read.
 *
 * Built, because the question is what the reader does with a shape no committed
 * file has to keep having. A fixture taken off the archive answers it until the
 * day the archive stops carrying that shape, and then it answers nothing while
 * still passing (`CLAUDE.md` section 13).
 */
function view(): SourceHealthView {
	return {
		generated_at: '2026-09-14T06:00:00Z',
		run_id: '2026-09-14-1',
		headline_sentence: 'Nothing on this page is outside its bound.',
		reliability_floor: 0.5,
		reliability_window_days: 30,
		min_complete_days: 30,
		complete_dates: 9,
		yield_readable: false,
		first_date: '2026-09-05',
		last_date: '2026-09-13',
		sources: [
			{
				source_id: 'canary-one',
				title: 'Canary One',
				vertical: 'ai',
				permission: 'allowed',
				availability: 'answering',
				retired: false,
				retired_on: null,
				opportunities: 12,
				publications: 9,
				source_failures: 1,
				reliability: 0.75,
				reliability_reads: 8
			}
		]
	};
}

test('a view written before the ranking factor existed draws an absence, not a crash', () => {
	// The five reliability fields landed on 2026-09-14 and the committed view was
	// written by a run older than that, so on the day this row merged the file on
	// disk had none of them. A page that read `row.reliability.toFixed(3)` without
	// asking threw during prerender and took the whole route out of the build -
	// the census and the failure list with it, neither of which needs the field.
	//
	// The key is removed from a built view rather than counted in the committed
	// tree. A test that asserted "some committed view still lacks the field" goes
	// green today and red on the day the last old view ages out, which is a date
	// on the calendar rather than a change anybody made.
	expect(reliabilityPublished(view()), 'a current view reads as unpublished').toBe(true);

	const old = view() as Partial<SourceHealthView>;
	delete old.reliability_floor;
	delete old.reliability_window_days;
	delete old.headline_sentence;
	for (const row of old.sources ?? []) {
		delete (row as Partial<(typeof row)>).reliability;
		delete (row as Partial<(typeof row)>).reliability_reads;
	}
	expect(
		reliabilityPublished(old as SourceHealthView),
		'a view from before the field reads as carrying it, so the page would draw a bar over nothing'
	).toBe(false);

	// And the two states either side of the guard are distinguishable from
	// absence: no view at all is also false, and that is the state the panel was
	// already drawing an absence for.
	expect(reliabilityPublished(null)).toBe(false);
});
