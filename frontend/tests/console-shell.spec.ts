import { expect, test, type Page } from './support/door-page';
import { BAND_UNREAD, type RouteId } from '../src/lib/console/band';
import { BY_ROUTE } from './support/console-expect/console-shell';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import {
	completenessOf,
	completenessSentence,
	spelledInstant,
	untilNextUtcDay
} from '../src/lib/console/completeness';

/**
 * The console's shell: the strip that sticks from the wide breakpoint up, the
 * sentence under it that dates the record, the jump links on a long route, and
 * the site line that drops on the console.
 *
 * The oracle is the one the row was written for. At 1440 the stuck strip is one
 * row and every jump link lands its heading below the strip rather than behind
 * it; at 768 nothing is stuck. And the strip is held to one row with one tab
 * more than the console has, because the next route is already foreseen and
 * adding it has to be a list entry, never a layout change - and with as many
 * more as it takes to make the tab list scroll, so the scrolling case is
 * checked whatever width today's tabs happen to be.
 *
 * Every geometry figure is printed beside `window.innerWidth`, because a
 * viewport asked for and a viewport rendered are two numbers.
 */

type Appearance = {
	frame: { breakpoints_px: [number, number, number] };
	console: {
		completeness_grace_days: number;
	};
};

/** The committed appearance file. Read inside the test that needs it, so a
 * shape it does not expect fails that test and not the whole file. */
function appearance(): Appearance {
	return JSON.parse(
		readFileSync(resolve(process.cwd(), '..', 'config', 'appearance.json'), 'utf8')
	) as Appearance;
}

const WIDE = { width: 1440, height: 1000 };
const NARROW = { width: 768, height: 1000 };
const DAY_MS = 86_400_000;

function routeHref(id: RouteId): string {
	const route = BAND_UNREAD.routes.find((route) => route.id === id);
	if (!route) throw new Error(`The console names no route ${id}`);
	return route.href;
}

/** The strip sticks only once a script has run, and the days control is
 * enabled in the same mount - so both are waited for. */
async function hydrated(page: Page): Promise<void> {
	await expect(page.locator('[data-console-strip]')).toHaveAttribute('data-console-strip-live', 'yes');
	await expect(page.locator('[data-window-preset] input').first()).toBeEnabled();
}

/** Scroll so the strip has left its place in the flow by a screen's worth. */
async function scrollPastStrip(page: Page): Promise<void> {
	await page.evaluate(() => {
		const strip = document.querySelector('[data-console-strip]') as HTMLElement;
		const top = strip.getBoundingClientRect().top + window.scrollY;
		window.scrollTo({ top: top + 600, behavior: 'instant' });
	});
}

/** An element's top in page coordinates. */
async function pageTop(page: Page, selector: string): Promise<number> {
	return page
		.locator(selector)
		.first()
		.evaluate((node) => Math.round(node.getBoundingClientRect().top + window.scrollY));
}

/** The strip, its tabs and its control, in viewport coordinates. */
async function stripGeometry(page: Page) {
	return page.evaluate(() => {
		const strip = document.querySelector('[data-console-strip]') as HTMLElement;
		const box = strip.getBoundingClientRect();
		const list = strip.querySelector('[data-console-nav] ul') as HTMLElement;
		const control = (strip.querySelector('[data-window-control]') as HTMLElement).getBoundingClientRect();
		return {
			innerWidth: window.innerWidth,
			position: getComputedStyle(strip).position,
			stuck: strip.getAttribute('data-console-strip-stuck'),
			top: Math.round(box.top),
			bottom: Math.round(box.bottom),
			height: Math.round(box.height),
			right: Math.round(box.right),
			scrolls: list.scrollWidth > list.clientWidth,
			tabs: [...strip.querySelectorAll('[data-console-tab]')].map((node) => {
				const tab = node.getBoundingClientRect();
				return {
					id: node.getAttribute('data-console-tab') ?? '',
					top: Math.round(tab.top),
					height: Math.round(tab.height)
				};
			}),
			control: {
				top: Math.round(control.top),
				bottom: Math.round(control.bottom),
				right: Math.round(control.right)
			}
		};
	});
}

/** One more tab than the console has, cloned from the last one. The strip's
 * rules are about any number of tabs, and this is the one more that the next
 * route will be. */
async function addTab(page: Page): Promise<void> {
	await page.evaluate(() => {
		const list = document.querySelector('[data-console-nav] ul') as HTMLElement;
		const copy = list.lastElementChild?.cloneNode(true) as HTMLElement;
		const tab = copy.querySelector('[data-console-tab]') as HTMLElement;
		tab.setAttribute('data-console-tab', 'one-more');
		tab.removeAttribute('aria-current');
		(copy.querySelector('.tab-label') as HTMLElement).textContent = 'Security';
		list.append(copy);
		window.dispatchEvent(new Event('resize'));
	});
}

/** Tabs added one at a time until the row cannot hold them, so the list has to
 * scroll. How many that takes depends on how wide today's tabs are, which is
 * why it is counted rather than fixed. A list that wraps instead stops the
 * count too, and the one-row check then says so. */
async function addTabsUntilTheListScrolls(page: Page): Promise<number> {
	for (let added = 1; added <= 12; added += 1) {
		await addTab(page);
		const full = await page.evaluate(() => {
			const list = document.querySelector('[data-console-nav] ul') as HTMLElement;
			const tops = [...list.querySelectorAll('[data-console-tab]')].map((tab) =>
				Math.round(tab.getBoundingClientRect().top)
			);
			return list.scrollWidth > list.clientWidth || new Set(tops).size > 1;
		});
		if (full) return added;
	}
	throw new Error('twelve more tabs still fitted one row, so the list never had to scroll');
}

const CASES: { name: string; grow: (page: Page) => Promise<number>; mustScroll: boolean }[] = [
	{ name: 'the routes the console has', grow: async () => 0, mustScroll: false },
	{
		name: 'one tab more than it has',
		grow: async (page) => {
			await addTab(page);
			return 1;
		},
		mustScroll: false
	},
	{ name: 'more tabs than the row holds', grow: addTabsUntilTheListScrolls, mustScroll: true }
];

for (const { name, grow, mustScroll } of CASES) {
	test(`THE ORACLE: at 1440 the stuck strip is one row, with ${name}`, async ({ page }) => {
		await page.setViewportSize(WIDE);
		await page.goto(routeHref('machine'));
		await hydrated(page);
		const extra = await grow(page);

		await scrollPastStrip(page);
		const strip = page.locator('[data-console-strip]');
		await expect(strip).toHaveAttribute('data-console-strip-stuck', 'yes');
		const at = await stripGeometry(page);
		console.log(
			`[strip] asked ${WIDE.width} -> innerWidth ${at.innerWidth}, ${at.tabs.length} tabs, ` +
				`strip ${at.top}-${at.bottom} (${at.height}px), scrolls ${at.scrolls}, tabs ` +
				at.tabs.map((tab) => `${tab.id}@${tab.top}x${tab.height}`).join(' ')
		);

		expect(at.position, 'the strip does not stick at 1440').toBe('sticky');
		expect(at.top, 'the stuck strip is not at the top of the screen').toBe(0);
		expect(at.tabs).toHaveLength(6 + extra);
		// One row: every tab starts at one height, the control sits inside the
		// strip's own band, and the strip is shorter than two tabs stacked.
		expect(new Set(at.tabs.map((tab) => tab.top)).size, 'the tabs stand on more than one row').toBe(1);
		// And one height: the active route's rule is each tab's bottom edge, so a
		// shorter tab - one with no worst state - would float it above the others.
		expect(new Set(at.tabs.map((tab) => tab.height)).size, 'the tabs are not one height').toBe(1);
		const tallest = Math.max(...at.tabs.map((tab) => tab.height));
		expect(at.height, `the stuck strip is ${at.height}px, two rows of ${tallest}px tabs`).toBeLessThan(
			2 * tallest
		);
		expect(at.control.top).toBeGreaterThanOrEqual(at.top);
		expect(at.control.bottom).toBeLessThanOrEqual(at.bottom);
		// And the control stays pinned at the trailing end, scrolling list or not.
		expect(Math.abs(at.control.right - at.right), 'the control left the end of the strip').toBeLessThanOrEqual(1);
		if (mustScroll) {
			expect(at.scrolls, 'the stuck strip made room, so this case never asked the list to scroll').toBe(true);
		}
	});
}

test("from the breakpoint up a tab's worst state stands under its label, and every label starts level", async ({
	page
}) => {
	// Side by side, a tab is as wide as its label and its worst state together,
	// and on the landing route the fifth tab stayed out of view at every width
	// up to 1920. Stacked, a tab is as wide as the longer of the two.
	await page.setViewportSize(WIDE);
	await page.goto(routeHref('pipelines'));
	await hydrated(page);
	const at = await page.evaluate(() => {
		const list = document.querySelector('[data-console-nav] ul') as HTMLElement;
		const shown = list.getBoundingClientRect();
		const tabs = [...document.querySelectorAll('[data-console-tab]')].map((node) => {
			const label = (node.querySelector('.tab-label') as HTMLElement).getBoundingClientRect();
			const state = node.querySelector('.tab-state')?.getBoundingClientRect() ?? null;
			const tab = node.getBoundingClientRect();
			return {
				id: node.getAttribute('data-console-tab') ?? '',
				labelTop: Math.round(label.top),
				labelBottom: Math.round(label.bottom),
				stateTop: state === null ? null : Math.round(state.top),
				whole: tab.left >= shown.left - 1 && tab.right <= shown.right + 1
			};
		});
		return { innerWidth: window.innerWidth, tabs };
	});
	console.log(
		`[tabs] asked ${WIDE.width} -> innerWidth ${at.innerWidth}, ` +
			`${at.tabs.filter((tab) => tab.whole).length} of ${at.tabs.length} whole, ` +
			at.tabs.map((tab) => `${tab.id} label@${tab.labelTop} state@${tab.stateTop}`).join(' ')
	);

	const stated = at.tabs.filter((tab) => tab.stateTop !== null);
	expect(stated.length, 'no tab carries a worst state, so nothing here was checked').toBeGreaterThan(0);
	for (const tab of stated) {
		expect(tab.stateTop, `${tab.id}'s worst state stands beside its label`).toBeGreaterThanOrEqual(
			tab.labelBottom - 1
		);
	}
	expect(new Set(at.tabs.map((tab) => tab.labelTop)).size, 'the labels do not start level').toBe(1);
});

test('THE ORACLE: at 1024 every console route opens with its own tab whole', async ({ page }) => {
	// The narrowest width the strip is one row. When the tabs are wider than the
	// row the list scrolls, and a page that opened with its own tab cut off would
	// not say which route it is. The band's worst route is brought into view only
	// where the reader's own tab stays whole beside it.
	await page.setViewportSize({ width: 1024, height: 900 });
	for (const id of Object.keys(BY_ROUTE) as RouteId[]) {
		if (BY_ROUTE[id] === null) continue;
		const path = routeHref(id);
		await page.goto(path);
		await hydrated(page);
		const at = await page.evaluate(() => {
			const list = document.querySelector('[data-console-nav] ul') as HTMLElement;
			const shown = list.getBoundingClientRect();
			const own = document.querySelector('[data-console-tab-active="true"]') as HTMLElement;
			const tab = own.getBoundingClientRect();
			return {
				innerWidth: window.innerWidth,
				id: own.getAttribute('data-console-tab'),
				scrolls: list.scrollWidth > list.clientWidth,
				whole: tab.left >= shown.left - 1 && tab.right <= shown.right + 1
			};
		});
		console.log(
			`[own tab] ${path} asked 1024 -> innerWidth ${at.innerWidth}, ${at.id} whole ${at.whole}, list scrolls ${at.scrolls}`
		);
		expect(at.whole, `${path} opens with its own tab, ${at.id}, cut off`).toBe(true);
	}
});

test('THE ORACLE: every jump link lands its heading below the stuck strip', async ({ page }) => {
	await page.setViewportSize(WIDE);
	await page.goto(routeHref('machine'));
	await hydrated(page);

	const groups = BY_ROUTE.machine!.groups;
	const links = page.locator('[data-console-contents] [data-console-contents-link]');
	await expect(links).toHaveCount(groups.length);

	for (const group of groups) {
		await page.locator(`[data-console-contents-link="${group.id}"]`).click();
		await expect(page).toHaveURL(new RegExp(`#${group.id}$`));
		await expect(page.locator('[data-console-strip]')).toHaveAttribute('data-console-strip-stuck', 'yes');
		const landed = await page.evaluate((id) => {
			const strip = (document.querySelector('[data-console-strip]') as HTMLElement).getBoundingClientRect();
			const heading = (
				document.querySelector(`[data-console-group="${id}"] > h2`) as HTMLElement
			).getBoundingClientRect();
			return {
				innerWidth: window.innerWidth,
				stripBottom: Math.round(strip.bottom),
				headingTop: Math.round(heading.top),
				headingBottom: Math.round(heading.bottom),
				innerHeight: window.innerHeight
			};
		}, group.id);
		console.log(
			`[anchor] innerWidth ${landed.innerWidth}: ${group.id} heading at ${landed.headingTop}, ` +
				`strip ends at ${landed.stripBottom}`
		);
		expect(
			landed.headingTop,
			`${group.id} landed behind the strip: heading at ${landed.headingTop}, strip ends at ${landed.stripBottom}`
		).toBeGreaterThanOrEqual(landed.stripBottom);
		expect(landed.headingBottom, `${group.id} landed off the screen`).toBeLessThanOrEqual(
			landed.innerHeight
		);
	}

	// And a group's own Top link goes back to the head of the console, where the
	// strip is in its place again.
	await page.locator('[data-console-group-top]').last().click();
	await expect(page).toHaveURL(/#console-top$/);
	await expect(page.locator('[data-console-strip]')).toHaveAttribute('data-console-strip-stuck', 'no');
});

test('THE ORACLE: at 768 nothing is stuck', async ({ page }) => {
	await page.setViewportSize(NARROW);
	await page.goto(routeHref('machine'));
	await hydrated(page);
	await scrollPastStrip(page);

	const at = await stripGeometry(page);
	console.log(`[strip] asked ${NARROW.width} -> innerWidth ${at.innerWidth}, position ${at.position}, top ${at.top}`);
	expect(at.position, 'the strip sticks below the wide breakpoint').not.toBe('sticky');
	expect(at.stuck).not.toBe('yes');
	expect(at.top, 'the strip is still on the screen after scrolling past it').toBeLessThan(0);
	const padding = await page.evaluate(() => document.documentElement.style.scrollPaddingTop);
	expect(padding, 'the page still keeps room for a strip that is not stuck').toBe('');
});

test('the strip sticks from the configured breakpoint and not a pixel before it', async ({ page }) => {
	// A media query cannot read the knob, so the stylesheet repeats its value.
	// This is the test that holds the two in step: move `frame.breakpoints_px[1]`
	// without the stylesheet and one of these two widths fails.
	const stick = appearance().frame.breakpoints_px[1];
	for (const [width, sticks] of [
		[stick - 1, false],
		[stick, true]
	] as const) {
		await page.setViewportSize({ width, height: 900 });
		await page.goto(routeHref('machine'));
		await hydrated(page);
		const at = await stripGeometry(page);
		console.log(`[strip] asked ${width} -> innerWidth ${at.innerWidth}, position ${at.position}`);
		expect(at.position === 'sticky', `at innerWidth ${at.innerWidth} the strip sticks: ${at.position}`).toBe(
			sticks
		);
	}
});

test('the page does not move when the strip sticks and drops its descriptions', async ({ page }) => {
	await page.setViewportSize(WIDE);
	await page.goto(routeHref('machine'));
	await hydrated(page);

	const loose = await stripGeometry(page);
	const bandBefore = await pageTop(page, '[data-console-band]');
	const panelBefore = await pageTop(page, '[data-console-panel]');
	await scrollPastStrip(page);
	await expect(page.locator('[data-console-strip]')).toHaveAttribute('data-console-strip-stuck', 'yes');
	const stuck = await stripGeometry(page);

	console.log(
		`[strip] innerWidth ${stuck.innerWidth}: ${loose.height}px at the top, ${stuck.height}px stuck; ` +
			`band ${bandBefore} -> ${await pageTop(page, '[data-console-band]')}`
	);
	// The strip really did get shorter, or the rest of this proves nothing.
	expect(stuck.height, 'the stuck strip kept its descriptions').toBeLessThan(loose.height);
	expect(await pageTop(page, '[data-console-band]'), 'the band moved when the strip stuck').toBe(
		bandBefore
	);
	expect(await pageTop(page, '[data-console-panel]'), 'the panels moved when the strip stuck').toBe(
		panelBefore
	);
});

test('the days control is on the strip at every width, and its sentence is under the band', async ({
	page
}) => {
	for (const size of [WIDE, NARROW, { width: 390, height: 844 }]) {
		await page.setViewportSize(size);
		await page.goto(routeHref('pipelines'));
		await hydrated(page);
		await expect(page.locator('[data-console-strip] [data-window-control]')).toHaveCount(1);
		await expect(page.locator('[data-console-strip] [data-window-status]')).toHaveCount(0);
		const band = await pageTop(page, '[data-console-band]');
		const status = await pageTop(page, '[data-window-status]');
		expect(status, `at ${size.width} the days sentence is not under the band`).toBeGreaterThan(band);
	}
});

test('a route with named groups carries a jump link to each, and a flat route carries none', async ({
	page
}) => {
	const groups = BY_ROUTE.machine!.groups;
	await page.goto(routeHref('machine'));
	const links = await page
		.locator('[data-console-contents] [data-console-contents-link]')
		.evaluateAll((nodes) =>
			nodes.map((node) => ({
				href: node.getAttribute('href') ?? '',
				text: (node.textContent ?? '').trim()
			}))
		);
	expect(links.map((link) => link.text)).toEqual(groups.map((group) => group.title));
	expect(links.map((link) => link.href)).toEqual(groups.map((group) => `#${group.id}`));
	for (const group of groups) {
		// One element answers each link, or a link lands on whichever came first.
		await expect(page.locator(`[id="${group.id}"]`)).toHaveCount(1);
		await expect(page.locator(`[data-console-group="${group.id}"] [data-console-group-top]`)).toHaveAttribute(
			'href',
			'#console-top'
		);
	}
	await expect(page.locator('#console-top')).toHaveCount(1);

	// Pipelines takes one untitled group: an order, with nothing to jump between.
	await page.goto(routeHref('pipelines'));
	await expect(page.locator('[data-console-contents]')).toHaveCount(BY_ROUTE.pipelines!.groups.length);
});

test('the site line drops on the console and stays on the reading pages', async ({ page }) => {
	await page.goto(routeHref('pipelines'));
	await expect(page.locator('[data-site-tagline]')).toBeHidden();
	await page.goto('/');
	await expect(page.locator('[data-site-tagline]')).toBeVisible();
});

test("the band's first fact is named for the newest day, never for yesterday", async ({ page }) => {
	// The verdict is the newest day the record holds, which is today once
	// today's first run has finished. A label that said "Yesterday" sat under a
	// sentence dating the same run to today.
	await page.goto(routeHref('pipelines'));
	await expect(page.locator('[data-band-verdict-label]')).toHaveText('Latest day');
	await expect(page.locator('[data-console-band]')).not.toContainText('Yesterday');
});

test.describe('the sentence that dates the record', () => {
	/** The band's own instant, read off the site the suite serves. */
	async function finished(page: Page): Promise<number> {
		const band = (await (await page.request.get('/console/band.json')).json()) as {
			generated_at: string;
		};
		return Date.parse(band.generated_at);
	}

	/** The instant as the page is meant to spell it, written out here without
	 * the module under test, so the two can disagree. Built from the parts, so
	 * a runtime that puts a comma after the weekday cannot fail it. */
	function spelled(at: number): string {
		const parts = new Intl.DateTimeFormat('en-GB', {
			weekday: 'long',
			day: 'numeric',
			month: 'long',
			timeZone: 'UTC'
		}).formatToParts(new Date(at));
		const part = (type: string) => parts.find((entry) => entry.type === type)?.value ?? '';
		return `${new Date(at).toISOString().slice(11, 16)} UTC on ${part('weekday')} ${part('day')} ${part('month')}`;
	}

	test('with no clock to judge by, the page dates the record and claims nothing else', async ({
		page
	}) => {
		const at = await finished(page);
		const document = await (await page.request.get(routeHref('pipelines'))).text();
		expect(document).toContain(
			`The latest run on this page finished at ${spelled(at)}. A run still going is not on this page yet.`
		);
		expect(document).toContain('data-console-completeness="complete"');
	});

	test('a record inside the grace says it is complete, and one past it counts the days', async ({
		page
	}) => {
		const grace = appearance().console.completeness_grace_days;
		const at = await finished(page);
		const recordDay = Math.floor(at / DAY_MS) * DAY_MS;
		const sentence = page.locator('[data-console-completeness]');

		// Just after midnight UTC on the last day inside the grace.
		await page.clock.setFixedTime(new Date(recordDay + grace * DAY_MS + 30_000));
		await page.goto(routeHref('pipelines'));
		await hydrated(page);
		await expect(sentence).toHaveAttribute('data-console-completeness', 'complete');
		await expect(sentence).toHaveText(
			`The latest run on this page finished at ${spelled(at)}. A run still going is not on this page yet.`
		);

		// And the first day past it: every whole day between the record's and today.
		for (const past of [1, 2]) {
			const missing = grace + past - 1;
			await page.clock.setFixedTime(new Date(recordDay + (grace + past) * DAY_MS + 30_000));
			await page.goto(routeHref('pipelines'));
			await hydrated(page);
			await expect(sentence).toHaveAttribute('data-console-completeness', 'behind');
			await expect(sentence).toHaveText(
				`Nothing has been recorded since ${spelled(at)}. ` +
					(missing === 1 ? '1 day is missing.' : `${missing} days are missing.`)
			);
		}
	});

	test('the late sentence takes the main text colour and no verdict colour', async ({ page }) => {
		const grace = appearance().console.completeness_grace_days;
		const at = await finished(page);
		await page.clock.setFixedTime(new Date(at + (grace + 3) * DAY_MS));
		await page.goto(routeHref('pipelines'));
		await hydrated(page);
		const colours = await page.evaluate(() => {
			const probe = (value: string) => {
				const span = document.createElement('span');
				span.style.color = value;
				document.body.appendChild(span);
				const read = getComputedStyle(span).color;
				span.remove();
				return read;
			};
			const sentence = document.querySelector('[data-console-completeness]') as HTMLElement;
			return {
				drawn: getComputedStyle(sentence).color,
				text: probe('var(--color-text)'),
				verdict: ['--band-low', '--fill-low', '--band-medium', '--fill-medium'].map((token) =>
					probe(`var(${token})`)
				)
			};
		});
		expect(colours.drawn).toBe(colours.text);
		expect(colours.verdict).not.toContain(colours.drawn);
	});
});

test.describe('how complete the record is, as arithmetic', () => {
	// 18:23:02 UTC on Sunday 27 September 2026.
	const FINISHED = '2026-09-27T18:23:02Z';
	const at = Date.parse(FINISHED);
	const midnight = Date.parse('2026-09-27T00:00:00Z');

	test('no record is a named absence, and no clock claims nothing about age', () => {
		expect(completenessOf(null, at, 1)).toEqual({ kind: 'unread' });
		expect(completenessOf('not a time', at, 1)).toEqual({ kind: 'unread' });
		expect(completenessOf(FINISHED, null, 1)).toEqual({ kind: 'complete', finished: at });
		expect(completenessSentence({ kind: 'unread' })).toBe(
			'This page cannot say when the last run finished - its record did not load.'
		);
	});

	test('the day boundary is 00:00 UTC, and the grace moves only when the count is said', () => {
		expect(completenessOf(FINISHED, midnight + DAY_MS - 1, 1).kind).toBe('complete');
		expect(completenessOf(FINISHED, midnight + 2 * DAY_MS - 1, 1).kind).toBe('complete');
		expect(completenessOf(FINISHED, midnight + 2 * DAY_MS, 1)).toEqual({
			kind: 'behind',
			finished: at,
			missingDays: 1
		});
		// A wider grace says it later, and counts the same days when it does.
		expect(completenessOf(FINISHED, midnight + 3 * DAY_MS, 2)).toEqual({
			kind: 'behind',
			finished: at,
			missingDays: 2
		});
		expect(completenessOf(FINISHED, midnight + 3 * DAY_MS, 1)).toEqual({
			kind: 'behind',
			finished: at,
			missingDays: 2
		});
		// A reader whose clock is behind the record is not told anything is late.
		expect(completenessOf(FINISHED, at - DAY_MS, 1).kind).toBe('complete');
	});

	test('the instant is spelled in UTC, with the weekday and never "today"', () => {
		expect(spelledInstant(at)).toBe('18:23 UTC on Sunday 27 September');
		expect(completenessSentence({ kind: 'complete', finished: at })).toBe(
			'The latest run on this page finished at 18:23 UTC on Sunday 27 September. A run still going is not on this page yet.'
		);
		expect(completenessSentence({ kind: 'behind', finished: at, missingDays: 1 })).toBe(
			'Nothing has been recorded since 18:23 UTC on Sunday 27 September. 1 day is missing.'
		);
		expect(completenessSentence({ kind: 'behind', finished: at, missingDays: 4 })).toBe(
			'Nothing has been recorded since 18:23 UTC on Sunday 27 September. 4 days are missing.'
		);
	});

	test('the page looks again at the next 00:00 UTC and not before', () => {
		expect(untilNextUtcDay(at)).toBe(midnight + DAY_MS - at);
		expect(untilNextUtcDay(midnight)).toBe(DAY_MS);
	});
});
