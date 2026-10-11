/** Does the machine's memory bar reach a reader saying only what it can prove?
 *
 * The module's arithmetic is checked in `memory-held.spec.ts`, in plain Node
 * against rows built there. This half proves the same figures reach a page: that
 * the two brackets really do overlap on screen rather than merely being called
 * overlapping, that a day whose parts overshoot the machine draws the overshoot,
 * and that the panel says which of its two shapes a reader is looking at.
 *
 * **The overlap is the point, and it is the one thing prose cannot carry.** A
 * reader can add two bars drawn end to end, and adding these two gives 1.21 to
 * 1.87 times the machine, measured 2026-09-21 over the 378 committed rows that
 * carry a machine reading. Two bars that visibly sit on top of each other refuse
 * that addition without anybody having to read a caption.
 *
 * Independent rows mount the retained real component's two shapes, overlap,
 * disagreement and swap. A separate native-route oracle holds its newest-day
 * query to a built ledger's deliberately unmeasured newest day.
 */

import { expect, test, type Page } from './support/door-page';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { memoryHeld } from '../src/lib/console/machine/memory-held';
import { windowOfDays } from '../src/lib/charts/viewport';
import { clientCode, drawClient } from './support/console-window/client-render';
import { openMachine } from './support/machine-record-state';
import { buildRows, serveToPage } from './support/ledger-lifecycle';
import * as queries from '../src/lib/console/queries/machine';

const DESKTOP = { width: 1280, height: 900 };

/** The panel, wherever its group puts it. Read by id rather than by title,
 * because the title is prose and a row may rewrite it. */
const PANEL = '[data-console-panel-id="memory-held"]';
const GIB = 2 ** 30;
const reading = (date: string, cells: Record<string, number> = {}) => Object.fromEntries(
	Object.entries({ date, item_id: date, os_mem_total_bytes: 16 * GIB,
		os_mem_available_bytes: 6 * GIB, llama_rss_bytes: 12 * GIB, python_rss_bytes: 2 * GIB,
		os_swap_total_bytes: GIB, os_swap_free_bytes: GIB, ...cells }).map(([key, value]) => [key, String(value)])
);
const record = memoryHeld([
	{ date: '2026-08-01', item_id: 'unrecorded' },
	reading('2026-08-08'),
	reading('2026-08-18', { llama_rss_anon_bytes: 4 * GIB, python_rss_anon_bytes: GIB,
		os_swap_free_bytes: GIB - 1024 ** 2 }),
	reading('2026-08-19', { llama_rss_anon_bytes: 12 * GIB, python_rss_anon_bytes: 2 * GIB })
]);
let panelCode: string;
test.beforeAll(async () => {
	panelCode = await clientCode([['MemoryHeldPanel', './src/lib/console/machine/MemoryHeldPanel.svelte']]);
});
async function drawHeld(page: Page, days: number) {
	const span = windowOfDays('2026-08-19', days, 'right');
	await drawClient(page, panelCode, 'MemoryHeldPanel', {
		record, start: span.start, end: span.end, days
	});
	await page.addStyleTag({ content: readFileSync(resolve('src', 'styles', 'tokens.css'), 'utf8') });
}

test.beforeEach(async ({ page }) => {
	await page.setViewportSize(DESKTOP);
	await drawHeld(page, 30);
});

test('THE ORACLE: the drawn parts add up to the machine, on every bar the page draws', async ({
	page
}) => {
	const panel = page.locator(PANEL);
	await expect(panel, 'the machine memory panel is not on the Hardware route').toBeVisible();

	const bars = await panel.locator('[data-memory-bar]').evaluateAll((nodes) =>
		nodes.map((node) => ({
			date: node.getAttribute('data-memory-bar') ?? '',
			total: Number(node.getAttribute('data-memory-total')),
			parts: [...node.querySelectorAll('[data-memory-segment]')].map((part) => ({
				key: part.getAttribute('data-memory-segment') ?? '',
				bytes: Number(part.getAttribute('data-memory-bytes'))
			}))
		}))
	);

	expect(bars.length, 'the canary carries machine readings and the page drew no bar').toBeGreaterThan(
		0
	);
	for (const bar of bars) {
		expect(bar.parts.length, `${bar.date} drew a bar with no parts`).toBeGreaterThanOrEqual(2);
		const drawn = bar.parts.reduce((sum, part) => sum + part.bytes, 0);
		// Exact. The four-slice stack this panel replaced reads 1.21 to 1.87
		// times the machine, so a tolerance here is the gap that stack fits
		// through.
		expect(drawn, `${bar.date} draws parts that are not the machine`).toBe(bar.total);
		for (const part of bar.parts) {
			expect(part.bytes, `${bar.date} draws ${part.key} larger than the machine`).toBeLessThanOrEqual(
				bar.total
			);
		}
	}
});

test('THE ORACLE: the two brackets are drawn on top of each other, not beside each other', async ({
	page
}) => {
	const panel = page.locator(PANEL);
	const bracketed = panel.locator('[data-memory-brackets="2"]').first();
	await expect(bracketed, 'no bar drew both process readings').toBeVisible();

	const server = bracketed.locator('[data-memory-bracket-bar="server"]');
	const worker = bracketed.locator('[data-memory-bracket-bar="worker"]');
	const serverBox = await server.boundingBox();
	const workerBox = await worker.boundingBox();
	expect(serverBox, 'the model server bracket has no box on the page').not.toBeNull();
	expect(workerBox, 'the worker bracket has no box on the page').not.toBeNull();

	// They share an origin, so the overlap is the narrower one's whole width.
	// Anything less means somebody put them end to end, which is the addition
	// this panel exists to refuse.
	const overlap =
		Math.min(serverBox!.x + serverBox!.width, workerBox!.x + workerBox!.width) -
		Math.max(serverBox!.x, workerBox!.x);
	expect(overlap, 'the two brackets do not overlap on screen').toBeGreaterThan(
		Math.min(serverBox!.width, workerBox!.width) * 0.99
	);
	// A stripe a reader cannot see is not an overlap they can refuse to add.
	expect(overlap, 'the overlap is too narrow to read').toBeGreaterThan(8);

	// And the label that says why.
	const labels = await bracketed.locator('[data-memory-bracket] .tag').allInnerTexts();
	expect(labels.length, 'a bracket carries no label').toBe(2);
	for (const label of labels) {
		expect(label, 'a bracket does not say it is an upper bound').toContain('at most');
	}
});

test('THE ORACLE: a bar whose parts overshoot the machine draws the disagreement', async ({
	page
}) => {
	const panel = page.locator(PANEL);
	// The canary builds one day where the two own-memory readings claim more
	// than the kernel says is held. No committed row does - the modelled
	// remainder is positive on all 378, 0.26 GiB at its smallest - so this state
	// is unreachable without a fixture, and it is the one state that must never
	// be quietly tidied away.
	const over = panel.locator('[data-memory-day]:has([data-memory-over-bytes])').first();
	await expect(over, 'the canary day that overshoots the machine drew no disagreement').toBeVisible();

	const overshoot = Number(
		await over.locator('[data-memory-over-bytes]').getAttribute('data-memory-over-bytes')
	);
	expect(overshoot, 'the overshoot was clamped to nothing').toBeGreaterThan(0);

	// The machine's edge is marked inside the bar rather than at its end, which
	// is what says the parts ran past it.
	const edge = over.locator('[data-memory-machine-edge]');
	await expect(edge, 'the bar did not mark where the machine ended').toBeVisible();
	const bar = over.locator('[data-memory-bar]');
	const scale = Number(await bar.getAttribute('data-memory-scale'));
	const total = Number(await bar.getAttribute('data-memory-total'));
	expect(scale, 'the bar was drawn against the machine and the parts trimmed to fit').toBe(
		total + overshoot
	);

	// Said in words as well, because a mark nobody explains reads as a bug.
	await expect(over.locator('.disagree')).toContainText('past the machine');
});

test('the panel says which shape a reader is looking at, and when the reading begins', async ({
	page
}) => {
	const panel = page.locator(PANEL);
	// Two of the canary's four reading days carry what each process holds on its
	// own and two do not, so the mixed sentence is the one that renders.
	const shapes = await panel.locator('[data-memory-shapes]').getAttribute('data-memory-shapes');
	expect(shapes, 'the panel does not count its two shapes').toMatch(/^\d+\/\d+$/);
	const [four, two] = (shapes ?? '').split('/').map(Number);
	expect(four + two, 'the shape counts do not add up to the bars drawn').toBe(
		await panel.locator('[data-memory-bar]').count()
	);
	expect(four, 'no day drew the four-part shape').toBeGreaterThan(0);
	expect(two, 'no day drew the two-part shape').toBeGreaterThan(0);

	// A shape attribute on every bar, so which one a reader is looking at is
	// readable off the bar and not only off the sentence under the list.
	const drawn = await panel.locator('[data-memory-shape]').evaluateAll((nodes) =>
		nodes.map((node) => node.getAttribute('data-memory-shape'))
	);
	expect(new Set(drawn), 'a bar drew a shape the panel does not name').toEqual(
		new Set(['four', 'two'])
	);

	// The ledger reaches further back than the reading does. A reader not told
	// that reads the gap as a quiet machine.
	const begins = panel.locator('[data-memory-begins]');
	await expect(begins, 'the panel does not say when the machine reading begins').toBeVisible();
	await expect(begins).toContainText(/\d{4}-\d{2}-\d{2}/);

	// The one thing it cannot separate, said on the panel.
	await expect(panel, 'the panel does not say what it cannot separate').toContainText(
		'may not be added'
	);
});

test('the swap in use is ruled under the bar, and none is not the same as no reading', async ({
	page
}) => {
	const panel = page.locator(PANEL);
	const swaps = await panel.locator('[data-memory-swap-used]').evaluateAll((nodes) =>
		nodes.map((node) => ({
			used: Number(node.getAttribute('data-memory-swap-used')),
			text: (node.textContent ?? '').replace(/\s+/g, ' ').trim()
		}))
	);
	expect(swaps.length, 'no bar ruled its swap underneath').toBeGreaterThan(0);

	// Measured 2026-09-21 over the 378 committed rows: a median of 60 KiB, a p90
	// of 61.1 MiB and a worst of 657.9 MiB, non-zero on 346 of them. At the
	// machine's scale the median paints four ten-thousandths of a percent, so the
	// rule is drawn against the swap file's own size and the figure is printed
	// beside it either way.
	for (const swap of swaps) {
		expect(swap.text, 'a swap rule carries no figure').toMatch(/(KiB|MiB|GiB)/);
		if (swap.used === 0) {
			expect(swap.text, 'an untouched swap did not say so in words').toContain('Nothing');
		} else {
			expect(swap.text, 'a swap in use did not say what was pushed out').toContain('pushed out');
		}
	}
	expect(
		swaps.some((swap) => swap.used > 0),
		'no canary day has any swap in use, so the drawn state is untested'
	).toBe(true);
	expect(
		swaps.some((swap) => swap.used === 0),
		'no canary day reads an untouched swap, so the other state is untested'
	).toBe(true);
});

test('a narrowed component span narrows its bars and names its own grain', async ({ page }) => {
	const panel = page.locator(PANEL);
	// The subtitle's last clause carries the grain, as every subtitle on this
	// route does. `console-frame.spec.ts` holds the rule; this holds it to the
	// number the control is actually on.
	const note = ((await panel.locator(':scope > header > p').textContent()) ?? '')
		.replace(/\s+/g, ' ')
		.trim();
	expect(note, 'the subtitle does not name the span it was drawn at').toMatch(
		/(?:these \d+ days|this one day)\.$/
	);

	const wide = await panel.locator('[data-memory-bar]').count();
	// The canary puts one reading day ten days back, so the narrowest preset
	// cannot reach it and the widest can. A panel that ignored the control would
	// draw the same count at both.
	await drawHeld(page, 7);
	await expect(panel.locator('[data-memory-bar]')).toHaveCount(wide - 1);
	const narrowNote = ((await panel.locator(':scope > header > p').textContent()) ?? '')
		.replace(/\s+/g, ' ')
		.trim();
	expect(narrowNote, 'the subtitle kept the span the page opened at').toContain('over these 7 days');
});

test('the native route does not substitute an older memory bar for its newest unmeasured day', async ({ page }) => {
	const root = test.info().outputPath('newest-memory-records');
	const days = ['2026-08-19', '2026-08-20'];
	const cells = (ledger: string) => Object.fromEntries(Object.values(queries)
		.filter((query) => query.ledger === ledger).flatMap((query) => query.columns)
		.map((column) => [column, null]));
	await buildRows(root, 'item-health', days.map((date, index) => ({ covers: date, rows: [{
		...cells('item-health'), date, run_id: `${date}-1`, item_id: date,
		...(index === 0 ? { os_mem_total_bytes: 16 * GIB, os_mem_available_bytes: 6 * GIB,
			llama_rss_bytes: 12 * GIB, python_rss_bytes: 2 * GIB } : {})
	}] })));
	await buildRows(root, 'host-fingerprint', days.map((date) => ({ covers: date, rows: [{
		...cells('host-fingerprint'), date, run_id: `${date}-1`, job: 'work', shard: 0,
		fingerprint: '0123456789abcdef', cpu_model: 'Fixture CPU', cores: 4, threads: 8
	}] })));
	await buildRows(root, 'run-shards', days.map((date) => ({ covers: date, rows: [{
		date, run_id: `${date}-1`, shards: null
	}] })));
	for (const ledger of ['item-health', 'host-fingerprint', 'run-shards'] as const) {
		await serveToPage(page.context(), root, ledger);
	}
	await openMachine(page);
	await expect(page.locator(`${PANEL} [data-memory-bar]`)).toHaveCount(0);
	await expect(page.locator(`${PANEL} [data-machine-panel-empty="memory-held"]`)).toBeVisible();
});
