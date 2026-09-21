import { expect, test } from '@playwright/test';

/**
 * What the stolen-processor panel says on the archive as it stands.
 *
 * **The canary carries no reading, and that is the case under test.** It names
 * `cpu_steal_pct` among its item columns and leaves every cell empty, on the
 * same rule the committed archive meets by accident: measured 2026-09-21, none
 * of the 13,946 committed item rows over 28 days carries the column at all,
 * because the ledger only began splitting it out of the busy share on
 * 2026-09-20 and no run has been published since. So the fourth state - the
 * reading begins later - is not an edge case here, it is the whole of what
 * ships today, and this is the file that says so.
 *
 * The loud tile and the quiet tile are driven directly in
 * `processor-lost.spec.ts`, over rows written there. A browser oracle for them
 * would never bite.
 */

test.beforeEach(async ({ page }) => {
	await page.goto('/console/machine/');
});

test('THE ORACLE: a page with no reading says so about the days it drew, and never that there is none', async ({
	page
}) => {
	const verdict = page.locator('[data-processor-lost-verdict]');
	await expect(verdict).toHaveCount(1);
	await expect(verdict).toHaveAttribute('data-processor-lost-verdict', 'unrecorded');

	const said = (await verdict.innerText()).replace(/\s+/g, ' ');
	// Bounded to the days on screen. "No run has ever recorded it" would be a
	// claim about runs this page did not read.
	expect(said, 'the sentence does not bound itself to the days it drew').toMatch(
		/in these \d+ days/
	);
	expect(said, 'the sentence claims something about every run there has ever been').not.toMatch(
		/\bnever\b/i
	);
	expect(said, 'the page invented a share nobody measured').not.toMatch(/\b0(\.0)?%/);
});

test('THE ORACLE: a day with no reading draws a blank cell, not a zero', async ({ page }) => {
	const tiles = page.locator('[data-processor-lost-tile]');
	const drawn = await tiles.count();
	expect(drawn, 'the day row drew no tiles, so this oracle asserts nothing').toBeGreaterThan(0);

	for (const tile of await tiles.all()) {
		expect(
			await tile.getAttribute('data-processor-lost-state'),
			'a day the canary never measured was drawn as a measurement'
		).toBe('unrecorded');
		expect(
			await tile.getAttribute('data-processor-lost-pct'),
			'a day with no reading carries a figure'
		).toBe('');
		expect(
			(await tile.locator('.says').innerText()).trim(),
			'a blank cell printed something'
		).toBe('');
	}
});

test('THE ORACLE: both grains are drawn, and the run grain names its run', async ({ page }) => {
	await expect(page.locator('[data-processor-lost-grain="day"]')).toHaveCount(1);
	const run = page.locator('[data-processor-lost-grain="run"]');
	await expect(run).toHaveCount(1);

	// A window is a span and a span cannot narrow one run, so the run row names
	// the run it is about rather than following the control.
	const shards = page.locator('[data-processor-lost-shard]');
	if ((await shards.count()) > 0) {
		await expect(run).toContainText(/\d{4}-\d{2}-\d{2}-\d+/);
	} else {
		await expect(run.locator('[data-processor-lost-empty="run"]')).toHaveCount(1);
	}
});

test('THE ORACLE: the correction is printed on the panel, not filed in a doc', async ({ page }) => {
	const correction = page.locator('[data-processor-lost-correction]');
	await expect(correction).toHaveCount(1);
	// The date is an attribute as well as prose, so a reader gets the sentence
	// and a test gets the fact without matching on wording.
	const on = await correction.getAttribute('data-processor-lost-correction');
	expect(on, 'the correction names no date').toMatch(/^\d{4}-\d{2}-\d{2}$/);
	await expect(correction).toContainText(String(on));
	await expect(correction, 'the correction does not say what was wrong').toContainText(
		'as our own work'
	);
});

test('THE ORACLE: the shard board carries the same reading, in the same third state', async ({
	page
}) => {
	const rows = page.locator('[data-shard-stolen-state]');
	const drawn = await rows.count();
	expect(drawn, 'the shard board drew no rows, so this oracle asserts nothing').toBeGreaterThan(0);

	for (const row of await rows.all()) {
		// The board and the panel read one ledger, so they cannot be in two
		// states at once. The canary records nothing, so both say unrecorded.
		expect(
			await row.getAttribute('data-shard-stolen-state'),
			'the board drew a stolen share the ledger does not hold'
		).toBe('unrecorded');
		expect(await row.getAttribute('data-shard-stolen-max'), 'the board invented a worst').toBe('');
	}
	await expect(page.locator('[data-shard-figure="stolen-range"]').first()).toContainText(
		'Not recorded'
	);
});
