import { expect, test, type Page, type Route } from '@playwright/test';
import { telemetryCsv } from '../src/lib/charts/series';

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

/** A telemetry shard with a header and no rows. Valid, parses, holds nothing -
 * which is what a genuinely quiet month looks like on the wire.
 *
 * Written by the same function the pipeline writes shards with. A header copied
 * into this file would be right on the day it was copied: the reader refuses a
 * shard whose columns do not match the contract, and a refused shard is
 * indistinguishable here from a fetch that never arrived. */
const EMPTY_CSV = telemetryCsv([]);

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

/** The one panel on this route whose content comes out of the fetch.
 *
 * Its body is a chart, a readout strip and a shape switch, and the last two
 * exist only once there is a series to read and a shape to switch - so its box
 * grows when the rows land, and it is the ONLY box that may. Naming it here is
 * what makes the oracle below strong: a second panel that starts changing size
 * fails, whatever the reason.
 */
const FETCHED_PANEL = 'What is failing, by stage';

test('THE ORACLE: only the panel that is waiting for rows changes size', async ({ page }) => {
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

	// Size, not position: a panel below a region that grew has moved down, and
	// that is arithmetic rather than a defect. A panel that RESIZED is a panel
	// that reserved the wrong room.
	const resized = Object.keys(first)
		.filter((name) => first[name][1] !== after[name][1] || first[name][2] !== after[name][2])
		.map((name) => `${name}: ${JSON.stringify(first[name])} -> ${JSON.stringify(after[name])}`);
	expect(resized, `panels changed size when the payload landed:\n${resized.join('\n')}`).toEqual([
		`${FETCHED_PANEL}: ${JSON.stringify(first[FETCHED_PANEL])} -> ${JSON.stringify(
			after[FETCHED_PANEL]
		)}`
	]);
});

test('THE ORACLE: nothing in the first viewport moves when the payload lands', async ({ page }) => {
	await page.setViewportSize({ width: 1280, height: 900 });
	await holdMonths(page);
	await page.goto('/console/');
	await hydrated(page);
	const first = await panelBoxes(page);

	// Everything an operator can already see. Moving one of these is the failure
	// the reserved shape exists to prevent - it moves what somebody is reading.
	const visible = Object.keys(first).filter((name) => first[name][3] < 900);
	expect(visible.length, 'no panel was in the first viewport at all').toBeGreaterThan(0);

	await settled(page);
	await page.screenshot();
	const after = await panelBoxes(page);

	const moved = visible
		.filter((name) => JSON.stringify(first[name]) !== JSON.stringify(after[name]))
		.map((name) => `${name}: ${JSON.stringify(first[name])} -> ${JSON.stringify(after[name])}`);
	expect(moved, `the first viewport moved under the operator:\n${moved.join('\n')}`).toEqual([]);
});

test('THE ORACLE: the reserved chart box is the box the chart takes', async ({ page }) => {
	await page.setViewportSize({ width: 1280, height: 900 });
	await holdMonths(page);
	await page.goto('/console/');
	await hydrated(page);

	const reserved = page.locator('[data-reserved="telemetry-viewport"]');
	await expect(reserved).toBeVisible();
	const waiting = await reserved.boundingBox();
	const waitingSection = (
		(await page.locator('[data-viewport-section]').boundingBox()) as { y: number }
	).y;
	// The box is exactly the chart height it reserves, and never an inch more.
	expect(Math.round((waiting as { height: number }).height)).toBe(220);

	await settled(page);
	await page.screenshot();

	// The reserved box is gone and the charts are in its place. What has to hold
	// is the room INSIDE the section: the surfaces that replaced the box start
	// where the box started. Measured against the section rather than the page,
	// because the failure-mix panel above grows when its rows land and carries
	// this whole section down with it - which is arithmetic, not a shift here.
	await expect(reserved).toHaveCount(0);
	const section = await page.locator('[data-viewport-section]').boundingBox();
	const replaced = await page.locator('[data-viewport-body]').boundingBox();
	expect(waiting, 'nothing was reserved').not.toBeNull();
	expect(replaced, 'nothing replaced the reserved box').not.toBeNull();
	expect(Math.round((replaced as { y: number }).y - (section as { y: number }).y)).toBe(
		Math.round((waiting as { y: number }).y - waitingSection)
	);
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

	// The hole is in the built fixture and is not injected here. The canary's
	// band lists three months, and the widest preset reaches back past all of
	// them - so the months before the first shard are inside the window and were
	// never written, which is exactly what a real gap is.
	await page.route(TELEMETRY, (route: Route) =>
		route.fulfill({ status: 200, contentType: 'text/csv', body: EMPTY_CSV })
	);
	await page.goto('/console/');
	await settled(page);

	await page.locator('[data-window-preset]').last().click();
	await settled(page);

	const surface = page.locator('[data-console-panels="pipelines"]');
	await expect(surface).toHaveAttribute('data-telemetry-state', 'missing');

	const note = page.locator('[data-reserved-note="telemetry-viewport"]');
	await expect(note).toContainText('never recorded');
	await expect(note).toContainText('gap rather than a dip');
	// The dates are named in words, not left to be worked out from the axis.
	await expect(note).toContainText(
		/\b(January|February|March|April|May|June|July|August|September|October|November|December) 20\d\d\b/
	);
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
