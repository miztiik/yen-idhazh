import { expect, test } from '@playwright/test';
import { memoryHeld, memoryHeldWithin } from '../src/lib/console/machine/memory-held';

/**
 * Plan 37 row #20: the arithmetic behind the machine's memory bar, checked in
 * plain Node against rows built here.
 *
 * **The claim under test is that the bar cannot lie about the machine.** The
 * first shape of this panel - the model server, our python, the page cache and
 * what is free, side by side, summing to the machine - overshoots the machine on
 * **378 of 378 committed rows that carry the kernel reading, by 1.21x at the
 * narrowest and 1.87x at the widest, measured 2026-09-21 over
 * `state/item-health/`**. Two independent double-counts cause it: the mapped
 * weight file is resident in the server and in the page cache at once, and what
 * the kernel calls available is mostly that same page cache. So the oracle here
 * is arithmetic rather than visual - the parts that are drawn as a bar add up to
 * the machine exactly, and a shape that overshoots it fails.
 *
 * Nothing here reads the committed ledger (`CLAUDE.md` section 13): every row is
 * built in the test, so its cost is fixed whatever the archive grows to.
 */

/** The two readings the four-segment shape needs, and the four the machine's
 * own partition needs. Bytes, as the ledger stores them. */
function row(cells: Record<string, string | number>): Record<string, string> {
	const built: Record<string, string> = {};
	for (const [name, value] of Object.entries(cells)) built[name] = String(value);
	return built;
}

const MACHINE = 16766414848;

/** A day in the shape every committed row is in: the machine's own total and
 * what the kernel said was available, with no reading of what either process
 * holds on its own. */
function twoSegmentDay(date: string, availableBytes: number, itemId = 'ai-01') {
	return row({
		date,
		item_id: itemId,
		os_mem_total_bytes: MACHINE,
		os_mem_available_bytes: availableBytes,
		os_swap_total_bytes: 3221221376,
		os_swap_free_bytes: 3179167744,
		llama_rss_bytes: 13723394048,
		python_rss_bytes: 1188237312
	});
}

/** The same day with the two anonymous readings on it, which is what turns the
 * held part into three parts a reader may add. */
function fourSegmentDay(
	date: string,
	availableBytes: number,
	serverAnon: number,
	workerAnon: number,
	itemId = 'ai-01'
) {
	return row({
		...twoSegmentDay(date, availableBytes, itemId),
		llama_rss_anon_bytes: serverAnon,
		python_rss_anon_bytes: workerAnon
	});
}

/** Every span, so a filter that quietly dropped a day would fail rather than
 * pass with fewer bars. */
const WHOLE_SPAN = { start: '2000-01-01', end: '2999-12-31' };

test('THE ORACLE: the drawn parts add up to the machine, and never past it', () => {
	// Three days, one of each shape the panel can draw: two segments, four that
	// close, and four that overshoot because the two own-memory readings and the
	// kernel's disagree.
	const record = memoryHeld([
		twoSegmentDay('2026-09-18', 5455843328),
		fourSegmentDay('2026-09-19', 5455843328, 8042871584, 1093178327),
		fourSegmentDay('2026-09-20', 8000000000, 8500000000, 1100000000)
	]);
	const view = memoryHeldWithin(record, WHOLE_SPAN.start, WHOLE_SPAN.end);

	expect(view.days.length, 'a day with a machine reading drew no bar').toBe(3);
	for (const day of view.days) {
		const drawn = day.segments.reduce((total, segment) => total + segment.bytes, 0);
		// Exact, not near. Every part is an integer count of bytes off one row,
		// so a rounding tolerance here would be a place for a double-count to
		// hide. This is the assertion that fails if anyone puts the page cache
		// back in beside what is free, or the resident sets back in beside what
		// is held: that stack reads 1.21 to 1.87 times the machine.
		expect(drawn, `${day.date} draws parts that are not the machine`).toBe(day.totalBytes);
		// The other half of the same claim, stated the way a reader would: no
		// single part is bigger than the machine it is drawn inside.
		for (const segment of day.segments) {
			expect(
				segment.bytes,
				`${day.date} draws ${segment.key} larger than the whole machine`
			).toBeLessThanOrEqual(day.totalBytes);
		}
	}
});

test('a shape that overshoots the machine is drawn, not clamped', () => {
	// The kernel says 8.77 GiB is held; the two own-memory readings claim 9.60
	// GiB between them. That is two readings taken a moment apart disagreeing,
	// and a panel that clamped the remainder to zero would delete the finding
	// while still passing every sum above.
	const record = memoryHeld([fourSegmentDay('2026-09-20', 8000000000, 8500000000, 1100000000)]);
	const day = record.days[0];

	expect(day.shape, 'a row with both anonymous readings drew the two-part shape').toBe('four');
	const rest = day.segments.find((segment) => segment.key === 'rest');
	expect(rest?.bytes, 'the remainder was clamped instead of drawn').toBe(-833585152);
	expect(day.restBytes, 'the remainder lost its sign').toBeLessThan(0);
	expect(day.overBytes, 'the overshoot was not measured').toBe(833585152);
	// The bar widens to hold the overshoot and marks where the machine ended,
	// rather than trimming the parts to fit inside it.
	expect(day.scaleBytes, 'the bar was drawn against the machine and the parts trimmed').toBe(
		day.totalBytes + day.overBytes
	);
	expect(day.machineWidth, 'the machine edge was not moved off the end').not.toBe('100%');
	// Still exact, sign included.
	expect(day.segments.reduce((total, segment) => total + segment.bytes, 0)).toBe(day.totalBytes);
});

test('the two brackets are anchored together, so they overlap by the narrower one', () => {
	const record = memoryHeld([twoSegmentDay('2026-09-19', 5455843328)]);
	const day = record.days[0];

	expect(day.brackets.map((bracket) => bracket.key)).toEqual(['server', 'worker']);
	for (const bracket of day.brackets) {
		expect(bracket.label, `the ${bracket.key} bracket does not say it is a bound`).toContain(
			'at most'
		);
	}
	// What a reader would have counted twice if the two were drawn end to end.
	expect(day.overlapBytes, 'the shared stretch is not the narrower bracket').toBe(1188237312);
	// Measured 2026-09-21: the model server's resident set is larger than
	// everything the kernel calls held on 375 of 378 committed rows, because
	// most of it is the mapped weight file. A bracket that could be read as
	// sitting inside the held part would be a false statement about 99.2 percent
	// of the record.
	const server = day.brackets.find((bracket) => bracket.key === 'server');
	expect(server?.pastHeld, 'a bracket past what is held did not say so').toBe(true);
});

test('a day with no machine reading draws no bar, and the panel says when the reading begins', () => {
	const record = memoryHeld([
		row({ date: '2026-08-24', item_id: 'ai-01', llama_rss_bytes: 13723394048 }),
		row({ date: '2026-08-25', item_id: 'ai-01' }),
		twoSegmentDay('2026-09-19', 5455843328)
	]);

	expect(record.days.map((day) => day.date), 'a day with no machine total drew a bar').toEqual([
		'2026-09-19'
	]);
	expect(record.firstDate, 'the panel cannot say when the reading begins').toBe('2026-09-19');
	// The ledger reaches back further than the reading does, and a reader who is
	// not told that reads the gap as a quiet machine.
	expect(record.daysRead, 'the days with no reading were not counted at all').toBe(3);
});

test('the bar is one moment, so it reads the row with the least left to hand out', () => {
	const record = memoryHeld([
		twoSegmentDay('2026-09-19', 9000000000, 'ai-02'),
		twoSegmentDay('2026-09-19', 5455843328, 'ai-01'),
		twoSegmentDay('2026-09-19', 7000000000, 'ai-03')
	]);
	const day = record.days[0];

	expect(day.itemId, 'the day was drawn off a looser moment than its tightest').toBe('ai-01');
	const free = day.segments.find((segment) => segment.key === 'free');
	expect(free?.bytes, 'the parts came from more than one moment').toBe(5455843328);
});

test('the swap is read off the same row, and zero is not the same as no reading', () => {
	const inUse = memoryHeld([twoSegmentDay('2026-09-19', 5455843328)]).days[0];
	expect(inUse.swap?.usedBytes, 'the swap in use is not the difference of the two cells').toBe(
		42053632
	);
	expect(inUse.swap?.none, 'a swap in use read as none').toBe(false);

	const untouched = memoryHeld([
		row({
			date: '2026-09-19',
			item_id: 'ai-01',
			os_mem_total_bytes: MACHINE,
			os_mem_available_bytes: 5455843328,
			os_swap_total_bytes: 3221221376,
			os_swap_free_bytes: 3221221376
		})
	]).days[0];
	expect(untouched.swap?.none, 'an untouched swap did not say so').toBe(true);

	const unread = memoryHeld([
		row({
			date: '2026-09-19',
			item_id: 'ai-01',
			os_mem_total_bytes: MACHINE,
			os_mem_available_bytes: 5455843328
		})
	]).days[0];
	expect(unread.swap, 'a row with no swap reading invented one').toBeNull();
});

test('the open span decides which days are drawn, and the shape count follows it', () => {
	const record = memoryHeld([
		twoSegmentDay('2026-09-10', 5455843328),
		fourSegmentDay('2026-09-19', 5455843328, 8042871584, 1093178327)
	]);

	const wide = memoryHeldWithin(record, '2026-09-01', '2026-09-30');
	expect(wide.days.length).toBe(2);
	expect(wide.fourShape, 'the four-part days were miscounted').toBe(1);
	expect(wide.twoShape, 'the two-part days were miscounted').toBe(1);
	expect(wide.empty).toBe(false);

	const narrow = memoryHeldWithin(record, '2026-09-15', '2026-09-30');
	expect(narrow.days.length, 'a day outside the span was drawn').toBe(1);
	expect(narrow.twoShape, 'a count was carried over from the wider span').toBe(0);

	const none = memoryHeldWithin(record, '2026-10-01', '2026-10-31');
	expect(none.empty, 'a span with no day did not report itself empty').toBe(true);
	expect(none.firstDate, 'an empty span forgot when the reading begins').toBe('2026-09-10');
});
