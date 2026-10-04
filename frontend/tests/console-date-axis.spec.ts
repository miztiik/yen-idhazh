/** Which dates a run strip labels, and how it divides spare room. */
import { expect, test } from '@playwright/test';
import { axisLabels, centreOffset, spanLabel } from '../src/lib/charts/run-history';
import { days } from './support/consecutive-days';

/** A run strip at the pitch `cellFor` settles on for a page-wide frame: a 16px
 * cell and a 4px gap. The axis is thinned against that room, so a test about it
 * has to state it. `density` is `chart.tick_density`. */
const STRIP = { density: 6, pitch: 20 };

test('one day gets a full date, and a short run gets one span', () => {
	expect(axisLabels([], STRIP)).toEqual([]);
	expect(axisLabels(['2026-08-20'], STRIP)).toEqual([
		{ column: 1, text: '20 Aug 2026', align: 'end' }
	]);

	// Two to six days cannot carry a cadence, so the whole span is said once.
	expect(spanLabel('2026-08-18', '2026-08-20')).toBe('18-20 Aug 2026');
	expect(spanLabel('2026-07-30', '2026-08-02')).toBe('30 Jul - 2 Aug 2026');
	expect(spanLabel('2025-12-30', '2026-01-02')).toBe('30 Dec 2025 - 2 Jan 2026');
	expect(axisLabels(days('2026-08-15', 4), STRIP)).toEqual([
		{ column: 4, text: '15-18 Aug 2026', align: 'end' }
	]);
});

test('a longer run carries both ends and as many between them as fit', () => {
	const twenty = axisLabels(days('2026-08-01', 20), STRIP);

	// The ceiling offers six columns over twenty days. At a 20px pitch the strip
	// is 380px wide, and a date is about 64px, so six of them cannot be drawn.
	// The rule drops to three rather than letting two of them touch.
	expect(twenty.map((label) => label.column)).toEqual([1, 12, 20]);
	expect(twenty.map((label) => label.text)).toEqual(['1 Aug 2026', '12 Aug', '20 Aug']);
	expect(twenty.map((label) => label.align)).toEqual(['start', 'centre', 'end']);

	// A strip with three times the room carries every column the ceiling allows.
	const wide = axisLabels(days('2026-08-01', 20), { density: STRIP.density, pitch: 60 });
	expect(wide.map((label) => label.column)).toEqual([1, 5, 9, 12, 16, 20]);
});

test('the year is stated on the first label that changes it, and not again', () => {
	const across = axisLabels(days('2025-12-20', 30), { density: STRIP.density, pitch: 60 });

	expect(across.map((label) => label.text)).toEqual([
		'20 Dec 2025',
		'26 Dec',
		'1 Jan 2026',
		'6 Jan',
		'12 Jan',
		'18 Jan'
	]);
});

test('a strip shares its spare room, and a strip with none keeps its first column', () => {
	// Half the difference, rounded, so the two margins differ by at most a pixel.
	expect(centreOffset(1326, 300)).toBe(513);
	expect(centreOffset(1326, 1290)).toBe(18);

	// An overflowing strip has no spare room to divide, and an offset there
	// would push its first column out of reach of the scroll.
	expect(centreOffset(360, 1290)).toBe(0);
	expect(centreOffset(300, 300)).toBe(0);

	// Nothing has measured the frame yet - the server, or the first frame - so
	// there is no room to share and the strip starts where it always did.
	expect(centreOffset(null, 300)).toBe(0);
	expect(centreOffset(0, 300)).toBe(0);
	expect(centreOffset(1326, 0)).toBe(0);
});
