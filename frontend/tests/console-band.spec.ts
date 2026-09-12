import { expect, test, type Page } from '@playwright/test';
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { gzipSync } from 'node:zlib';
import { PAGES_CAP_BYTES, siteCost, siteRunway } from '../src/lib/charts/glance';
import type { RunSummary } from '../src/lib/server/payload';

/**
 * The band's remaining-room figure, and the unit it is allowed to be in.
 *
 * It used to be published days, and the number of articles it divided a day by
 * was `run.safety_ceiling_per_run` - which bounds one RUN, not one day. The
 * schedule fires up to five runs a day, so a day was priced at 160 articles
 * while the ten committed published days ran 4 to 731, median 334 (measured
 * 2026-08-31). The band printed 1,950 published days where the measured median
 * rate gives 934: too long by 2.09 times.
 *
 * The fix removes the assumption instead of correcting it. Headroom over the
 * per-article cost is a count of articles and needs no daily rate at all, so
 * there is nothing left in it for a run rate to be wrong about. That is the
 * claim this file holds: the printed figure equals `(cap - bytes) / cost`, and
 * no number of runs a day can move it.
 *
 * `console-site-size.spec.ts` owns the per-article cost the runway divides by.
 */

/** The tree the site was built from. The suite builds from the canaries. */
const CANARY = resolve(process.cwd(), '..', 'backend', 'var', 'canary', 'digest');

/** What the alarm is set to matters to `site-weight`, never to this figure. */
const ALARM = 800 * 1024 * 1024;

interface Day {
	date: string;
	siteBytes: number;
	items: number;
}

function dirs(at: string): string[] {
	return readdirSync(at, { withFileTypes: true })
		.filter((entry) => entry.isDirectory())
		.map((entry) => entry.name)
		.sort();
}

/** Every published day the build read, oldest first.
 *
 * Read straight off the manifests rather than through `payload.ts`, so the
 * expected answer below is arrived at by a second path and not by running the
 * page's own arithmetic twice.
 */
function publishedDays(root: string): Day[] {
	const days: Day[] = [];
	for (const year of dirs(root)) {
		for (const month of dirs(join(root, year))) {
			for (const day of dirs(join(root, year, month))) {
				const at = join(root, year, month, day);
				if (!existsSync(join(at, 'run.json')) || !existsSync(join(at, 'digest.json'))) continue;
				const runs = (JSON.parse(readFileSync(join(at, 'run.json'), 'utf8')).runs ?? []) as {
					site_bytes?: number;
				}[];
				const items = (JSON.parse(readFileSync(join(at, 'digest.json'), 'utf8')).items ??
					[]) as unknown[];
				days.push({
					date: `${year}-${month}-${day}`,
					// The console reads the last run of the day, because the site is one
					// thing measured once per run.
					siteBytes: Number(runs.at(-1)?.site_bytes ?? 0) || 0,
					items: items.length
				});
			}
		}
	}
	return days.sort((a, b) => a.date.localeCompare(b.date));
}

function medianOf(values: number[]): number | null {
	if (values.length === 0) return null;
	const sorted = [...values].sort((a, b) => a - b);
	const middle = Math.floor(sorted.length / 2);
	return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}

/** `(cap - bytes) / bytesPerItem`, stated here rather than imported. */
function remainingArticles(days: Day[]): number | null {
	const rates: number[] = [];
	for (let i = 1; i < days.length; i += 1) {
		if (days[i].items <= 0) continue;
		rates.push((days[i].siteBytes - days[i - 1].siteBytes) / days[i].items);
	}
	const cost = medianOf(rates);
	if (cost === null || cost <= 0) return null;
	return (PAGES_CAP_BYTES - days[days.length - 1].siteBytes) / cost;
}

/** Three significant figures, which is the precision the band prints at.
 *
 * The rate under the answer is a median whose spread is near a fifth of itself,
 * so the trailing digits of a six-figure count are noise (Rule #10).
 */
function threeFigures(value: number): number {
	if (value <= 0) return 0;
	const scale = 10 ** Math.max(0, Math.floor(Math.log10(value)) - 2);
	return Math.round(value / scale) * scale;
}

function summary(date: string, siteBytes: number, runs: number): RunSummary {
	return { date, runs, planned: 0, failed: 0, siteBytes, siteFiles: 1, models: [], records: [] };
}

async function hydrated(page: Page) {
	await expect(page.locator('[data-window-control]')).toHaveAttribute('data-window-days', /\d+/);
}

test('THE ORACLE: the band prints the articles the headroom buys', async ({ page }) => {
	const days = publishedDays(CANARY);
	expect(days.length, 'the build read fewer than two days, so nothing has a rate').toBeGreaterThan(
		1
	);
	const expected = remainingArticles(days);
	expect(expected, 'no day in the build grew the tree over an article it published').not.toBeNull();

	await page.goto('/console/');
	await hydrated(page);

	const sentence = page.locator('[data-band-size]');
	await expect(sentence).toHaveCount(1);
	const text = (await sentence.innerText()).trim();

	const printed = Number(
		/room for about ([\d,]+) more articles/.exec(text)?.[1]?.replace(/,/g, '')
	);
	expect(Number.isFinite(printed), `the band printed no article headroom: ${text}`).toBe(true);
	expect(printed, 'the band and the manifests disagree about the room left').toBe(
		threeFigures(expected as number)
	);

	// The defect, stated as the thing that may not come back. A daily article
	// rate is a quantity nothing here measures, and the one number that was
	// standing in for it - `run.safety_ceiling_per_run` - bounds a run.
	expect(text, 'the band is claiming a daily article rate again').not.toMatch(/articles a day/);
	expect(text, 'the band is printing a date it cannot derive').not.toMatch(/fills it in/);
});

test('no rate of runs a day can move the answer', () => {
	// One site, described twice: four days at one run a day, and the same four
	// days at three. `run.safety_ceiling_per_run` is 80 and bounds a RUN, so a
	// formula built on it prices the second day at 240 articles and the first at
	// 80 - and its answer moves by three. This one may not move at all, because
	// the site did not change.
	const dates = ['2026-08-01', '2026-08-02', '2026-08-03', '2026-08-04'];
	const bytes = [1_000_000, 1_300_000, 1_600_000, 1_900_000];
	const used = bytes[bytes.length - 1];
	const items = new Map(dates.map((date) => [date, 100]));

	const once = dates.map((date, i) => summary(date, bytes[i], 1));
	const thrice = dates.map((date, i) => summary(date, bytes[i], 3));

	const a = siteRunway(used, siteCost(once, items).median, ALARM);
	const b = siteRunway(used, siteCost(thrice, items).median, ALARM);
	expect(a).not.toBeNull();
	expect(a?.toCap, 'the runway moved when only the run count did').toBe(b?.toCap);

	// 3,000 bytes an article, by construction, so the expected answer is a
	// division a reader can check.
	expect(Math.round(a?.toCap ?? 0)).toBe(Math.round((PAGES_CAP_BYTES - used) / 3000));

	// And what a per-day answer would have done with the same two fixtures,
	// written out so the difference is on the page rather than asserted in the
	// abstract.
	const CEILING = 80;
	const daysAtCeiling = (runsADay: number) =>
		(PAGES_CAP_BYTES - used) / (3000 * CEILING * runsADay);
	expect(daysAtCeiling(3)).toBeCloseTo(daysAtCeiling(1) / 3, 6);
});

/**
 * The band's height, and where it leaves the first chart.
 *
 * Measured on this tree at bf37eeef, 2026-09-01, node 24.12.0, real build: the
 * band was 340px at 1440x1000 and 586px at 390x844 - 69 percent of a phone
 * viewport - with the window control inside it and the navigation strip 577px
 * down the page, below both. The first drawn chart on `/console/` was at 890px
 * and 1,372px, and the band was 99 words.
 *
 * After: the band is 113px and 282px, 50 words, with the strip above it and the
 * control below it, and the first chart is at 726px and 1,163px. The band is
 * 33 percent of a phone viewport rather than 69.
 *
 * **The chart lines below are 760 and 1,200, and the plan asked for 640 and
 * 1,000.** That gap is measured and it is not the band's to close. At 1440 the
 * 726px above the first chart is 113 site header, 24 page padding, 33 page
 * title, 79 strip, 113 band, 91 control, 21 cross-route sentence, 28 section
 * heading, 97 of a measure card's own label and value, and 127 of margins - so
 * the three things this row owns are 283px of it and the other 443px belong to
 * five other surfaces. Cutting into those is a different row's decision.
 */
const VIEWPORTS = [
	{ name: 'desktop', width: 1440, height: 1000, band: 130, chart: 760 },
	{ name: 'phone', width: 390, height: 844, band: 320, chart: 1200 }
] as const;

/** The top and height of one element, in page coordinates. */
async function boxOf(page: Page, selector: string) {
	return page.locator(selector).evaluate((node) => {
		const box = node.getBoundingClientRect();
		return { top: Math.round(box.top + window.scrollY), height: Math.round(box.height) };
	});
}

for (const view of VIEWPORTS) {
	test(`THE ORACLE: the band is three facts and half the height at ${view.width}`, async ({
		page
	}) => {
		await page.setViewportSize({ width: view.width, height: view.height });
		await page.goto('/console/');
		await hydrated(page);

		const band = await boxOf(page, '[data-console-band]');
		expect(
			band.height,
			`the band is ${band.height}px at ${view.width}, over its ${view.band}px line`
		).toBeLessThanOrEqual(view.band);

		// The control is out of the band, not merely shorter inside it.
		await expect(page.locator('[data-console-band] [data-window-control]')).toHaveCount(0);

		const chart = await page.evaluate(() => {
			const svg = [...document.querySelectorAll('[data-surface="operator"] svg')].find(
				(node) => node.getBoundingClientRect().width > 0
			);
			return svg === undefined
				? null
				: Math.round(svg.getBoundingClientRect().top + window.scrollY);
		});
		expect(chart, 'no chart is drawn on the route at all').not.toBeNull();
		expect(
			chart as number,
			`the first chart is at ${chart}px at ${view.width}, past its ${view.chart}px line`
		).toBeLessThanOrEqual(view.chart);
	});
}

test('THE ORACLE: chrome reads top to bottom - title, strip, band, control', async ({ page }) => {
	await page.goto('/console/');

	// Read as an ordering of tops rather than of DOM nodes, because that is what
	// a reader gets. Until 2026-08-31 the strip sat 337px BELOW the band on a
	// phone, so the band's worst fact linked into a strip the reader had already
	// scrolled past, and the control sat inside a panel it does not govern.
	const order = await page.evaluate(() => {
		const at = (selector: string) => {
			const node = document.querySelector(selector);
			return node === null ? null : node.getBoundingClientRect().top + window.scrollY;
		};
		return {
			header: at('body > header, header'),
			title: at('[data-surface="operator"] h1'),
			nav: at('[data-console-nav]'),
			band: at('[data-console-band]'),
			control: at('[data-window-control]'),
			content: at('[data-surface="operator"] .console-h2')
		};
	});
	for (const [name, top] of Object.entries(order)) {
		expect(top, `${name} is not on the page`).not.toBeNull();
	}
	const tops = [
		order.header,
		order.title,
		order.nav,
		order.band,
		order.control,
		order.content
	] as number[];
	expect(
		tops,
		`header, title, strip, band, control, content - measured ${tops.join(', ')}`
	).toEqual([...tops].sort((a, b) => a - b));
	expect(new Set(tops).size, 'two of the six sit at the same height').toBe(tops.length);
});

test('the band says what the worst state costs, and the strip keeps the short form', async ({
	page
}) => {
	await page.goto('/console/');

	const worst = page.locator('[data-band-worst]');
	const route = await worst.getAttribute('data-band-worst-route');
	if (route === null) {
		// The clear state is a sentence, and it has no strip fragment to differ
		// from. `console-nav.spec.ts` holds that shape.
		await expect(worst).toHaveAttribute('data-band-worst', 'clear');
		return;
	}

	const strip = (
		await page.locator(`[data-console-tab-worst="${route}"]`).innerText()
	).trim();
	const band = (await worst.innerText()).replace(/\s+/g, ' ').trim();
	// The two said the same words until 2026-08-31, 337px apart on a phone. The
	// band has room for a consequence and the strip has room for two words, so
	// one string for both was always going to be the strip's.
	expect(band, 'the band prints the strip fragment and nothing more').not.toBe(strip);
	expect(band, 'the band names no consequence').toContain(', so ');
	expect(band.length, 'the band is not saying more than the strip').toBeGreaterThan(strip.length);
});

test('the newest day draws one square a run, on the same ramp as the run strip', async ({
	page
}) => {
	await page.goto('/console/');

	// The sentence says the day ran N runs and published M of P. It cannot say
	// whether one run ate every failure or all of them limped, and that is the
	// question the row answers. Hand-written markup, so it is on the page with
	// no script at all.
	const squares = await page
		.locator('[data-band-fact="verdict"] [data-band-run]')
		.evaluateAll((nodes) =>
			nodes.map((node) => ({
				health: node.getAttribute('data-band-run') ?? '',
				label: node.getAttribute('aria-label') ?? '',
				fill: getComputedStyle(node).backgroundColor
			}))
		);
	expect(squares.length, 'the newest day drew no run row').toBeGreaterThan(0);
	expect(squares.length, 'the row is a chart, not a row').toBeLessThanOrEqual(12);

	const ramp = await page.evaluate(() => {
		const root = getComputedStyle(document.documentElement);
		const probe = (value: string) => {
			const span = document.createElement('span');
			span.style.color = value;
			document.body.appendChild(span);
			const read = getComputedStyle(span).color;
			span.remove();
			return read;
		};
		return ['--fill-high', '--fill-medium', '--fill-low'].map((token) =>
			probe(root.getPropertyValue(token).trim())
		);
	});
	for (const square of squares) {
		// Colour is one signal and never the only one.
		expect(square.label.length, 'a square carries no words').toBeGreaterThan(4);
		expect(ramp, `a square is painted ${square.fill}, off the run ramp`).toContain(square.fill);
	}

	// And the count agrees with the sentence beside it, so the row and the words
	// cannot report two different days.
	const said = await page.locator('[data-band-verdict]').innerText();
	const runs = Number(/ran (\d+) runs?/.exec(said)?.[1] ?? 0);
	const overflow = page.locator('[data-band-runs-more]');
	const more =
		(await overflow.count()) === 0
			? 0
			: Number((await overflow.getAttribute('data-band-runs-more')) ?? 0);
	expect(squares.length + more, 'the row and the sentence count different runs').toBe(runs);
});

test('THE ORACLE: the band is the same three facts on every route, and no window moves it', async ({
	page
}) => {
	const bandText = async (path: string) => {
		await page.goto(path);
		await hydrated(page);
		return (await page.locator('[data-console-band]').innerText()).replace(/\s+/g, ' ').trim();
	};

	// One band, derived once in the shared layout and drawn above all five route
	// panels. Five routes deriving their own would eventually disagree about which
	// one of them is worst, which is the whole reason it is derived once (row 24).
	const pipelines = await bandText('/console/');
	expect(pipelines.length, 'the band drew nothing on /console/').toBeGreaterThan(0);
	for (const path of [
		'/console/model/',
		'/console/machine/',
		'/console/judgement/',
		'/console/voices/'
	]) {
		expect(await bandText(path), `the band differs on ${path}`).toBe(pipelines);
	}

	// The band is deliberately not windowed: a route's control governs the panels
	// below it, never the standing band above it. Moving the control to another
	// preset may not move the three facts (row 24 decision 2). This is also the
	// guardrail on the read change - a band sourced from the newest day cannot have
	// quietly become a windowed read.
	await page.goto('/console/model/');
	await hydrated(page);
	const before = (await page.locator('[data-console-band]').innerText()).replace(/\s+/g, ' ').trim();
	const current = await page.locator('[data-window-control]').getAttribute('data-window-days');
	const presets = await page
		.locator('[data-window-preset]')
		.evaluateAll((nodes) => nodes.map((node) => node.getAttribute('data-window-preset') ?? ''));
	const other = presets.find((preset) => preset !== '' && preset !== current);
	expect(other, 'the control offers only one preset, so nothing here can move').toBeTruthy();
	await page.locator(`[data-window-preset="${other}"]`).click();
	await expect(page.locator('[data-window-control]')).toHaveAttribute(
		'data-window-days',
		other as string
	);
	const after = (await page.locator('[data-console-band]').innerText()).replace(/\s+/g, ' ').trim();
	expect(after, 'moving a route window control moved the standing band').toBe(before);
});

/** The payload the pipeline publishes, which is the one a reader is served. */
const BAND_PAYLOAD = resolve(process.cwd(), 'public', 'console', 'band.json');

/**
 * The guardrail, read from the file the bundle gate reads.
 *
 * It was `8 * 1024` here until 2026-09-10, while `bundle-gate.mjs` enforced
 * `page_weight.payload_ceilings_bytes['console/band.json']` at 2,000 - two live
 * numbers for one payload, fourfold apart, and this spec's own century model
 * produced 3,247 bytes, which passed the number asserted here and failed the
 * one the gate applies. Nothing had gone red yet, which is the whole hazard.
 * The knob lives in `config/idhazh.json` and nowhere else (Rule #6), so this
 * reads it rather than restating it.
 */
const REPO = resolve(process.cwd(), '..');
const CONFIG = JSON.parse(readFileSync(join(REPO, 'config', 'idhazh.json'), 'utf8')) as {
	observability: Record<string, number | null>;
	page_weight: { payload_ceilings_bytes: Record<string, number> };
};
const BAND_GUARDRAIL_BYTES = CONFIG.page_weight.payload_ceilings_bytes['console/band.json'];

/**
 * The longest months list retention can leave, which is what bounds this payload.
 *
 * `months` is `fetchable_months`, the union of the month shards across the seven
 * published series, and `idhazh prune-state` deletes a shard past its own
 * `observability.public_*_keep_months`. All of them are 14 today, so the list
 * holds fourteen entries however long the project runs - the bound is read here
 * rather than typed, so a retention change moves this test with it.
 */
const KEPT_MONTHS = Math.max(
	...Object.entries(CONFIG.observability)
		.filter(([key, value]) => key.startsWith('public_') && key.endsWith('_keep_months') && value !== null)
		.map(([, value]) => value as number)
);

test('THE ORACLE: the band is inside its guardrail on the wire', () => {
	const raw = readFileSync(BAND_PAYLOAD);
	const wire = gzipSync(raw, { level: 5 }).length;

	// Measured 2026-09-10 on the committed payload, node 24.12.0: 1,799 bytes raw
	// and 777 gzipped, which is 38.9 percent of the guardrail. The guardrail is
	// not about today's payload - it is what stops the band becoming the thing an
	// operator waits for. A band that has to be downloaded before it can be read
	// is a verdict that arrives after the page it was meant to explain.
	expect(
		wire,
		`the band is ${wire} gzipped bytes, over its ${BAND_GUARDRAIL_BYTES}-byte guardrail`
	).toBeLessThanOrEqual(BAND_GUARDRAIL_BYTES);
});

test('THE ORACLE: the months list is the only part of the band that grows, and retention bounds it', () => {
	const payload = JSON.parse(readFileSync(BAND_PAYLOAD, 'utf8')) as { months: string[] };
	expect(Array.isArray(payload.months), 'the band carries no months list').toBe(true);

	// Everything else on the payload is a fixed set of sentences and counts about
	// one day, so the only term that moves with the archive is one `YYYY-MM`
	// string a month - and even that stops, because the shard behind it is
	// deleted at the retention bound. Priced here rather than asserted about
	// today: measured 2026-09-10, node 24.12.0, the list at its 14-month bound
	// takes the payload to 758 gzipped bytes against 726 with no months at all,
	// so the whole growable part of this payload is 32 bytes. The committed file
	// reads 777 rather than 726 because it is written pretty-printed and this
	// model re-serialises it compact; at the bound the served payload is about
	// 809, which is 40.5 percent of the guardrail.
	const withMonths = (count: number) => {
		const months: string[] = [];
		for (let i = 0; i < count; i += 1) {
			months.push(`${2026 + Math.floor(i / 12)}-${String((i % 12) + 1).padStart(2, '0')}`);
		}
		return gzipSync(Buffer.from(JSON.stringify({ ...payload, months })), { level: 5 }).length;
	};

	expect(
		payload.months.length,
		`the band lists ${payload.months.length} months where retention keeps ${KEPT_MONTHS}`
	).toBeLessThanOrEqual(KEPT_MONTHS);

	const bounded = withMonths(KEPT_MONTHS);
	expect(
		bounded,
		`a full ${KEPT_MONTHS} months puts the band at ${bounded} gzipped bytes, over its guardrail`
	).toBeLessThanOrEqual(BAND_GUARDRAIL_BYTES);

	// And the list is a bounded term rather than a growing one, so nothing here
	// needs a window of its own: what it can ever add is small against the room
	// the guardrail has spare.
	expect(
		bounded - withMonths(0),
		'the months list costs more than the guardrail has room for'
	).toBeLessThan(BAND_GUARDRAIL_BYTES - withMonths(0));
});

/** A request for code, not for an answer. The band is measured against the
 * payloads, because a route's own chunk has to arrive before any load runs. */
const CODE = /\/_app\/|\.(?:js|mjs|css|map|woff2?|ico|png|jpe?g|svg|webmanifest)$/;

/** SvelteKit's own file for the route, holding what the three `+page.server.ts`
 * loads return. The router fetches it and AWAITS it before it runs a single
 * universal load, so while the console keeps a server load this one file is
 * ahead of the band and there is nothing the band can do about it. */
const ROUTE_DATA = '/console/__data.json';

test('THE ORACLE: the band is the first payload the console asks for', async ({ page }) => {
	const issued: string[] = [];
	page.on('request', (request) => issued.push(new URL(request.url()).pathname));

	// A cold document already carries the band. The routes are prerendered and
	// the layout load is universal, so SvelteKit resolves its fetch against the
	// staged payload at build time and the verdict is markup - nothing is asked
	// for at all. The request exists on a move INTO the console from outside,
	// which is the entry an operator makes from a tab he already had open, and it
	// is the entry this measures.
	await page.goto('/');
	await expect(page.locator('body')).toBeVisible();
	issued.length = 0;

	await page.evaluate(() => {
		const link = document.createElement('a');
		link.href = '/console/';
		link.id = 'oracle-console-entry';
		link.textContent = 'console';
		document.body.append(link);
	});
	await page.click('#oracle-console-entry');
	await hydrated(page);
	// Wait for the route to have asked for its panel data as well, so this cannot
	// pass by the band being the only payload in the list.
	await page.waitForFunction(
		() =>
			Number(
				document.querySelector('[data-telemetry-rows]')?.getAttribute('data-telemetry-rows') ?? 0
			) > 0,
		undefined,
		{ timeout: 20_000 }
	);

	const payloads = issued.filter((path) => !CODE.test(path));
	const order = payloads.join(', ');
	expect(payloads.length, `the console asked for ${payloads.length} payloads: ${order}`).toBeGreaterThan(1);

	const bandAt = payloads.indexOf('/console/band.json');
	expect(bandAt, `the console never asked for the band: ${order}`).toBeGreaterThanOrEqual(0);

	// Nothing of ours may be ahead of it. Measured 2026-09-09 on this tree, node
	// 24, canary build: the order is `/console/__data.json`, `/console/band.json`,
	// `/telemetry/2026-07.csv`, `/telemetry/2026-08.csv`, so the band is second
	// and the one file ahead of it is SvelteKit's, not ours. That file is 31,354
	// bytes (6,520 gzipped) against the band's 1,904 (779), and the router awaits
	// it before any universal load starts - so the verdict is a second round trip
	// today rather than the first. It becomes index 0 when the console's three
	// server loads go and the file with them; both lines below still hold then.
	const ahead = payloads.slice(0, bandAt);
	expect(
		ahead.filter((path) => path !== ROUTE_DATA),
		`something of ours got in front of the band: ${order}`
	).toEqual([]);
	expect(ahead.length, `${ahead.length} requests are ahead of the band: ${order}`).toBeLessThanOrEqual(1);

	// And it is ahead of every panel the page draws, which is the thing decision 2
	// bought: the verdict does not wait for the data behind it.
	const panels = payloads.filter((path) => path.startsWith('/telemetry/'));
	expect(panels.length, `the route drew no panel data at all: ${order}`).toBeGreaterThan(0);
	for (const panel of panels) {
		expect(payloads.indexOf(panel), `${panel} was asked for before the band: ${order}`).toBeGreaterThan(
			bandAt
		);
	}
});
