/** Voices narrows source counts while named snapshots keep their own recorded span. */
import { expect, test, type Page } from './support/browser';

import { shortDate } from '../src/lib/format';

import { hydrated, setWindow, windowed, routeHref } from './support/console-window/controls';
import { windowDates } from './support/console-window/readout';
import { DRAWN_THROUGH as JUDGED_THROUGH } from './support/console-window/readout';

import { clientCode, drawClient } from './support/console-window/client-render';

async function cutFacts(page: Page) {
	// Named, not positional. The cost sentence sits above this one now, and a
	// `p` picked by order silently reads whichever paragraph moved into first
	// place rather than failing.
	const intro = (
		await page.locator('[data-source-cuts-intro]').innerText()
	).replace(/\s+/g, ' ');
	const more = (await page.locator('[data-source-cuts-more]').innerText()).replace(/\s+/g, ' ');
	const cost = (await page.locator('[data-source-cuts-cost]').innerText()).replace(/\s+/g, ' ');
	return {
		// Thousands are grouped in the sentence, so the comma is stripped rather
		// than the digits before it being read as the whole count.
		articles: Number(/ held ([\d,]+) articles?/.exec(intro)?.[1]?.replace(/,/g, '')),
		tailSources: Number(/(\d+) more sources/.exec(more)?.[1]),
		cut: Number(/(\d+) articles were cut short/.exec(cost)?.[1])
	};
}

test('the source table follows the window, and drops what falls outside it', async ({ page }) => {
	await page.goto(routeHref('voices'));
	await hydrated(page);

	// The canary writes one cut ten days back, under a source with a single cut.
	// Seven days cannot reach it and every wider preset can, so the section's own
	// counts move with the control rather than only its heading. They are read
	// rather than typed: a number written here goes stale the day the fixture
	// grows a row, and it goes stale silently.
	await setWindow(page, 7);
	const narrow = await cutFacts(page);
	await setWindow(page, 90);
	const wide = await cutFacts(page);

	expect(narrow.articles, 'the section prints no denominator').toBeGreaterThan(0);
	expect(wide.articles, 'widening reached no further article').toBeGreaterThan(narrow.articles);
	expect(wide.cut, 'widening reached no further cut').toBeGreaterThan(narrow.cut);
	// The older cut belongs to a source with one cut, so it lands in the tail
	// rather than the printed ten. The tail is where it has to show up.
	expect(wide.tailSources, 'the tail did not gain the older source').toBeGreaterThan(
		narrow.tailSources
	);

	// And the denominator is on the page, because at seven days it runs as low
	// as six articles and a share over six is not a rate. `\s+` rather than a
	// space: the sentence wraps in the template, and a regex reads the raw text.
	await expect(page.locator('[data-windowed="source-cuts"]')).toContainText(
		/held\s+[\d,]+\s+articles/
	);
});
test('feed and ranking snapshots state that they do not follow the window', async ({ page }) => {
	await page.goto(routeHref('voices'));
	await hydrated(page);

	// A windowed quarantine count would disagree with the resting the pipeline
	// actually performed, so the feed count reads every run and states it. The
	// strip of days beside it does follow the window, and is a separate node -
	// which is why this locator is the paragraph and not the section.
	const feeds = page.locator('[data-window-exempt="feeds"]');
	await expect(feeds).toContainText('does not follow the window');
	await expect(feeds).not.toHaveAttribute('data-window-days', /.*/);

	// And the ranking weight, which the run reduced over its own span when it
	// ran. Redrawing it over seven days would print a number no run applied.
	const weight = page.locator('[data-window-exempt="reliability"]');
	await expect(weight).toContainText('does not follow the window control');
	await expect(weight).not.toHaveAttribute('data-window-days', /.*/);
});
test.describe("remaining one-day words and keys on generated records", () => {

let browserCode: string;
test.beforeAll(async () => { browserCode = await clientCode([["Voices","./src/routes/console/voices/+page.svelte"]]); });
async function drawRecord(page: Page, name: string, props: Record<string, unknown>) {
  await drawClient(page, browserCode, name, props);
}

function voiceData(preset: number, recordedDates: string[]) {
	const feedDates = windowDates(preset);
	const squares = recordedDates.map((date) => ({ date, state: 'nothing', label: `${shortDate(date)}: it decided nothing that day.` }));
	return {
		ui: { site_title: 'Generated records' },
		console: { default_window_days: preset, window_presets: [1, 7], today_anchor: 'right', min_attempts_for_rate: 5, source_rows: 10 },
		windowDay: JUDGED_THROUGH,
		chart: CHART,
		carries: { voices: '' },
		recordNotes: {},
		standing: null,
		sourceHealth: null,
		sourceCutsByWindow: [{ days: preset, articles: 0, measured: false, cost: null }],
		feedDates,
		feedRecord: { runs: 0 },
		quarantineAfter: 5,
		feedsHidden: 0,
		feeds: ['feed-a', 'feed-b'].map((feedId) => ({
			feedId, resting: false, streak: 0, failures: 0,
			marks: { empty: true, track: 1, band: 'unknown' },
			days: feedDates.map((date) => ({ date, outcome: 'answered', label: `${shortDate(date)}: answered.` }))
		})),
		retiring: {
			dates: recordedDates, dwellDays: 14, autoRetire: false,
			alarmPoint: 0.5, clear: 0, hidden: 0,
			rows: [{
				sourceId: 'source-a', title: 'source-a', squares, share: 0.5,
				daysUnder: 0, daysLeft: null, retiresOn: null, retired: false,
				marks: { empty: true, track: 1, band: 'unknown' }, readout: 'Nothing was decided.'
			}],
			completeDates: recordedDates.length, minCompleteDays: 14, minDecisions: 10,
			unjudgedHidden: 0,
			unjudged: ['source-b'].map((sourceId) => ({
				sourceId, title: sourceId, squares, readout: 'Nothing was decided.'
			}))
		}
	};
}

for (const preset of [1, 7]) {
	test(`THE ORACLE: feed words at ${preset} day(s) preserve real feed navigation`, async ({ page }) => {
		await drawRecord(page, 'Voices', { data: voiceData(preset, windowDates(7)) });
		const group = page.locator('[data-windowed="feed-outcomes"]');
		const strip = page.locator('[data-readout="feed-outcomes"] [data-readout-subject]');
		await expect(group).toHaveAttribute('aria-label', preset === 1
			? "Every feed's reading for this one day, one square per feed. Arrow keys move between feeds. Escape returns to the first feed."
			: "Every feed's days, one square a day. Arrow keys read a square, Escape returns to the first feed's newest day.");
		await expect(strip).toHaveText(preset === 1 ? 'feed-a, 15 Jun 2030, this one day' : 'feed-a, 15 Jun 2030, its newest day');
		await expect(page.locator('[data-readout-hint="feed-outcomes"]')).toHaveText(preset === 1
			? 'Point at a square to read it. Arrow keys move between feeds. Escape returns to the first feed.'
			: "Point at a square to read it. Left and Right step through a feed's days, Up and Down move between feeds, Escape returns to rest.");
		await group.focus();
		await group.press('ArrowDown');
		await group.press('ArrowDown');
		await expect(strip).toHaveText(preset === 1 ? 'feed-b, 15 Jun 2030' : 'feed-b, 9 Jun 2030');
		await group.press('Escape');
		await expect(strip).toContainText(preset === 1 ? ', this one day' : ', its newest day');
		if (preset === 1) {
			await group.press('ArrowRight');
			await group.press('ArrowRight');
			await expect(strip).toHaveText('feed-b, 15 Jun 2030');
		}
	});

	for (const recordDays of [1, 7]) {
		test(`THE ORACLE: source words use their own ${recordDays}-day record at the ${preset}-day window`, async ({ page }) => {
			await drawRecord(page, 'Voices', { data: voiceData(preset, windowDates(recordDays)) });
			const group = page.locator('[data-retiring="table"]');
			const strip = page.locator('[data-readout="source-yield"] [data-readout-subject]');
			await expect(group).toHaveAttribute('aria-label', recordDays === 1
				? "Every source's reading for the one recorded day, one square per source. Arrow keys move between sources. Escape returns to the first source."
				: "Every source's days, one square a day. Arrow keys read a square, Escape returns to the first source's newest day.");
			await expect(strip).toHaveText(recordDays === 1 ? 'source-a, 15 Jun 2030, its one recorded day' : 'source-a, 15 Jun 2030, its newest day');
			await expect(page.locator('[data-readout-hint="source-yield"]')).toHaveText(recordDays === 1
				? 'Point at a square to read it. Arrow keys move between sources. Escape returns to the first source.'
				: "Point at a square to read it. Left and Right step through a source's days, Up and Down move between sources, Escape returns to rest.");
			await group.focus();
			await group.press('ArrowDown');
			await group.press('ArrowDown');
			await expect(strip).toHaveText(recordDays === 1 ? 'source-b, 15 Jun 2030' : 'source-b, 9 Jun 2030');
			await group.press('Escape');
			await expect(strip).toContainText(recordDays === 1 ? ', its one recorded day' : ', its newest day');
		});
	}
}

test('THE ORACLE: an unjudged-only source rests on its newest recorded day before interaction', async ({ page }) => {
	const data = voiceData(7, windowDates(7));
	data.retiring.rows = [];
	data.retiring.unjudged = [{ ...data.retiring.unjudged[0], sourceId: 'source-a', title: 'source-a' }];
	await drawRecord(page, 'Voices', { data });
	const strip = page.locator('[data-readout="source-yield"] [data-readout-subject]');
	await expect(strip).toHaveText('source-a, 15 Jun 2030, its newest day');
	await page.locator('[data-retiring="table"]').focus();
	await page.locator('[data-retiring="table"]').press('ArrowLeft');
	await expect(strip).toHaveText('source-a, 9 Jun 2030');
	await page.locator('[data-retiring="table"]').press('Escape');
	await expect(strip).toHaveText('source-a, 15 Jun 2030, its newest day');
});

for (const preset of [1, 7]) {
	for (const recordDays of [1, 7]) {
		test(`unjudged sources keep pointer and keyboard selection for a ${recordDays}-day record at the ${preset}-day window`, async ({ page }) => {
			const data = voiceData(preset, windowDates(recordDays));
			data.retiring.rows = [];
			data.retiring.unjudged = [
				{ ...data.retiring.unjudged[0], sourceId: 'source-a', title: 'source-a' },
				data.retiring.unjudged[0]
			];
			await drawRecord(page, 'Voices', { data });
			const group = page.locator('[data-retiring="table"]');
			const strip = page.locator('[data-readout="source-yield"] [data-readout-subject]');
			const resting = recordDays === 1
				? 'source-a, 15 Jun 2030, its one recorded day'
				: 'source-a, 15 Jun 2030, its newest day';
			await expect(strip).toHaveText(resting);
			await group.focus();
			await group.press('ArrowDown');
			await group.press('ArrowDown');
			await expect(strip).toHaveText(recordDays === 1 ? 'source-b, 15 Jun 2030' : 'source-b, 9 Jun 2030');
			await group.press('Escape');
			await expect(strip).toHaveText(resting);
			const square = page.locator('[data-retiring-unjudged-row="source-b"] [data-readout-at]').last();
			await square.hover();
			await expect(strip).toHaveText('source-b, 15 Jun 2030');
			await square.click();
			await expect(strip).toHaveText('source-b, 15 Jun 2030');
			await page.mouse.move(0, 0);
			await expect(strip).toHaveText(resting);
			await group.focus();
			await group.press('Escape');
			await expect(strip).toHaveText(resting);
		});
	}
}

test('the first judged source keeps precedence over a newer unjudged source', async ({ page }) => {
	const data = voiceData(7, windowDates(7));
	data.retiring.rows[0].squares = data.retiring.rows[0].squares.slice(0, 6);
	await drawRecord(page, 'Voices', { data });
	const group = page.locator('[data-retiring="table"]');
	const strip = page.locator('[data-readout="source-yield"] [data-readout-subject]');
	await expect(strip).toHaveText('source-a, 14 Jun 2030, its newest day');
	await page.locator('[data-retiring-unjudged-row="source-b"] [data-readout-at]').last().hover();
	await expect(strip).toHaveText('source-b, 15 Jun 2030');
	await group.focus();
	await group.press('Escape');
	await expect(strip).toHaveText('source-a, 14 Jun 2030, its newest day');
});
for (const state of ['absent', 'empty', 'no-squares'] as const) {
	test(`a source record offers no square readout when ${state}`, async ({ page }) => {
		const generated = voiceData(7, []);
		if (state === 'empty') {
			generated.retiring.rows = [];
			generated.retiring.unjudged = [];
		}
		const data: Omit<ReturnType<typeof voiceData>, 'retiring'> & {
			retiring: ReturnType<typeof voiceData>['retiring'] | null;
		} = { ...generated, retiring: state === 'absent' ? null : generated.retiring };
		await drawRecord(page, 'Voices', { data });
		await expect(page.locator('[data-readout="source-yield"]')).toHaveCount(0);
		if (state === 'absent') await expect(page.locator('[data-retiring="table"]')).toHaveCount(0);
		else {
			await expect(page.locator('[data-retiring="table"]')).toHaveAttribute('data-readout-none', 'no source has a day on record, so there is no square to read; agreed with Susan');
			await expect(page.locator(state === 'empty' ? '[data-retiring-empty]' : '[data-retiring-no-strip]')).toBeVisible();
		}
	});
}
});
const CHART = { width_px: 760, height_px: 220, tick_density: 6, readout_max_share: 1 };
