/** Hardware narrows actual runs and leaves newest-run snapshots alone. */
import { expect, test } from './support/browser';

import { hydrated, setWindow, routeHref } from './support/console-window/controls';

import { machineSpan } from './support/console-window/machine-spans';

test('the Machine route draws the narrower span, not only the narrower label', async ({ page }) => {
	// A route that wired the day count onto its surfaces and drew the same runs
	// at every preset would pass the oracle above. The canary puts one run forty
	// days back, so only the widest preset reaches it: the counts are read off
	// the page rather than typed here, because a number written in a test goes
	// stale the day the fixture grows a row, and it goes stale silently.
	await page.goto(routeHref('machine'));
	await hydrated(page);

	await setWindow(page, 90);
	const wide = await machineSpan(page);
	await setWindow(page, 7);
	const narrow = await machineSpan(page);

	expect(narrow.end, 'the two spans end on different days').toBe(wide.end);
	expect(narrow.start > wide.start, 'narrowing did not move the first day').toBe(true);
	expect(wide.runs, 'the widest span reached no further run').toBeGreaterThan(narrow.runs);
	expect(wide.bars, 'the context panel drew the same bars at both spans').toBeGreaterThan(
		narrow.bars
	);
});

test('the panels about one run say so, and hold still while the window moves', async ({ page }) => {
	// Decision #2 of the row: a window is a span, and a span cannot narrow a
	// single run. The shard board, the split, the clock check and the latency
	// curves are snapshots, so they name the run they are about rather than
	// emptying out when an operator picks seven days. Since 2026-09-20 each says
	// it in its own subtitle instead of in a paragraph above all of them: the
	// groups name a decision now, so one group holds a snapshot beside a reading
	// over the span and no heading can carry the grain for its panels.
	await page.goto(routeHref('machine'));
	await hydrated(page);

	const exempt = page.locator('[data-window-exempt="newest-run"]');
	await expect(exempt).toContainText('newest run');
	await expect(exempt).not.toHaveAttribute('data-window-days', /.*/);
	await expect(page.locator('[data-console-panel-id="shard-board"] > header > p')).toContainText(
		'the newest run'
	);

	const board = page.locator('[data-shard-board]');
	const before = await board.innerText();
	await setWindow(page, 7);
	expect(await board.innerText(), 'the shard board followed the window').toBe(before);
	await setWindow(page, 90);
	expect(await board.innerText(), 'the shard board followed the window').toBe(before);
});
