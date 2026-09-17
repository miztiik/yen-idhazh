import { test, expect } from '@playwright/test';

/** The reliability strip: is a source counting down, and can an operator see it?
 *
 * One question a file. Whether the panel is on exactly one route is
 * `console-voices.spec.ts`'s; the yield figures themselves are
 * `console-voices-sources.spec.ts`'s. This file owns the countdown: the dwell
 * drawn as an area, the shared date axis, and the three sentences that carry
 * the state without colour.
 *
 * Everything is read off the built canary, which is what `playwright.config.ts`
 * serves. Nothing here opens a committed ledger: the archive grows on every run
 * and a test whose cost grows with it is the defect Guardrail #12 names
 * (`CLAUDE.md` section 13).
 */

const ROUTE = '/console/voices/';

test('the panel is present in every state, and says which one it is in', async ({ page }) => {
	await page.goto(ROUTE);

	const heading = page.getByRole('heading', { name: 'Sources close to retiring themselves' });
	await expect(heading).toBeVisible();

	// The heading survives even when the run published no census. A panel that
	// disappears teaches an operator to stop looking for it.
	const table = page.locator('[data-retiring="table"]');
	const absent = page.locator('[data-retiring="absent"]');
	expect((await table.count()) + (await absent.count())).toBe(1);
});

test('a countdown that retires nothing says so in words', async ({ page }) => {
	await page.goto(ROUTE);
	const table = page.locator('[data-retiring="table"]');
	test.skip((await table.count()) === 0, 'the canary published no source census');

	const auto = await table.getAttribute('data-retiring-auto');
	const watching = page.locator('[data-retiring-watching]');

	if (auto === 'no') {
		// A red countdown while nothing retires is a lie told in colour. The
		// sentence is what makes the panel honest in its first release.
		await expect(watching).toHaveText(/watching only/);
	} else {
		expect(await watching.count()).toBe(0);
	}
});

test('the lead names the rule in full: a share, a run of days, and a denominator', async ({
	page
}) => {
	await page.goto(ROUTE);
	const table = page.locator('[data-retiring="table"]');
	test.skip((await table.count()) === 0, 'the canary published no source census');

	const lead = await page.locator('[data-retiring-lead]').innerText();
	const dwell = await table.getAttribute('data-retiring-dwell');

	// A share with no period is not a measurement, and a period with no share is
	// not a rule. Both are in one sentence or the panel has not said the rule.
	expect(lead).toMatch(/\d+%/);
	expect(lead).toContain(`${dwell} days running`);
	await expect(page.locator('[data-retiring-clear]')).toHaveText(/at or above the mark/);
});

test('every row draws its bar on the same track with its marker at the same share', async ({
	page
}) => {
	await page.goto(ROUTE);
	const rows = page.locator('[data-retiring-row]');
	const drawn = await rows.count();
	test.skip(drawn === 0, 'no source is under the mark on the canary');

	// The whole reason to stack these is that a column means the same thing all
	// the way down. A per-row maximum, or a marker at a different x on different
	// rows, makes the stack unreadable while looking perfectly fine.
	const tracks = await rows.evaluateAll((list) =>
		list.map((row) => row.getAttribute('data-retiring-track'))
	);
	expect(new Set(tracks).size).toBe(1);
	expect(tracks[0]).toBe('1');
});

test('the dwell is an area under the newest squares, not a number in a chip', async ({ page }) => {
	await page.goto(ROUTE);
	const rows = page.locator('[data-retiring-row]');
	const drawn = await rows.count();
	test.skip(drawn === 0, 'no source is under the mark on the canary');

	for (let index = 0; index < drawn; index += 1) {
		const row = rows.nth(index);
		const under = Number(await row.getAttribute('data-retiring-days-under'));
		const rule = row.locator('[data-retiring-dwell-rule]');
		expect(await rule.count()).toBe(under > 0 ? 1 : 0);

		if (under === 0) continue;
		// The marked squares are the newest ones, contiguous. Anything else and
		// the picture and the number below it are telling two stories.
		const states = await row
			.locator('[data-retiring-state]')
			.evaluateAll((list) => list.map((square) => square.getAttribute('data-retiring-state')));
		const tail = states.slice(states.length - under);
		expect(tail.every((state) => state !== 'at-or-above')).toBe(true);
	}
});

test('a live countdown reads its days and its date without colour', async ({ page }) => {
	await page.goto(ROUTE);
	const rows = page.locator('[data-retiring-row]');
	const drawn = await rows.count();
	test.skip(drawn === 0, 'no source is under the mark on the canary');

	for (let index = 0; index < drawn; index += 1) {
		const row = rows.nth(index);
		const under = Number(await row.getAttribute('data-retiring-days-under'));
		if (under === 0) continue;

		const readout = await row.locator('[data-retiring-readout]').innerText();
		expect(readout).toContain('published of');
		expect(readout).toContain(`Under the mark for ${under}`);

		const on = await row.getAttribute('data-retiring-on');
		if (on) expect(readout).toContain(on);
	}
});

test('one date axis serves the whole list, so a column is one day on every row', async ({
	page
}) => {
	await page.goto(ROUTE);
	const strips = page.locator('[data-retiring-strip]');
	const count = await strips.count();
	test.skip(count === 0, 'the canary drew no strip');

	const widths = await strips.evaluateAll((list) =>
		list.map((strip) => strip.querySelectorAll('[data-retiring-day]').length)
	);
	expect(new Set(widths).size).toBe(1);

	const dates = await strips
		.first()
		.locator('[data-retiring-day]')
		.evaluateAll((list) => list.map((square) => square.getAttribute('data-retiring-day')));
	for (let index = 1; index < count; index += 1) {
		const other = await strips
			.nth(index)
			.locator('[data-retiring-day]')
			.evaluateAll((list) => list.map((square) => square.getAttribute('data-retiring-day')));
		expect(other).toEqual(dates);
	}
});

test('every square carries a sentence, so colour is never the only signal', async ({ page }) => {
	await page.goto(ROUTE);
	const squares = page.locator('[data-retiring-day]');
	const count = await squares.count();
	test.skip(count === 0, 'the canary drew no strip');

	const labels = await squares.evaluateAll((list) =>
		list.map((square) => square.getAttribute('aria-label') ?? '')
	);
	expect(labels.every((label) => label.length > 0)).toBe(true);
	expect(labels.some((label) => /mark|decided nothing/.test(label))).toBe(true);
});

test('a source under its evidence floors is drawn, not hidden, and says what is missing', async ({
	page
}) => {
	await page.goto(ROUTE);
	const table = page.locator('[data-retiring="table"]');
	test.skip((await table.count()) === 0, 'the canary published no source census');

	const unjudged = page.locator('[data-retiring-unjudged-row]');
	const count = await unjudged.count();
	test.skip(count === 0, 'every source on the canary has cleared both floors');

	// Hiding these would hide the shape, and the shape is what an operator is
	// here for. What they have not got is a number anybody may act on.
	await expect(page.locator('[data-retiring-unjudged-lead]')).toHaveText(/Not judged yet/);
	await expect(page.locator('[data-retiring-unjudged-lead]')).toHaveText(
		/judged at \d+ of them plus \d+/
	);
	const readout = await unjudged.first().locator('[data-retiring-readout]').innerText();
	expect(readout).toMatch(/Decided \d+ of the \d+ address/);
	expect(await unjudged.first().locator('[data-retiring-chip]').count()).toBe(0);
});

test('the unjudged block is capped too, and its tail is a number', async ({ page }) => {
	await page.goto(ROUTE);
	const table = page.locator('[data-retiring="table"]');
	test.skip((await table.count()) === 0, 'the canary published no source census');

	const drawn = await page.locator('[data-retiring-unjudged-row]').count();
	test.skip(drawn === 0, 'every source on the canary has cleared both floors');

	// On a shallow record every source is unjudged, which on this repository is
	// 156 rows. A wall is not a panel, so it caps like every other console list.
	expect(drawn).toBeLessThanOrEqual(Number(await table.getAttribute('data-retiring-cap')));
	const more = page.locator('[data-retiring-unjudged-more]');
	if ((await more.count()) > 0) await expect(more).toHaveText(/^\d+ more/);
});

test('the tail of the ranking is a number, never another page of rows', async ({ page }) => {
	await page.goto(ROUTE);
	const table = page.locator('[data-retiring="table"]');
	test.skip((await table.count()) === 0, 'the canary published no source census');

	const hidden = Number(await table.getAttribute('data-retiring-hidden'));
	const more = page.locator('[data-retiring-more]');
	expect(await more.count()).toBe(hidden > 0 ? 1 : 0);
	if (hidden > 0) await expect(more).toHaveText(new RegExp(`^${hidden} more`));
});
