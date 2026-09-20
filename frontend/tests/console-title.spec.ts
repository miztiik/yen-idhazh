import { expect, test, type Page } from '@playwright/test';

/**
 * One grammar for every title on the console, and no address moved to get it.
 *
 * The three routes grew their titles separately, so a reader met a question on
 * one panel and a noun phrase on the next: `Did the runs finish?` above a chart
 * of two shares, `Do the two clocks agree` above a bar per shard. A question
 * title asks the reader to hold it while he reads the panel; a noun phrase
 * names what is in front of him, and the owner's own model - `What one more
 * article costs` - is a noun phrase.
 *
 * The declared grammar is mechanical on purpose, because a grammar nothing can
 * check is a preference. A title carries no trailing question mark; it does not
 * open with an auxiliary verb, because `Did`, `Do`, `Is`, `Are`, `Was`, `Has`,
 * `Can` and `Will` turn the rest of the line into a question with or without
 * the mark; and it is one clause rather than a sentence.
 *
 * `What`, `Which`, `How`, `Where` and `Why` are allowed openings: they head a
 * free relative - `What one more article costs`, `Which sources the checker
 * doubts` - which is a noun phrase and not a question.
 *
 * The second half of this file is the half that matters more. Two of the three
 * route labels were rewritten on the same day - `Model` became `Summaries`,
 * `Machine` became `Hardware` - and the whole risk of a rename is that a word
 * a reader reads and a word a browser resolves turn out to be one string. Every
 * id, every path and every route marker is asserted unmoved. The fuller address
 * check, including the geometric oracle the strip took when it grew to five
 * tabs on 2026-09-12, is in `console-nav.spec.ts`.
 */

/** Every console route, and the fewest headings it may draw.
 *
 * The floor is per route rather than shared, because the two things it is doing
 * pull apart. The grammar below binds every title on every route. The floor is
 * a separate guarantee - that the scan found the route's own panels rather than
 * an empty frame - and that number is a fact about the route, not about the
 * rule. A shared floor of three made `/console/judgement/` unassertable when it
 * drew one heading, and a shared floor of two would quietly stop noticing if
 * `/console/` lost a panel.
 *
 * `/console/judgement/` draws two on 2026-09-17: the `Stories the day merged`
 * panel, and the heading over the absence that names what the model still does
 * not record. `/console/voices/` drew one until 2026-09-14, when four panels
 * moved onto it. `/console/machine/` draws sixteen since 2026-09-20 - three
 * group headings and the thirteen panel titles under them.
 */
const ROUTES: Record<string, number> = {
	'/console/': 3,
	'/console/model/': 3,
	'/console/machine/': 16,
	'/console/voices/': 3,
	'/console/judgement/': 2
};

/** An opening that turns the rest of the line into a question. */
const AUXILIARY =
	/^(did|do|does|is|are|am|was|were|has|have|had|can|could|will|would|shall|should|may|might|must)\b/i;

/** Every heading the route draws, which is every section heading and every
 * panel title - `Panel.svelte` renders its `title` prop as an h2, or as an h3
 * where a group heading above it took the h2, so one scan covers both halves of
 * what the row rules on. */
async function titlesOn(page: Page): Promise<string[]> {
	return page
		.locator('[data-surface="operator"] h2, [data-surface="operator"] h3')
		.evaluateAll((nodes) =>
			nodes.map((node) => (node.textContent ?? '').replace(/\s+/g, ' ').trim())
		);
}

for (const [route, floor] of Object.entries(ROUTES)) {
	test(`THE ORACLE: every title on ${route} is a noun phrase`, async ({ page }) => {
		await page.goto(route);
		const titles = await titlesOn(page);
		expect(
			titles.length,
			`${route} draws fewer than ${floor} headings, so this asserts less than it should`
		).toBeGreaterThanOrEqual(floor);

		for (const title of titles) {
			expect(title.length, `${route} carries an empty title`).toBeGreaterThan(2);
			expect(title, `"${title}" on ${route} is a question`).not.toMatch(/\?\s*$/);
			expect(title, `"${title}" on ${route} opens with an auxiliary verb`).not.toMatch(AUXILIARY);
			expect(title, `"${title}" on ${route} is a sentence, not a title`).not.toMatch(/\.\s+\S/);
		}
	});
}

test('the three titles the row was opened for are the ones that changed', async ({ page }) => {
	// Named, so a future edit that reintroduces one fails here rather than in the
	// general rule above - which would only say "a title is a question" without
	// saying which one came back.
	const gone = [
		'Did the runs finish?',
		'Do the two clocks agree',
		'Is the tail growing',
		'Did the model change move anything'
	];
	for (const route of Object.keys(ROUTES)) {
		await page.goto(route);
		const text = await page.locator('[data-surface="operator"]').innerText();
		for (const title of gone) {
			expect(text, `${route} still asks "${title}"`).not.toContain(title);
		}
	}

	// And the panels themselves are still drawn, under their new names, so this
	// reads as a rename and not as four deletions.
	await page.goto('/console/');
	await expect(page.locator('[data-glance-chart="runs"] figcaption')).toHaveText(
		'Runs that finished'
	);
	await page.goto('/console/machine/');
	const machine = await titlesOn(page);
	expect(machine, 'the clock check lost its panel').toContain('The two clocks, compared');
	expect(machine, 'the latency panel lost its panel').toContain('How the tail moved');

	// The model-change panel draws only where the ledger holds a swap, and the
	// canary holds none - so what is asserted is the shape that survives either
	// state: where the section is drawn it carries the new heading, and where it
	// is not it is absent rather than headless.
	await page.goto('/console/model/');
	const swap = page.locator('[data-model-swap-section]');
	if ((await swap.count()) > 0) {
		await expect(swap.locator('h2')).toHaveText('What the model change moved');
	} else {
		expect(await titlesOn(page), 'a headless model-change section is on the page').not.toContain(
			'What the model change moved'
		);
	}
});

test('THE ORACLE: the labels moved and the addresses did not', async ({ page }) => {
	await page.goto('/console/');
	const drawn = await page
		.locator('[data-console-nav] [data-console-tab]')
		.evaluateAll((links) =>
			links.map((node) => ({
				id: node.getAttribute('data-console-tab') ?? '',
				href: (node as HTMLAnchorElement).getAttribute('href') ?? '',
				label: (node.querySelector('.tab-label')?.textContent ?? '').trim()
			}))
		);

	// The labels changed.
	expect(
		drawn.map((tab) => tab.label),
		'the strip does not carry the five labels'
	).toEqual(['Pipelines', 'Summaries', 'Hardware', 'Judgement', 'Voices']);

	// The ids did not, and neither did what they point at. Typed out in strip
	// order rather than read off `ROUTES`: that map is keyed for the grammar
	// rule and nothing holds its keys in the order the strip draws them.
	expect(
		drawn.map((tab) => tab.id),
		'a tab id moved with a label, which is an address and not a label'
	).toEqual(['pipelines', 'model', 'machine', 'judgement', 'voices']);
	const IN_STRIP_ORDER = [
		'/console/',
		'/console/model/',
		'/console/machine/',
		'/console/judgement/',
		'/console/voices/'
	];
	for (const [index, path] of IN_STRIP_ORDER.entries()) {
		expect(drawn[index].href, `${drawn[index].id} stopped pointing at ${path}`).toContain(path);
	}
});
