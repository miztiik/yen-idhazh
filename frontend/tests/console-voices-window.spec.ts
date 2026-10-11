/** Voices narrows source counts while named snapshots keep their own recorded span. */
import { expect, test, type Page } from './support/door-page';

import { shortDate } from '../src/lib/format';

import { hydrated, setWindow, windowed, routeHref } from './support/console-window/controls';
import { windowDates } from './support/console-window/readout';

import { clientCode } from './support/console-window/client-render';
import { retirementDrawing } from '../src/lib/console/voices/retiring';
import type { Retiring } from '../src/lib/server/source-retiring';
import { consoleConfig } from '../src/lib/server/config';
import { shareMarks } from '../src/lib/charts/targetbar';

async function cutFacts(page: Page) {
	await expect(page.locator('[data-console-panels="voices"]')).not.toHaveAttribute('data-route-state', 'loading');
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
test('only the three unpublished source snapshots keep their recorded span', async ({ page }) => {
	await page.goto(routeHref('voices'));
	await hydrated(page);

	// These are the producer's unpublished decisions, not a new judgement over
	// the native-query window.
	for (const [id, sentence] of [
		['source-health', 'not the window control'],
		['retiring', 'does not follow the window control'],
		['ranking-discount', 'does not follow the control']
	]) {
		const snapshot = page.locator(`[data-window-exempt="${id}"]`);
		await expect(snapshot).toContainText(sentence);
		await expect(snapshot).not.toHaveAttribute('data-window-days', /.*/);
	}

	// And the ranking weight, which the run reduced over its own span when it
	// ran. Redrawing it over seven days would print a number no run applied.
	const weight = page.locator('[data-window-exempt="ranking-discount"]');
	await expect(weight).toContainText('does not follow the control');
	await expect(weight).not.toHaveAttribute('data-window-days', /.*/);
});
test.describe("remaining one-day words and keys on generated records", () => {
	test.use({ bypassCSP: true });

let browserCode: string;
test.beforeAll(async () => { browserCode = await clientCode([["Retiring","./src/lib/console/voices/RetiringPanel.svelte"]]); });
async function drawRecord(page: Page, name: string, props: Record<string, unknown>) {
	await page.goto('/console/voices/');
	await page.addScriptTag({ content: browserCode });
	const strip = (props.data as { retiring: Retiring | null }).retiring;
	const drawing = retirementDrawing(strip, 6);
	const config = consoleConfig();
	await page.evaluate(({ strip, drawing, index, config }) => {
		document.querySelector('main')?.replaceChildren();
		drawing.index = new Map(index);
		window.oneDayWords.draw('Retiring', { strip, drawing, cap: config.source_rows, readoutMaxShare: 1, width: config.chart_width, height: config.chart_height });
	}, { strip, drawing, index: [...drawing.index], config });
}

function voiceData(_preset: number, recordedDates: string[]): { retiring: Retiring } {
	const squares = recordedDates.map((date) => ({ date, state: 'nothing' as const, label: `${shortDate(date)}: it decided nothing that day.` }));
	const source = {
		sourceId: 'source-a', title: 'source-a', squares, share: null,
		publications: 0, decisions: 0, opportunities: 0, unjudged: false,
		daysUnder: 0, daysLeft: null, retiresOn: null, retired: false, dwellFrom: null,
		marks: { ...shareMarks(0, 0.5), empty: true }, readout: 'Nothing was decided.'
	};
	return {
		retiring: {
			dates: recordedDates, dwellDays: 14, autoRetire: false,
			runId: '2030-06-15-1', generatedAt: '2030-06-15T19:00:00Z',
			alarmPoint: 0.5, clear: 0, hidden: 0,
			rows: [source],
			completeDates: recordedDates.length, minCompleteDays: 14, minDecisions: 10,
			unjudgedHidden: 0,
			unjudged: ['source-b'].map((sourceId) => ({
				...source, sourceId, title: sourceId, unjudged: true
			}))
		}
	};
}

for (const preset of [1, 7]) {
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
		else if (state === 'empty') await expect(page.locator('[data-empty-state="quiet"]')).toHaveCount(1);
		else {
			await expect(page.locator('[data-retiring="table"]')).toHaveAttribute('data-readout-none', 'no source has a day on record, so there is no square to read; agreed with Susan');
			await expect(page.locator('[data-retiring-no-strip]')).toBeVisible();
		}
	});
}
});
