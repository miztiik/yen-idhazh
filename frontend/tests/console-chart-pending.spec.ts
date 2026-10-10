import { expect, test, type Page } from './support/browser';
import { BAND_UNREAD } from '../src/lib/console/band';
import { BY_ROUTE } from './support/console-expect/console-chart-pending';

/**
 * What stands in a browser-drawn chart's box until a mark lands there, and what
 * stands there when the chart script never arrives.
 *
 * Five console charts have no server picture: the browser draws them, and it
 * draws a chart only once it comes within one screen of the viewport. So for
 * every such chart further down the page, "not drawn yet" is the normal state,
 * and the box holds a sentence that says so. Until 2026-09-27 the component
 * decided it had drawn the moment the engine's small first file arrived. The
 * sentence went away while the host still said `data-chart="waiting"`, and the
 * box stayed empty until somebody scrolled to it - or for the rest of the visit,
 * when the chart library never downloaded.
 *
 * The engine already publishes the moment of truth on the host, `data-chart`,
 * and these cases hold the component's words to it. The sentence is on the page
 * exactly while the host has not drawn, `data-chart-drawn` on the figure says
 * `yes` only once a mark is on screen, and a download that failed swaps the
 * sentence for one that says the chart did not load.
 *
 * The bite, run 2026-09-27 on the canary build of 0236e868f, before the fix:
 * all four cases fail, each on its own line. The oracle reads
 * `data-chart-drawn="yes"` over a host that still says `waiting`. A refused
 * engine module leaves the box promising a chart that cannot come. A refused
 * chart library leaves no host saying so. And with no script, nothing in the
 * box separates the promise from the words a reader can use.
 */

const DESKTOP = { width: 1440, height: 900 };
/** A short window puts the draw line high. At a desktop's height the first
 * browser-drawn chart on Pipelines sits about two hundred pixels past the
 * line, where a platform's fonts can decide which side of it the chart lands;
 * at this height it sits several hundred past, and the case reads the same
 * charts on any machine. */
const SHORT = { width: 1440, height: 600 };
const PHONE = { width: 360, height: 900 };
/** The engine and the chart library are network fetches, so a draw is not
 * instant. */
const DRAWN = 20_000;
/** Every built script the page can ask for. The chunk a case refuses is picked
 * out of these by what it holds. */
const BUILT_SCRIPTS = '**/_app/immutable/**/*.js';

interface Undrawn {
	/** The figure's accessible name. Two panels here fill in when their rows
	 * arrive, so a figure's position in the document can move under a case, and
	 * its name cannot. */
	label: string;
	/** Distance from the top of the document to the plot's box. */
	top: number;
}

/** Every chart on the page that a reader can see the box of, that has no marks
 * in it yet and no server picture to keep: its host holds no `<svg>`. */
async function undrawnCharts(page: Page): Promise<Undrawn[]> {
	return page.evaluate(() =>
		[...document.querySelectorAll('figure[data-chart-drawn]')].flatMap((figure) => {
			const host = figure.querySelector('.chart-host');
			if (host === null || host.querySelector('svg') !== null) return [];
			const box = host.getBoundingClientRect();
			if (box.height === 0) return [];
			return [{ label: figure.getAttribute('aria-label') ?? '', top: box.top + window.scrollY }];
		})
	);
}

/** The charts a reader has not come near: past the fold plus the one screen of
 * reach the engine gives a chart before it draws. The line is read off the
 * page's own window rather than typed here. */
async function chartsBelowTheDrawLine(page: Page): Promise<Undrawn[]> {
	const line = await page.evaluate(() => window.innerHeight * 2);
	const undrawn = await undrawnCharts(page);
	const far = undrawn.filter((one) => one.top > line);
	const lowest = Math.max(...undrawn.map((one) => Math.round(one.top)), 0);
	expect(
		far.length,
		`no browser-drawn chart sits below the ${line}px draw line - the lowest is at ${lowest}px - so this case cannot see the defect`
	).toBeGreaterThan(0);
	return far;
}

function figureNamed(page: Page, label: string) {
	return page.getByRole('figure', { name: label, exact: true });
}

/** Come to a chart the way a reader does. Instant rather than smooth, because a
 * smooth scroll is still moving when the next line reads the page. */
async function comeTo(page: Page, label: string): Promise<void> {
	await figureNamed(page, label).evaluate((node) =>
		node.scrollIntoView({ behavior: 'instant', block: 'center' })
	);
}

/** Refuse the one built script whose text holds `marker`, and report every path
 * that was refused.
 *
 * This is FAULT INJECTION on a real page, not a mock. The build, the server and
 * the page are the real ones; the only change is that one download fails, which
 * is what an offline reader, a dropped connection or a blocking extension does
 * to it. The file is picked by what it holds because its name is a content hash
 * - the method `console-chart-lifetime.spec.ts` uses, read off the response here
 * rather than off the build directory. The config blocks service workers, so no
 * worker can answer the request from its own cache and hide the refusal. */
async function refuse(page: Page, marker: string): Promise<Set<string>> {
	const refused = new Set<string>();
	await page.route(BUILT_SCRIPTS, async (route) => {
		const response = await route.fetch();
		const body = await response.text();
		if (!body.includes(marker)) return route.fulfill({ response, body });
		refused.add(new URL(route.request().url()).pathname);
		return route.abort();
	});
	return refused;
}

async function openCharts(page: Page, href: string): Promise<void> {
	await page.goto(href);
}

for (const { id, href: ROUTE, label } of BAND_UNREAD.routes) {
	const expected = BY_ROUTE[id];
	if (expected === null) continue;
	test.describe(label, () => {
if (expected.browserDrawn) {
test('THE ORACLE: a chart below the draw line keeps its sentence until a mark lands', async ({
	page
}) => {
	await page.setViewportSize(SHORT);
	await openCharts(page, ROUTE);

	const far = await chartsBelowTheDrawLine(page);
	for (const one of far) {
		const figure = figureNamed(page, one.label);
		const words = figure.locator('[data-chart-pending]');
		// `hydrate` writes `waiting` on the host the moment the engine module has
		// arrived and taken the chart. That is the moment the component used to
		// decide it had drawn, so it is the moment to read what the box says.
		await expect(figure.locator('.chart-host'), `${one.label}: the engine never took the chart`).toHaveAttribute(
			'data-chart',
			'waiting',
			{ timeout: DRAWN }
		);
		await expect(figure, `${one.label}: says it is drawn while its box is empty`).toHaveAttribute(
			'data-chart-drawn',
			'no'
		);
		await expect(words, `${one.label}: the box is empty and says nothing`).toBeVisible();
		await expect(words, `${one.label}: the box says the wrong nothing`).toHaveAttribute(
			'data-chart-pending',
			'waiting'
		);
	}

	for (const one of far) {
		const figure = figureNamed(page, one.label);
		await comeTo(page, one.label);
		await expect(figure.locator('.chart-host'), `${one.label}: a reader came to it and it never drew`).toHaveAttribute(
			'data-chart',
			'live',
			{ timeout: DRAWN }
		);
		await expect(figure.locator('.chart-host svg').first()).toBeAttached();
		await expect(figure, `${one.label}: drew and still says it has not`).toHaveAttribute(
			'data-chart-drawn',
			'yes'
		);
		await expect(figure.locator('[data-chart-pending]'), `${one.label}: the sentence outlived the wait`).toHaveCount(0);
	}
});

test('THE ORACLE: a chart whose script never arrives says it did not load', async ({ page }) => {
	// The engine is two downloads - the module, and the chart library it fetches
	// when a chart comes near - and a catch on one is not a catch on the other,
	// so each gets a case. The module fails every chart at mount; the library
	// fails a chart when a reader comes to it.
	const thrown: string[] = [];
	page.on('pageerror', (error) => thrown.push(String(error)));
	await page.setViewportSize(SHORT);
	/** The failure sentence each case left in each box, by the chart's name. */
	const saidByCase: Map<string, string>[] = [];

	for (const subject of [
		{ what: 'the engine module', marker: 'data-charts-live' },
		{ what: 'the chart library', marker: '_echarts_instance_' }
	]) {
		const said = new Map<string, string>();
		const refused = await refuse(page, subject.marker);
		await openCharts(page, `${ROUTE}?refused=${encodeURIComponent(subject.marker)}`);
		await expect(page.locator('figure[data-chart-drawn]').first()).toBeAttached({ timeout: DRAWN });

		if (subject.what === 'the engine module') {
			// Every browser-drawn chart heard the same failure at mount.
			await expect
				.poll(async () => refused.size, { message: `${subject.what} was never refused`, timeout: DRAWN })
				.toBe(1);
			const undrawn = await undrawnCharts(page);
			expect(undrawn.length, 'the page drew no browser-drawn chart').toBeGreaterThan(0);
			for (const one of undrawn) {
				const figure = figureNamed(page, one.label);
				const words = figure.locator('[data-chart-pending]');
				await expect(
					words,
					`${subject.what}: ${one.label} still says it is coming after its script failed`
				).toHaveAttribute('data-chart-pending', 'failed', { timeout: DRAWN });
				await expect(figure).toHaveAttribute('data-chart-drawn', 'no');
				await expect(words).toBeVisible();
				said.set(one.label, (await words.innerText()).trim());
			}
		} else {
			// Nothing is refused until a chart comes near. A chart further down is
			// still waiting, and says so, until a reader comes to it.
			const far = await chartsBelowTheDrawLine(page);
			const one = far[0] as Undrawn;
			const figure = figureNamed(page, one.label);
			const words = figure.locator('[data-chart-pending]');
			await expect(words, `${one.label}: the box is empty and says nothing`).toHaveAttribute(
				'data-chart-pending',
				'waiting'
			);
			const waiting = (await words.innerText()).trim();
			await comeTo(page, one.label);
			await expect(figure.locator('.chart-host'), `${subject.what}: the host never said it failed`).toHaveAttribute(
				'data-chart',
				'failed',
				{ timeout: DRAWN }
			);
			await expect(figure).toHaveAttribute('data-chart-drawn', 'no');
			await expect(words, `${subject.what}: the box still says the chart is coming`).toHaveAttribute(
				'data-chart-pending',
				'failed'
			);
			await expect(words).toBeVisible();
			const failed = (await words.innerText()).trim();
			expect(failed, `${subject.what}: the box says nothing once the chart failed`).not.toBe('');
			expect(failed, `${subject.what}: "did not load" reads the same as "loading"`).not.toBe(waiting);
			said.set(one.label, failed);
			expect(refused.size, `${subject.what} was refused from more than one file`).toBe(1);
		}

		await page.unroute(BUILT_SCRIPTS);
		saidByCase.push(said);
	}

	// One fact - a download that did not arrive - is said one way, whichever of
	// the two downloads it was.
	const [module, library] = saidByCase as [Map<string, string>, Map<string, string>];
	const [label, words] = [...library.entries()][0] as [string, string];
	expect(module.get(label), `${label}: the two failures were said two ways`).toBe(words);
	expect(thrown, 'a failed download threw at the reader').toEqual([]);
});
}

if (expected.serverPictures) {
test('a chart the server drew keeps its picture, and no sentence, when the chart library never arrives', async ({
	page
}) => {
	// A failed download is a sentence for a box with nothing in it. A chart the
	// server drew already has its marks, so the failure costs it the tooltip and
	// nothing else, and a sentence laid over the picture would take away what the
	// failure did not. The Machine console is the route where every chart has a
	// server picture.
	await page.setViewportSize(DESKTOP);
	const refused = await refuse(page, '_echarts_instance_');
	await openCharts(page, `${ROUTE}?refused=library`);
	const first = page.locator('.chart-host').first();
	await expect(first, `${ROUTE} draws no chart`).toBeAttached({ timeout: DRAWN });
	await first.evaluate((node) => node.scrollIntoView({ behavior: 'instant', block: 'center' }));
	await expect(
		page.locator('[data-chart="failed"]').first(),
		'no chart a reader came to said its library did not arrive'
	).toBeAttached({ timeout: DRAWN });
	expect(refused.size, 'the chart library was refused from more than one file').toBe(1);

	const failed = page.locator('figure[data-chart-drawn]:has([data-chart="failed"])');
	const count = await failed.count();
	expect(count).toBeGreaterThan(0);
	for (let at = 0; at < count; at += 1) {
		const figure = failed.nth(at);
		await expect(figure.locator('.chart-host svg').first(), 'a failed download took the server picture').toBeAttached();
		await expect(figure, 'a chart with its server picture says it has not drawn').toHaveAttribute(
			'data-chart-drawn',
			'yes'
		);
		await expect(figure.locator('[data-chart-pending]'), 'a sentence was laid over the server picture').toHaveCount(0);
	}
	await page.unroute(BUILT_SCRIPTS);
});
}

if (expected.browserDrawn) {
test.describe('the console before its JavaScript runs', () => {
	test.use({ javaScriptEnabled: false, viewport: PHONE });

	test('a browser-drawn chart says it needs JavaScript rather than that it is loading', async ({
		page
	}) => {
		// With no script the prerendered sentence is the last word the box will
		// ever say, so a promise that the chart is on its way is false for the
		// whole visit. The promise sits in its own element, the page's
		// `<noscript>` rule hides it, and the words a reader can use stay.
		await openCharts(page, ROUTE);
		const figures = page.locator('figure[data-chart-drawn="no"]');
		const count = await figures.count();
		let read = 0;
		for (let at = 0; at < count; at += 1) {
			const figure = figures.nth(at);
			// The flow diagram is hidden below the page's stacking breakpoint.
			if (!(await figure.isVisible())) continue;
			const words = figure.locator('[data-chart-pending]');
			const promise = words.locator('[data-chart-scripted]');
			await expect(promise, 'the box has no promise to hide, so it keeps it').toHaveCount(1);
			await expect(promise, 'with no script, the box still says the chart is on its way').toBeHidden();
			const shown = (await words.innerText()).trim();
			const promised = ((await promise.textContent()) ?? '').trim();
			expect(shown, 'with no script the box says nothing at all').not.toBe('');
			expect(promised).not.toBe('');
			expect(shown, 'with no script, the box still says the chart is on its way').not.toContain(promised);
			read += 1;
		}
		expect(read, 'no browser-drawn chart is on screen without a script, so this case read nothing').toBeGreaterThan(0);
	});
});
}
	});
}
