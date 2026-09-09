import { expect, test, type Page, type Route } from '@playwright/test';

/**
 * The console's reserved shape, and the four different nothings behind it.
 *
 * The page holds no telemetry row when its document arrives - every row is
 * fetched on mount (row 10 of the shell-and-fetch plan). That split one
 * "nothing" into four, and until row 12 the page drew three of them the same
 * way: an unmarked gap. A quiet pipeline and a broken fetch were one picture,
 * which is the exact pair this console exists to tell apart.
 *
 * What this file holds:
 *
 * - **The oracle.** Every console panel's bounding box, measured twice in ONE
 *   page session - while the months are still in the air, and once they have
 *   landed - and compared. A CSS property is not checked, because a CSS
 *   property is not what moves under a reader's cursor.
 * - **One timeline.** Every shimmering block starts its sweep in the same
 *   frame. Out of phase, twelve sweeping boxes read as twelve broken things.
 * - **Reduced motion.** `app.css` zeroes every `animation-duration` to
 *   `0.01ms !important` on `*`, which would FREEZE a moving gradient mid-sweep
 *   and leave a bright band nobody chose. The flat block has to beat that rule,
 *   and the proof is the computed style in a browser that asked for stillness.
 * - **A state per state**, each with the sentence it prints.
 *
 * Every arm blocks the service worker. A "the payload did not arrive" arm is a
 * lie while a worker can serve the payload out of its own cache.
 */

test.use({ serviceWorkers: 'block' });

/** How long a blocked month is held before it answers, so the waiting state is
 * on screen long enough to measure. Comfortably past `shimmer_after_ms` (400). */
const HELD_MS = 2500;

const TELEMETRY = '**/telemetry/*.csv';
const BAND = '**/console/band.json';

/** A telemetry shard with a header and no rows. Valid, parses, holds nothing -
 * which is what a genuinely quiet month looks like on the wire. */
const EMPTY_CSV =
	'date,run_id,item_id,stage,outcome,source_id,url,title,error_code,summarize_ms,' +
	'prompt_tokens,completion_tokens,cached_tokens,compression_ratio,band,words_in,words_out\n';

async function hydrated(page: Page) {
	await expect(page.locator('[data-console-panels="pipelines"]')).toHaveAttribute(
		'data-telemetry-state',
		/loading|ready|quiet|missing|unreachable/
	);
}

async function settled(page: Page) {
	await expect(page.locator('[data-console-panels="pipelines"]')).not.toHaveAttribute(
		'data-telemetry-state',
		'loading',
		{ timeout: 20_000 }
	);
}

/** Every panel on the page, keyed by its title, with the box it occupies. */
async function panelBoxes(page: Page): Promise<Record<string, [number, number, number, number]>> {
	return page.locator('[data-console-panel]').evaluateAll((nodes) => {
		const boxes: Record<string, [number, number, number, number]> = {};
		for (const node of nodes) {
			const box = node.getBoundingClientRect();
			boxes[node.getAttribute('data-console-panel') ?? ''] = [
				Math.round(box.x),
				Math.round(box.width),
				Math.round(box.height),
				// The offset from the top of the DOCUMENT, not the viewport: the
				// question is whether anything MOVED, and a scroll would answer it
				// wrongly either way.
				Math.round(box.top + window.scrollY)
			];
		}
		return boxes;
	});
}

/** Hold every month file for `HELD_MS`, so the waiting state can be measured. */
async function holdMonths(page: Page) {
	await page.route(TELEMETRY, async (route: Route) => {
		await new Promise((resolve) => setTimeout(resolve, HELD_MS));
		await route.continue();
	});
}

test('THE ORACLE: no console panel moves between the first frame and the settled page', async ({
	page
}) => {
	await page.setViewportSize({ width: 1280, height: 900 });
	await holdMonths(page);
	await page.goto('/console/');
	await hydrated(page);

	// While the months are in the air. Reading the boxes now is reading what an
	// operator sees in the first frame.
	await expect(page.locator('[data-console-panels="pipelines"]')).toHaveAttribute(
		'data-telemetry-state',
		'loading'
	);
	const first = await panelBoxes(page);
	expect(Object.keys(first).length, 'the page drew no panels at all').toBeGreaterThan(3);

	await settled(page);
	// A frame after the rows land, so layout has run.
	await page.screenshot();
	const after = await panelBoxes(page);

	expect(Object.keys(after).sort(), 'a panel appeared or vanished when the rows landed').toEqual(
		Object.keys(first).sort()
	);

	const moved = Object.keys(first)
		.filter((name) => JSON.stringify(first[name]) !== JSON.stringify(after[name]))
		.map((name) => `${name}: ${JSON.stringify(first[name])} -> ${JSON.stringify(after[name])}`);
	expect(moved, `panels moved when the payload landed:\n${moved.join('\n')}`).toEqual([]);
});

test('THE ORACLE: the reserved chart box is the box the chart takes', async ({ page }) => {
	await page.setViewportSize({ width: 1280, height: 900 });
	await holdMonths(page);
	await page.goto('/console/');
	await hydrated(page);

	const reserved = page.locator('[data-reserved="telemetry-viewport"]');
	await expect(reserved).toBeVisible();
	const waiting = await reserved.boundingBox();

	await settled(page);
	await page.screenshot();

	// The reserved box is gone and the charts are in its place. What has to hold
	// is the room: the surfaces that replaced it start where it started.
	await expect(reserved).toHaveCount(0);
	const replaced = await page.locator('[data-viewport-section] .mt-6').boundingBox();
	expect(waiting, 'nothing was reserved').not.toBeNull();
	expect(replaced, 'nothing replaced the reserved box').not.toBeNull();
	expect(Math.round((replaced as { y: number }).y)).toBe(Math.round((waiting as { y: number }).y));
	expect(Math.round((replaced as { x: number }).x)).toBe(Math.round((waiting as { x: number }).x));
	expect(Math.round((replaced as { width: number }).width)).toBe(
		Math.round((waiting as { width: number }).width)
	);
});

test('a waiting plot draws its axis frame and its ticks, and prints no number', async ({
	page
}) => {
	await page.setViewportSize({ width: 1280, height: 900 });
	await holdMonths(page);
	await page.goto('/console/');
	await hydrated(page);

	const frame = page.locator('[data-reserved-frame="telemetry-viewport"]');
	await expect(frame).toHaveAttribute('data-reserved-ticks', '6');
	// Two axes plus six ticks each way.
	expect(await frame.locator('line').count()).toBe(14);
	// A tick LABEL needs a value and there is no value, so an invented one is the
	// one thing a waiting plot may not print.
	expect(await frame.locator('text').count(), 'a waiting plot printed a number').toBe(0);
	await expect(page.locator('[data-reserved="telemetry-viewport"]')).toHaveAttribute(
		'aria-busy',
		'true'
	);
});

test('THE ORACLE: every shimmering block is on one timeline', async ({ page }) => {
	await page.setViewportSize({ width: 1280, height: 900 });
	await holdMonths(page);
	await page.goto('/console/');
	await hydrated(page);

	// The switch arrives late on purpose - `console.shimmer_after_ms` - so a
	// fetch that lands first never animates at all.
	await expect(page.locator('[data-console-panels="pipelines"]')).toHaveAttribute(
		'data-shimmer',
		'on',
		{ timeout: 5_000 }
	);
	await page.screenshot();

	const starts = await page.locator('[data-shimmer="on"] .loading').evaluateAll((nodes) =>
		nodes.flatMap((node) =>
			node.getAnimations().map((animation) => Math.round(Number(animation.startTime ?? -1)))
		)
	);
	expect(starts.length, 'nothing was animating').toBeGreaterThan(4);
	expect(
		new Set(starts).size,
		`blocks started their sweep at ${[...new Set(starts)].join(', ')} - out of phase`
	).toBe(1);
});

test('under reduced motion a reserved block is a flat tint, with no gradient frozen in it', async ({
	page
}) => {
	await page.emulateMedia({ reducedMotion: 'reduce' });
	await page.setViewportSize({ width: 1280, height: 900 });
	await holdMonths(page);
	await page.goto('/console/');
	await hydrated(page);
	await expect(page.locator('[data-console-panels="pipelines"]')).toHaveAttribute(
		'data-shimmer',
		'on',
		{ timeout: 5_000 }
	);
	await page.screenshot();

	const block = page.locator('[data-shimmer="on"] .loading').first();
	await expect(block).toBeVisible();

	// The blanket `animation-duration: 0.01ms !important` on `*` does not remove
	// a gradient - it freezes one mid-sweep. So the block has to lose the image
	// outright, and this is where that is proved rather than reasoned about.
	const look = await block.evaluate((node) => {
		const style = getComputedStyle(node);
		return {
			image: style.backgroundImage,
			colour: style.backgroundColor,
			running: node.getAnimations().length
		};
	});
	expect(look.image, 'a gradient survived reduced motion and is frozen mid-sweep').toBe('none');
	expect(look.running, 'an animation is still attached under reduced motion').toBe(0);
	expect(look.colour, 'the flat block has no tint, so it is not a block').not.toBe(
		'rgba(0, 0, 0, 0)'
	);
});

test('QUIET: a window that was read and held nothing says so, and names the widening', async ({
	page
}) => {
	await page.setViewportSize({ width: 1280, height: 900 });
	// Every month arrives, and every month is empty. That is a quiet pipeline and
	// nothing else - no gap, no failure.
	await page.route(TELEMETRY, (route: Route) =>
		route.fulfill({ status: 200, contentType: 'text/csv', body: EMPTY_CSV })
	);
	await page.goto('/console/');
	await settled(page);

	const surface = page.locator('[data-console-panels="pipelines"]');
	await expect(surface).toHaveAttribute('data-telemetry-state', 'quiet');

	const note = page.locator('[data-reserved-note="telemetry-viewport"]');
	await expect(note).toContainText('Nothing was recorded in these');
	// Neutral, never a warning: an empty window is an answer, not a fault.
	await expect(page.locator('[data-reserved="telemetry-viewport"]')).toHaveAttribute(
		'data-tone',
		'neutral'
	);
	await expect(page.locator('[data-reserved-retry="telemetry-viewport"]')).toHaveCount(0);
});

test('MISSING: months the pipeline never wrote are named, and read as a gap', async ({ page }) => {
	await page.setViewportSize({ width: 1280, height: 900 });

	// A hole mid-window: the band stops listing one of the months the window
	// reaches into, which is what a month the pipeline never wrote looks like.
	let dropped = '';
	await page.route(BAND, async (route: Route) => {
		const response = await route.fetch();
		const band = (await response.json()) as { months: string[] };
		dropped = band.months.at(-1) ?? '';
		band.months = band.months.filter((month) => month !== dropped);
		await route.fulfill({ json: band });
	});
	// The months that remain arrive and are empty, so the panel has nothing to
	// draw and the gap is the whole story.
	await page.route(TELEMETRY, (route: Route) =>
		route.fulfill({ status: 200, contentType: 'text/csv', body: EMPTY_CSV })
	);
	await page.goto('/console/');
	await settled(page);
	expect(dropped, 'the band listed no months, so no hole could be made').not.toBe('');

	const surface = page.locator('[data-console-panels="pipelines"]');
	await expect(surface).toHaveAttribute('data-telemetry-state', 'missing');

	const note = page.locator('[data-reserved-note="telemetry-viewport"]');
	await expect(note).toContainText('never recorded');
	await expect(note).toContainText('gap rather than a dip');
	// The dates are named, not left to be worked out from the axis.
	const year = dropped.slice(0, 4);
	await expect(note).toContainText(year);
	// No alarm and no retry: nothing went wrong and there is nothing to fetch.
	await expect(page.locator('[data-reserved="telemetry-viewport"]')).toHaveAttribute(
		'data-tone',
		'neutral'
	);
	await expect(page.locator('[data-reserved-retry="telemetry-viewport"]')).toHaveCount(0);
});

test('UNREACHABLE: a fetch that did not arrive names its month and offers a retry', async ({
	page
}) => {
	await page.setViewportSize({ width: 1280, height: 900 });
	let refuse = true;
	await page.route(TELEMETRY, async (route: Route) => {
		if (refuse) return route.abort();
		return route.continue();
	});
	await page.goto('/console/');
	await settled(page);

	const surface = page.locator('[data-console-panels="pipelines"]');
	await expect(surface).toHaveAttribute('data-telemetry-state', 'unreachable');

	const note = page.locator('[data-reserved-note="telemetry-viewport"]');
	await expect(note).toContainText('did not arrive');
	// A warn tint, and it is the only one of the four states that takes a hue.
	await expect(page.locator('[data-reserved="telemetry-viewport"]')).toHaveAttribute(
		'data-tone',
		'warn'
	);

	// The retry names its own subject, so it is still true read out of context.
	const retry = page.locator('[data-reserved-retry="telemetry-viewport"]');
	await expect(retry).toBeVisible();
	const label = ((await retry.textContent()) ?? '').trim();
	expect(label).toMatch(/^Try .+ again$/);

	// And it recovers rather than sulking for the rest of the page's life.
	refuse = false;
	await retry.click();
	await settled(page);
	await expect(surface).not.toHaveAttribute('data-telemetry-state', 'unreachable');
});

test('a blocked fetch and a quiet pipeline do not draw the same picture', async ({ page }) => {
	await page.setViewportSize({ width: 1280, height: 900 });

	await page.route(TELEMETRY, (route: Route) =>
		route.fulfill({ status: 200, contentType: 'text/csv', body: EMPTY_CSV })
	);
	await page.goto('/console/');
	await settled(page);
	const quiet = {
		state: await page
			.locator('[data-console-panels="pipelines"]')
			.getAttribute('data-telemetry-state'),
		tone: await page.locator('[data-reserved="telemetry-viewport"]').getAttribute('data-tone'),
		says: ((await page.locator('[data-reserved-note="telemetry-viewport"]').textContent()) ?? '')
			.replace(/\s+/g, ' ')
			.trim(),
		retries: await page.locator('[data-reserved-retry="telemetry-viewport"]').count()
	};

	await page.unroute(TELEMETRY);
	await page.route(TELEMETRY, (route: Route) => route.abort());
	await page.goto('/console/');
	await settled(page);
	const broken = {
		state: await page
			.locator('[data-console-panels="pipelines"]')
			.getAttribute('data-telemetry-state'),
		tone: await page.locator('[data-reserved="telemetry-viewport"]').getAttribute('data-tone'),
		says: ((await page.locator('[data-reserved-note="telemetry-viewport"]').textContent()) ?? '')
			.replace(/\s+/g, ' ')
			.trim(),
		retries: await page.locator('[data-reserved-retry="telemetry-viewport"]').count()
	};

	// This is the whole reason the row exists. Three ways apart, not one.
	expect(broken.state).not.toBe(quiet.state);
	expect(broken.tone).not.toBe(quiet.tone);
	expect(broken.says).not.toBe(quiet.says);
	expect(quiet.retries).toBe(0);
	expect(broken.retries).toBe(1);
});

test('with no script the console says its panels are empty rather than leaving them bare', async ({
	page
}) => {
	// The signpost is in the document, not conditionally rendered, so it is there
	// for the reader who never runs a line of our code.
	const document = await (await page.request.get('/console/')).text();
	expect(document).toContain('data-console-noscript');
	expect(document).toContain('month files a browser fetches');

	// And it is hidden from everyone else. `<noscript>` does that itself; this
	// is the check that nothing overrode it.
	await page.goto('/console/');
	await expect(page.locator('[data-console-noscript]')).toBeHidden();
});
