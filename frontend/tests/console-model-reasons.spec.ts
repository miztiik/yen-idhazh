import { expect, test, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import {
	REASONS,
	neverSeenNote,
	reasonDays,
	reasonHeadline,
	reasonTotals,
	unexplainedNote
} from '../src/lib/console/doubt-reasons';

/**
 * The five reasons a summary is doubted, and the one sum that proves the chart.
 *
 * `band_reason` reaches a reader on every doubtful item and had never been
 * plotted, so nobody could say which fault dominates or whether a prompt change
 * helped. This is the oracle for the panel that answers it.
 *
 * **The oracle is a sum with a named total.** The five drawn bands must add up,
 * per day, to that day's count of published summaries carrying a reason - not to
 * its count of doubtful summaries. The two are not the same number, and saying
 * so is half the test: `band_reason` was added to the published item after the
 * first days were published, so the oldest days carry a band with nothing beside
 * it. A panel that quietly folded those into a band would draw a fault the
 * checker never named, and one that dropped them without saying so would make
 * three days look clean.
 *
 * The arithmetic is driven from days written here rather than from the committed
 * archive, which Guardrail #12 refuses and which would cost more every day the
 * pipeline publishes. It is also the stronger case: these days carry an unknown
 * reason and a day of pure absence, neither of which the archive has ever
 * produced. The browser half holds the page to its own numbers: each day the
 * panel draws adds up, and the sentences above the chart count the same days the
 * columns do. What the site was built from is never read here, so nothing below
 * changes when the canary does. That a top-band summary carries no reason is the
 * producer's rule, and `backend/tests/pipeline/test_banding.py` holds it.
 */

const CONFIG = JSON.parse(
	readFileSync(resolve(process.cwd(), '..', 'config', 'appearance.json'), 'utf8')
) as { console?: { window_presets?: number[]; default_window_days?: number } };
const PRESETS = CONFIG.console?.window_presets ?? [1, 7, 14, 30, 90];
const DEFAULT_DAYS = CONFIG.console?.default_window_days ?? 30;

interface RawItem {
	band?: string | null;
	band_reason?: string | null;
}

/** One day counted a second time, by hand, with nothing shared with the module.
 *
 * Deliberately written as one plain loop rather than as a call into
 * `reasonDays`. An oracle that reuses the code under test cannot fail. */
function countByHand(items: readonly RawItem[]) {
	const reasons: Record<string, number> = {};
	let doubtful = 0;
	for (const item of items) {
		const reason = item.band_reason ?? '';
		if (reason !== '') reasons[reason] = (reasons[reason] ?? 0) + 1;
		if (item.band === 'medium' || item.band === 'low') doubtful += 1;
	}
	return { reasons, doubtful, items: items.length };
}

/** `n` items of one shape, so a day below reads as a table rather than a list. */
function some(n: number, band: string, reason: string | null): RawItem[] {
	return Array.from({ length: n }, () => ({ band, band_reason: reason }));
}

/** Six days, covering every state the panel has to draw or explain.
 *
 * Written out on purpose. Two of these six have never occurred in the published
 * corpus - a reason the contract does not publish, and a day with items and no
 * band at all - and a fixture is the only place they can be driven from.
 */
const FIXTURE: { date: string; items: RawItem[] }[] = [
	// Out of order, so the sort is asserted rather than assumed.
	{
		date: '2026-03-04',
		items: [
			...some(3, 'low', 'unsupported_number'),
			...some(5, 'low', 'faithfulness'),
			...some(2, 'medium', 'faithfulness'),
			...some(4, 'medium', 'lead_missing'),
			...some(6, 'medium', 'hedge_dropped'),
			...some(1, 'medium', 'not_scored'),
			...some(9, 'high', null)
		]
	},
	// The days published before `band_reason` existed: a band, and nothing beside
	// it. This is the whole reason the column total is not the doubtful count.
	{ date: '2026-03-01', items: [...some(4, 'medium', null), ...some(2, 'low', null), ...some(7, 'high', null)] },
	// A clean day. Nothing to explain, and it must not read as a day nothing ran.
	{ date: '2026-03-02', items: some(11, 'high', null) },
	// A reason the panel has never heard of. It may not be counted as one of the
	// five, and the item is still doubted, so it lands in the unexplained count.
	{ date: '2026-03-03', items: [...some(2, 'low', 'a_sixth_reason'), ...some(3, 'high', null)] },
	// A day that published nothing.
	{ date: '2026-03-05', items: [] },
	// Items with no band at all - a payload older than the band itself.
	{ date: '2026-03-06', items: [{}, {}, {}] }
];

function fixtureDays() {
	return reasonDays(
		FIXTURE.map((day) => ({
			date: day.date,
			items: day.items.map((item) => ({
				band: item.band ?? null,
				reason: item.band_reason ?? null
			}))
		}))
	);
}

test.describe('the arithmetic', () => {
	test('THE ORACLE: the five counts sum to the day own reason count', () => {
		const days = fixtureDays();
		expect(days.map((day) => day.date), 'the days are not oldest first').toEqual([
			'2026-03-01',
			'2026-03-02',
			'2026-03-03',
			'2026-03-04',
			'2026-03-05',
			'2026-03-06'
		]);

		const byDate = new Map(FIXTURE.map((day) => [day.date, countByHand(day.items)]));
		for (const day of days) {
			const hand = byDate.get(day.date);
			const drawn = REASONS.reduce((sum, reason) => sum + (day.counts[reason.id] ?? 0), 0);

			expect(drawn, `${day.date}: the bands do not add up to the column`).toBe(day.explained);
			expect(day.items, `${day.date}: the denominator is not the day own item count`).toBe(
				hand?.items
			);
			// The claim the panel makes in words: what is drawn plus what is said in
			// the sentence beside it accounts for every doubtful summary of the day.
			expect(
				day.explained + day.unexplained,
				`${day.date}: reasons plus the unexplained do not account for the doubtful items`
			).toBe(hand?.doubtful);
			for (const reason of REASONS) {
				expect(day.counts[reason.id] ?? 0, `${day.date}: ${reason.id} was miscounted`).toBe(
					hand?.reasons[reason.id] ?? 0
				);
			}
		}
	});

	test('a day the checker had nothing to say about is not a day nothing ran', () => {
		const clean = fixtureDays().find((day) => day.date === '2026-03-02');
		expect(clean?.items, 'the clean day lost its item count').toBe(11);
		expect(clean?.explained, 'a top-band day drew a band').toBe(0);
		expect(clean?.unexplained, 'a top-band day was called unexplained').toBe(0);
	});

	test('a reason the panel has never heard of is never drawn as one of the five', () => {
		// A sixth reason arriving in a payload before the page knows it. Counting it
		// under a name it does not have would put a fault on the wrong band.
		const odd = fixtureDays().find((day) => day.date === '2026-03-03');
		expect(REASONS.reduce((sum, r) => sum + (odd?.counts[r.id] ?? 0), 0)).toBe(0);
		expect(odd?.explained, 'an unknown reason was counted as a drawn one').toBe(0);
		expect(odd?.unexplained, 'the item was doubted and is not accounted for').toBe(2);
	});

	test('the days with no reason written down are counted and never folded in', () => {
		const totals = reasonTotals(fixtureDays());
		// 2026-03-01 has 6, 2026-03-03 has 2, and no other day has any.
		expect(totals.unexplained).toBe(8);
		expect(totals.unexplainedDays).toBe(2);
		expect(totals.explained).toBe(21);
		expect(totals.items).toBe(3 + 5 + 2 + 4 + 6 + 1 + 9 + 13 + 11 + 5 + 0 + 3);
	});

	test('the three sentences say what the numbers mean, and say nothing when there is nothing to say', () => {
		const days = fixtureDays();
		// 7 of the 62 summaries these six days published, which rounds to 11 percent
		// and reads as one in nine.
		expect(reasonHeadline(days, 30)).toBe(
			'The reason given most often is "Does not match the article": 7 summaries in these 30 days, or about one in every nine published.'
		);
		expect(unexplainedNote(days, 30)).toBe(
			'8 of the 29 doubted summaries in these 30 days have no reason written down, on 2 days. Those columns are short by that much: the reason is missing from our record, not from the summary.'
		);
		// Every one of the five drew at least once here, so nothing is named absent.
		expect(neverSeenNote(days, 30)).toBeNull();

		// A window that doubted nothing has no headline and no gap to explain, and
		// names all five as absent rather than drawing five empty lines.
		const clean = reasonDays([{ date: '2026-03-02', items: [{ band: 'high', reason: null }] }]);
		expect(reasonHeadline(clean, 7)).toBeNull();
		expect(unexplainedNote(clean, 7)).toBeNull();
		expect(neverSeenNote(clean, 7)).toContain('"Numbers not in the article"');
		expect(neverSeenNote(clean, 7)).toContain('"Maybe" told as fact');

		// No window at all is a different fact from a window that saw nothing.
		expect(neverSeenNote([], 7)).toBeNull();
	});

	test('a share is spelled out, so the number carries what it means', () => {
		// `CLAUDE.md` section 0b: 19.8 percent is not an answer. One in five is.
		const oneInFive = reasonDays([
			{
				date: '2026-03-04',
				items: [
					...some(2, 'medium', 'faithfulness'),
					...some(8, 'high', null)
				].map((item) => ({ band: item.band ?? null, reason: item.band_reason ?? null }))
			}
		]);
		expect(reasonHeadline(oneInFive, 30)).toBe(
			'The reason given most often is "Does not match the article": 2 summaries in these 30 days, or about one in every five published.'
		);
	});

	test('no reason label is the name of the column behind it', () => {
		// A console figure says what it counts, in words (design-system.md). The
		// identifier is how the payload spells it; the page spells what it means.
		for (const reason of REASONS) {
			expect(reason.label, `${reason.id} is labelled with its own identifier`).not.toContain('_');
			expect(reason.label.length, `${reason.id} has no label`).toBeGreaterThan(3);
		}
	});
});

async function hydrated(page: Page) {
	// Disabled in the prerendered document and enabled on mount, so waiting for
	// it is waiting for the control to be able to do anything at all.
	await expect(page.locator(`[data-window-preset="${DEFAULT_DAYS}"] input`)).toBeEnabled();
}

async function setWindow(page: Page, days: number) {
	await page.locator(`[data-window-preset="${days}"]`).click();
	await expect(page.locator('[data-window-control]')).toHaveAttribute(
		'data-window-days',
		String(days)
	);
}

/** A sentence as a reader sees it, with its line breaks collapsed. */
function flat(text: string): string {
	return text.replace(/\s+/g, ' ').trim();
}

/** What the page says it drew, per day, read out of its own text list. */
async function drawn(page: Page) {
	return page.locator('[data-reason-days] [data-reason-day]').evaluateAll((nodes) =>
		nodes.map((node) => ({
			date: node.getAttribute('data-reason-day') ?? '',
			items: Number(node.getAttribute('data-reason-items')),
			explained: Number(node.getAttribute('data-reason-explained')),
			unexplained: Number(node.getAttribute('data-reason-unexplained')),
			counts: Object.fromEntries(
				[...node.querySelectorAll('[data-reason-count]')].map((cell) => [
					cell.getAttribute('data-reason-count') ?? '',
					Number(cell.getAttribute('data-reason-n'))
				])
			)
		}))
	);
}

test.describe('the panel, in a browser', () => {
	test('the section states what it counts, whatever the fixture holds', async ({ page }) => {
		await page.goto('/console/model/');
		const section = page.locator('[data-model-reasons]');
		await expect(section, 'the model route lost the doubt-reason panel').toHaveCount(1);
		// The heading and the sentence stay whatever the window holds: a panel that
		// vanishes when it has nothing teaches an operator the measurement does not
		// exist (design-system.md).
		await expect(page.locator('[data-model-reasons-intro]')).toContainText(
			'never added into one doubt count'
		);
		await expect(page.locator('[data-model-reasons-rule]')).toHaveCount(1);
	});

	test('THE ORACLE: each drawn day adds up to its column, and the sentences count the same days', async ({
		page
	}) => {
		await page.goto('/console/model/');
		await hydrated(page);
		const section = page.locator('[data-model-reasons]');
		const from = (await section.getAttribute('data-model-reasons-from')) ?? '';
		const to = (await section.getAttribute('data-model-reasons-to')) ?? '';
		const days = Number(await section.getAttribute('data-model-reasons-days'));
		expect(from, 'the panel names no window').toMatch(/^\d{4}-\d{2}-\d{2}$/);
		const rows = await drawn(page);

		// The day list is drawn exactly when the window explained something, and one
		// sentence names the empty state otherwise.
		await expect(
			page.locator('[data-model-reasons="none"], [data-model-reasons="empty"]')
		).toHaveCount(rows.length > 0 ? 0 : 1);
		const dates = rows.map((row) => row.date);
		expect(dates, 'the days are not oldest first, once each').toEqual([...new Set(dates)].sort());
		for (const row of rows) {
			expect(row.date >= from && row.date <= to, `${row.date} is outside ${from} to ${to}`).toBe(true);
			const sum = REASONS.reduce((total, reason) => total + (row.counts[reason.id] ?? 0), 0);
			expect(sum, `${row.date}: the drawn bands do not add up to the column`).toBe(row.explained);
			expect(
				row.explained + row.unexplained,
				`${row.date}: more summaries are doubted than the day published`
			).toBeLessThanOrEqual(row.items);
		}

		// The headline names the reason the columns hold most of, with their count.
		const total = (id: string) => rows.reduce((sum, row) => sum + (row.counts[id] ?? 0), 0);
		const explained = rows.reduce((sum, row) => sum + row.explained, 0);
		const headline = page.locator('[data-model-reasons-headline]');
		await expect(headline).toHaveCount(explained > 0 ? 1 : 0);
		if (explained > 0) {
			const said = flat(await headline.innerText());
			const named = /^The reason given most often is "(.+)": ([\d,]+) summaries in these (\d+) days/.exec(said);
			expect(named, `the headline names no reason and count: ${said}`).not.toBeNull();
			const reason = REASONS.find((one) => one.label === named?.[1]);
			expect(reason, `the headline names a reason the panel does not draw: ${named?.[1]}`).toBeDefined();
			const count = total(reason?.id ?? '');
			expect(Number(named?.[2].replace(/,/g, '')), 'the headline count is not its columns').toBe(count);
			expect(Math.max(...REASONS.map((one) => total(one.id))), 'another reason holds more').toBe(count);
			expect(Number(named?.[3]), 'the headline names another span').toBe(days);
		}

		// The note on the doubted summaries with no reason counts the same columns.
		const unexplained = rows.reduce((sum, row) => sum + row.unexplained, 0);
		const gap = page.locator('[data-model-reasons-unexplained]');
		await expect(gap).toHaveCount(unexplained > 0 ? 1 : 0);
		if (unexplained > 0) {
			const said = flat(await gap.innerText());
			const counted = /^([\d,]+) of the ([\d,]+) doubted summaries in these (\d+) days have no reason written down, on (\d+) days?\./.exec(said);
			expect(counted, `the note counts nothing: ${said}`).not.toBeNull();
			expect(counted?.slice(1).map((value) => Number(value.replace(/,/g, '')))).toEqual([
				unexplained,
				explained + unexplained,
				days,
				rows.filter((row) => row.unexplained > 0).length
			]);
		}
	});

	test('the panel follows the one control, without declaring a sixth windowed surface', async ({
		page
	}) => {
		// `console-window.spec.ts` pins the exact list of surfaces that carry
		// `data-windowed`, and its oracle is stronger for being an exact list. So
		// this panel honours the shared window and proves it here instead, against
		// the control's own attribute rather than against a number written twice.
		await page.goto('/console/model/');
		await hydrated(page);
		const section = page.locator('[data-model-reasons]');
		await expect(section).toHaveCount(1);
		await expect(
			section,
			'the panel declared itself windowed and moved another spec oracle'
		).not.toHaveAttribute('data-windowed', /.*/);

		for (const preset of PRESETS) {
			await setWindow(page, preset);
			await expect(
				section,
				`the panel is drawing a different window from the control at ${preset} days`
			).toHaveAttribute('data-model-reasons-days', String(preset));
			await expect(
				page.locator('[data-model-reasons-intro]'),
				`the panel never says it is showing ${preset} days`
			).toContainText(`${preset} days`);
		}
	});

	test('the strip is the key, and it prints one row per reason the window saw', async ({
		page
	}) => {
		await page.goto('/console/model/');
		await hydrated(page);
		// One row per reason the drawn days carry, in the declared order. A reason
		// that never fired draws no band, so a row for it would be a swatch in a
		// colour the plot never uses.
		const rows = await drawn(page);
		const seen = REASONS.filter((reason) => rows.some((row) => (row.counts[reason.id] ?? 0) > 0));
		const strip = page.locator('[data-readout="doubt-reasons"]');
		await expect(strip, 'the strip is not drawn exactly when a reason is').toHaveCount(
			seen.length > 0 ? 1 : 0
		);
		// Read the labels rather than building one locator per label: two of the
		// five carry a double quote, which an attribute selector cannot hold.
		const labels = await strip
			.locator('[data-readout-row]')
			.evaluateAll((nodes) => nodes.map((node) => node.getAttribute('data-readout-row') ?? ''));
		expect(labels, 'the strip does not name exactly the reasons the columns carry').toEqual(
			seen.map((reason) => reason.label)
		);
	});

	test('a reason the window never saw is named in words, not left invisible', async ({ page }) => {
		await page.goto('/console/model/');
		await hydrated(page);
		// Without this a reader cannot tell a reason that never fired from a reason
		// nobody thought to look for. The note names every reason the drawn days
		// never carried and none they did, unless the window held no day at all.
		const rows = await drawn(page);
		const missing = REASONS.filter((reason) => !rows.some((row) => (row.counts[reason.id] ?? 0) > 0));
		const noDay = (await page.locator('[data-model-reasons="empty"]').count()) > 0;
		const note = page.locator('[data-model-reasons-never]');
		await expect(note).toHaveCount(!noDay && missing.length > 0 ? 1 : 0);
		const said = (await note.count()) > 0 ? flat(await note.innerText()) : '';
		for (const reason of REASONS) {
			expect(said.includes(`"${reason.label}"`), `the note is wrong about ${reason.id}`).toBe(
				!noDay && missing.includes(reason)
			);
		}
	});
});
