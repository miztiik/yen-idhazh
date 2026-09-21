/** A reading and the window it is read against, as one band and one upright.
 *
 * Every rule the shape has is checked here as arithmetic: where the band
 * starts, where it ends, where the run's own mark falls on it, and the three
 * states an absent reading or an unread window leave it in.
 *
 * **No panel draws this today.** The shape is kept whole, with its rules held
 * here, because the honest version of the processor share it was drawn for is
 * the one that separates out the time another tenant took - and that figure
 * needs the same band rather than a second one. A panel that draws it owes a
 * page oracle putting a real band against the numbers printed beside it.
 *
 * These are pure functions over built parameters rather than the committed
 * archive, so they cost the same on the day the archive is a thousand runs long.
 */

import { expect, test } from '@playwright/test';
import { spanTrack } from '../src/lib/charts/span-track';

/** A drawing width wide enough that a band of any real width is a length. */
const WIDE = 760;

test.describe('a figure with a span is a track, not a sentence', () => {
	test('the band is the window and the upright is this run inside it', () => {
		const track = spanTrack(75, { low: 50, high: 100, from: 9, outOf: 12 }, { width: WIDE });
		expect(track.spanned).toBe(true);
		if (!track.spanned) return;
		// No ceiling, so the track ends at the largest reading drawn on it.
		expect(track.scale).toBe(100);
		expect(track.start).toBe('50.0000%');
		expect(track.length).toBe('50.0000%');
		expect(track.at).toBe('75.0000%');
		expect(track.drawn).toBe(true);
	});

	test('a ceiling ends the track even where no run reached it', () => {
		const track = spanTrack(94, { low: 90, high: 96, from: 9, outOf: 12 }, {
			ceiling: 100,
			width: WIDE
		});
		expect(track.spanned).toBe(true);
		if (!track.spanned) return;
		// The gap between 96 and 100 is the point of the figure, so the track has
		// to keep it. A track that ended at 96 would draw the worst run as full.
		expect(track.scale).toBe(100);
		expect(track.start).toBe('90.0000%');
		expect(track.length).toBe('6.0000%');
	});

	test('a reading past its ceiling draws past the band, never on the end of it', () => {
		const track = spanTrack(120, { low: 80, high: 120, from: 4, outOf: 4 }, {
			ceiling: 100,
			width: WIDE
		});
		expect(track.spanned).toBe(true);
		if (!track.spanned) return;
		// The ceiling joins the readings rather than capping them: a breach that
		// drew at the ceiling would report a run that just reached it.
		expect(track.scale).toBe(120);
		expect(track.at).toBe('100.0000%');
	});

	test('a window that recorded nothing is unread, so there is no band', () => {
		const track = spanTrack(75, { low: null, high: null, from: 0, outOf: 12 }, { width: WIDE });
		expect(track.spanned).toBe(false);
		// The run's own reading survives the absence. A window with no span and a
		// run with no reading are different facts, and the panel says so.
		expect(track.value).toBe(75);
		expect(track.low).toBeNull();
		expect(track.high).toBeNull();
		expect(track.outOf).toBe(12);
	});

	test('a run that recorded nothing keeps the window it cannot be placed on', () => {
		const track = spanTrack(null, { low: 50, high: 100, from: 9, outOf: 12 }, { width: WIDE });
		expect(track.spanned).toBe(true);
		if (!track.spanned) return;
		expect(track.value).toBeNull();
		expect(track.low).toBe(50);
		expect(track.high).toBe(100);
	});

	test('a span every run agreed on is a mark, not a hairline', () => {
		const flat = spanTrack(500, { low: 500, high: 500, from: 9, outOf: 12 }, { width: WIDE });
		expect(flat.spanned).toBe(true);
		if (!flat.spanned) return;
		// Under one pixel at the drawing width, so it is printed rather than
		// drawn as a length nobody can see.
		expect(flat.drawn).toBe(false);
		expect(flat.length).toBe('0.0000%');

		// The same pair on a narrow track is still a mark, and a wider gap on the
		// same track is a length: the rule is the pixel, not the pair of readings.
		const thin = spanTrack(1000, { low: 999, high: 1000, from: 9, outOf: 12 }, { width: 100 });
		expect(thin.spanned).toBe(true);
		if (!thin.spanned) return;
		expect(thin.drawn).toBe(false);

		const wide = spanTrack(1000, { low: 990, high: 1000, from: 9, outOf: 12 }, { width: WIDE });
		expect(wide.spanned).toBe(true);
		if (!wide.spanned) return;
		expect(wide.drawn).toBe(true);
	});
});
