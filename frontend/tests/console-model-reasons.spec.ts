import { expect, test, type Page } from '@playwright/test';
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { REASONS, reasonDays, reasonTotals } from '../src/lib/console/doubt-reasons';

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
 * Both totals are re-derived here from the committed payloads, never read off
 * the page. A spec that compares a drawn mark against the label printed beside
 * it is a consistency check, not an oracle.
 */

/** The committed digest tree. The arithmetic arm reads every day of it. */
const PUBLISHED = join(process.cwd(), 'public', 'digest');
/** The tree the site under test was built from. */
const CANARY = resolve(process.cwd(), '..', 'backend', 'var', 'canary', 'digest');
const SCHEMA = resolve(process.cwd(), '..', 'schemas', 'digest-day.schema.json');

const CONFIG = JSON.parse(
	readFileSync(resolve(process.cwd(), '..', 'config', 'appearance.json'), 'utf8')
) as { console?: { window_presets?: number[]; default_window_days?: number } };
const PRESETS = CONFIG.console?.window_presets ?? [7, 14, 30, 90];
const DEFAULT_DAYS = CONFIG.console?.default_window_days ?? 30;

interface RawItem {
	band?: string | null;
	band_reason?: string | null;
}

function dirs(at: string): string[] {
	if (!existsSync(at)) return [];
	return readdirSync(at, { withFileTypes: true })
		.filter((entry) => entry.isDirectory())
		.map((entry) => entry.name)
		.sort();
}

/** Every committed day of a tree, oldest first, read straight off disk. */
function daysOf(root: string): { date: string; items: RawItem[] }[] {
	const found: { date: string; items: RawItem[] }[] = [];
	for (const year of dirs(root)) {
		for (const month of dirs(join(root, year))) {
			for (const day of dirs(join(root, year, month))) {
				const path = join(root, year, month, day, 'digest.json');
				if (!existsSync(path)) continue;
				const parsed = JSON.parse(readFileSync(path, 'utf8')) as { items?: RawItem[] };
				found.push({ date: `${year}-${month}-${day}`, items: parsed.items ?? [] });
			}
		}
	}
	return found.sort((a, b) => a.date.localeCompare(b.date));
}

/** One day counted a second time, by hand, with nothing shared with the module.
 *
 * Deliberately written as four plain loops rather than as a call into
 * `reasonDays`. An oracle that reuses the code under test cannot fail. */
function countByHand(items: readonly RawItem[]) {
	const reasons: Record<string, number> = {};
	let withReason = 0;
	let doubtful = 0;
	let highWithReason = 0;
	for (const item of items) {
		const reason = item.band_reason ?? '';
		if (reason !== '') {
			reasons[reason] = (reasons[reason] ?? 0) + 1;
			withReason += 1;
			if (item.band === 'high') highWithReason += 1;
		}
		if (item.band === 'medium' || item.band === 'low') doubtful += 1;
	}
	return { reasons, withReason, doubtful, highWithReason, items: items.length };
}

test.describe('the arithmetic, over every committed day', () => {
	test('THE ORACLE: the five counts sum to the day own reason count', () => {
		const raw = daysOf(PUBLISHED);
		// A tree with nothing in it would pass every assertion below by drawing
		// none of them, so the corpus is asserted before it is read.
		expect(raw.length, 'no committed day was found, so the oracle asserts nothing').toBeGreaterThan(
			0
		);

		const days = reasonDays(
			raw.map((day) => ({
				date: day.date,
				items: day.items.map((item) => ({
					band: item.band ?? null,
					reason: item.band_reason ?? null
				}))
			}))
		);
		expect(days.map((day) => day.date)).toEqual(raw.map((day) => day.date));

		for (const [index, day] of days.entries()) {
			const hand = countByHand(raw[index].items);
			const drawn = REASONS.reduce((sum, reason) => sum + (day.counts[reason.id] ?? 0), 0);

			expect(drawn, `${day.date}: the bands do not add up to the column`).toBe(day.explained);
			expect(day.explained, `${day.date}: the column is not the day own reason count`).toBe(
				hand.withReason
			);
			expect(day.items, `${day.date}: the denominator is not the day own item count`).toBe(
				hand.items
			);
			// The claim the panel makes in words: what is drawn plus what is said in
			// the sentence beside it accounts for every doubtful summary of the day.
			expect(
				day.explained + day.unexplained,
				`${day.date}: reasons plus the unexplained do not account for the doubtful items`
			).toBe(hand.doubtful);
			for (const reason of REASONS) {
				expect(day.counts[reason.id] ?? 0, `${day.date}: ${reason.id} was miscounted`).toBe(
					hand.reasons[reason.id] ?? 0
				);
			}
		}
	});

	test('the panel draws every reason the contract can publish, and no other', () => {
		// A sixth reason has to fail here rather than go unnoticed. The set is read
		// off the generated schema, so this is the contract and not a second copy
		// of it (`CLAUDE.md` Rule #3).
		const schema = JSON.parse(readFileSync(SCHEMA, 'utf8')) as {
			$defs?: { BandReason?: { enum?: string[] } };
		};
		const published = schema.$defs?.BandReason?.enum ?? [];
		expect(published.length, 'the schema publishes no reason enum').toBeGreaterThan(0);
		expect(
			REASONS.map((reason) => reason.id).sort(),
			'the panel and the contract disagree about which reasons exist'
		).toEqual([...published].sort());
	});

	test('no reason label is the name of the column behind it', () => {
		// A console figure says what it counts, in words (design-system.md). The
		// identifier is how the payload spells it; the page spells what it means.
		for (const reason of REASONS) {
			expect(reason.label, `${reason.id} is labelled with its own identifier`).not.toContain('_');
			expect(reason.label.length, `${reason.id} has no label`).toBeGreaterThan(3);
		}
	});

	test('a high summary never carries a reason, so no band is drawn for a clean item', () => {
		// The rule `verdict()` states and the panel depends on: the column counts
		// items the checker had something to say about, and a top-band item has
		// nothing to explain.
		for (const day of daysOf(PUBLISHED)) {
			expect(
				countByHand(day.items).highWithReason,
				`${day.date}: a top-band summary carries a reason`
			).toBe(0);
		}
	});

	test('the whole corpus totals what the committed payloads hold', () => {
		const raw = daysOf(PUBLISHED);
		const totals = reasonTotals(
			reasonDays(
				raw.map((day) => ({
					date: day.date,
					items: day.items.map((item) => ({
						band: item.band ?? null,
						reason: item.band_reason ?? null
					}))
				}))
			)
		);
		const hand = raw.reduce(
			(sum, day) => {
				const counted = countByHand(day.items);
				return {
					items: sum.items + counted.items,
					withReason: sum.withReason + counted.withReason,
					doubtful: sum.doubtful + counted.doubtful
				};
			},
			{ items: 0, withReason: 0, doubtful: 0 }
		);
		expect(totals.items).toBe(hand.items);
		expect(totals.explained).toBe(hand.withReason);
		expect(totals.explained + totals.unexplained).toBe(hand.doubtful);
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

	test('THE ORACLE: what the page drew is what the built tree holds', async ({ page }) => {
		// The fixture decides which arm runs, and the fixture is read here rather
		// than counted off the page. A skip that reads a locator count switches
		// itself off the day the attribute is renamed.
		const fixture = daysOf(CANARY);
		expect(fixture.length, 'the canary tree holds no committed day').toBeGreaterThan(0);
		const explained = fixture.reduce((sum, day) => sum + countByHand(day.items).withReason, 0);

		await page.goto('/console/model/');
		await hydrated(page);

		if (explained === 0) {
			// A real state and a designed one: the fixture published summaries and
			// the checker wrote a reason on none of them.
			await expect(page.locator('[data-model-reasons="none"]')).toHaveCount(1);
			return;
		}

		const rows = await drawn(page);
		expect(rows.length, 'the page drew no day at all').toBeGreaterThan(0);
		const byDate = new Map(fixture.map((day) => [day.date, countByHand(day.items)]));
		for (const row of rows) {
			const hand = byDate.get(row.date);
			expect(hand, `${row.date} is drawn and the built tree has no such day`).toBeDefined();
			const sum = REASONS.reduce((total, reason) => total + (row.counts[reason.id] ?? 0), 0);
			expect(sum, `${row.date}: the drawn bands do not add up to the column`).toBe(row.explained);
			expect(row.explained, `${row.date}: the column is not the day own reason count`).toBe(
				hand?.withReason
			);
			expect(row.items, `${row.date}: the denominator is not the day own item count`).toBe(
				hand?.items
			);
			expect(
				row.explained + row.unexplained,
				`${row.date}: the doubtful summaries are not all accounted for`
			).toBe(hand?.doubtful);
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
		const fixture = daysOf(CANARY);
		const seen = new Set(
			fixture.flatMap((day) => Object.keys(countByHand(day.items).reasons))
		);
		await page.goto('/console/model/');
		await hydrated(page);
		if (seen.size === 0) {
			await expect(page.locator('[data-model-reasons="none"]')).toHaveCount(1);
			return;
		}
		// One row per reason the window actually saw, in the declared order. A
		// reason that never fired draws no band, so a row for it would be a swatch
		// in a colour the plot never uses.
		const strip = page.locator('[data-readout="doubt-reasons"]');
		await expect(strip, 'the doubt-reason chart lost its readout strip').toHaveCount(1);
		// Read the labels rather than building one locator per label: two of the
		// five carry a double quote, which an attribute selector cannot hold.
		const labels = await strip
			.locator('[data-readout-row]')
			.evaluateAll((nodes) => nodes.map((node) => node.getAttribute('data-readout-row') ?? ''));
		expect(labels, 'the strip does not name exactly the reasons the window saw').toEqual(
			REASONS.filter((reason) => seen.has(reason.id)).map((reason) => reason.label)
		);
	});

	test('a reason the window never saw is named in words, not left invisible', async ({ page }) => {
		const fixture = daysOf(CANARY);
		const seen = new Set(
			fixture.flatMap((day) => Object.keys(countByHand(day.items).reasons))
		);
		const missing = REASONS.filter((reason) => !seen.has(reason.id));
		await page.goto('/console/model/');
		await hydrated(page);
		const note = page.locator('[data-model-reasons-never]');
		if (missing.length === 0) {
			await expect(note, 'every reason drew, so nothing should be named as absent').toHaveCount(0);
			return;
		}
		// Without this a reader cannot tell a reason that never fired from a reason
		// nobody thought to look for.
		await expect(note, 'a reason drew nothing and the panel never said so').toHaveCount(1);
		for (const reason of missing) {
			await expect(note, `${reason.id} drew nothing and is not named`).toContainText(reason.label);
		}
	});
});
