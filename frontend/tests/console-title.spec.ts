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
 * check, including the ceiling keys config holds the three routes to, is in
 * `console-nav.spec.ts`.
 */

const ROUTES = ['/console/', '/console/model/', '/console/machine/'] as const;

/** An opening that turns the rest of the line into a question. */
const AUXILIARY =
	/^(did|do|does|is|are|am|was|were|has|have|had|can|could|will|would|shall|should|may|might|must)\b/i;

/** Every h2 the route draws, which is every section heading and every panel
 * title - `Panel.svelte` renders its `title` prop as an h2, so one scan covers
 * both halves of what the row rules on. */
async function titlesOn(page: Page): Promise<string[]> {
	return page
		.locator('[data-surface="operator"] h2')
		.evaluateAll((nodes) =>
			nodes.map((node) => (node.textContent ?? '').replace(/\s+/g, ' ').trim())
		);
}

for (const route of ROUTES) {
	test(`THE ORACLE: every title on ${route} is a noun phrase`, async ({ page }) => {
		await page.goto(route);
		const titles = await titlesOn(page);
		expect(titles.length, `${route} draws no h2 at all, so this asserts nothing`).toBeGreaterThan(2);

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
	for (const route of ROUTES) {
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
		'the strip does not carry the three labels'
	).toEqual(['Pipelines', 'Summaries', 'Hardware']);

	// The ids did not, and neither did what they point at.
	expect(
		drawn.map((tab) => tab.id),
		'a tab id moved with a label, which is an address and not a label'
	).toEqual(['pipelines', 'model', 'machine']);
	for (const [index, path] of ROUTES.entries()) {
		expect(drawn[index].href, `${drawn[index].id} stopped pointing at ${path}`).toContain(path);
	}
});
