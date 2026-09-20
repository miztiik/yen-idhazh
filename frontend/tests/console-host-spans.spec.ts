/** The two figures outside the model call, drawn as one shape twice.
 *
 * The panel used to write each of them as a reading and a span in prose. A
 * reader could follow either sentence and compare neither, because the two were
 * written in different units with their ends buried mid-paragraph. One track
 * each puts the run's own mark on the window that measured it, and the oracle
 * below is what stops the drawing and the numbers parting: every band is
 * re-derived from the attributes the page published, with none of the builder's
 * code in the loop.
 *
 * The builder tests drive a built parameter rather than the committed archive,
 * so they cost the same on the day the archive is a thousand runs long.
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

test.describe('the panel draws what it publishes', () => {
	test('THE ORACLE: every band lands where the numbers beside it say', async ({ page }) => {
		await page.goto('/console/machine/');

		const tracks = await page.locator('[data-host-span]').evaluateAll((nodes) =>
			nodes.map((node) => {
				const band = node.querySelector('[data-host-mark="band"]');
				const now = node.querySelector('[data-host-mark="now"]');
				// Every sentence the panel owes the reader is a named node, so this
				// oracle reads the state the page branched on rather than the wording
				// it chose. A check against wording passes on the day somebody edits
				// the sentence and drops the numbers out of it.
				const said = (note: string) =>
					(node.querySelector(`[data-host-note="${note}"]`)?.textContent ?? '').trim().length;
				return {
					name: node.getAttribute('data-host') ?? '',
					value: node.getAttribute('data-host-value') ?? '',
					low: node.getAttribute('data-host-span-low') ?? '',
					high: node.getAttribute('data-host-span-high') ?? '',
					scale: node.getAttribute('data-host-span-scale') ?? '',
					mode: node.getAttribute('data-host-span') ?? '',
					start: band instanceof HTMLElement ? band.style.insetInlineStart : '',
					length: band instanceof HTMLElement ? band.style.inlineSize : '',
					at: now instanceof HTMLElement ? now.style.insetInlineStart : '',
					saidSpan: said('span'),
					saidMark: said('mark'),
					saidAbsent: said('absent'),
					saidUnread: said('unread')
				};
			})
		);

		expect(tracks.map((track) => track.name).sort()).toEqual(['cpu-busy', 'model-load']);

		// An unread figure says so and draws nothing. Both halves are checked
		// here, because a panel that drew a zero-length band would still pass a
		// check that only read the mode.
		for (const track of tracks.filter((track) => track.mode === 'unread')) {
			expect(track.low).toBe('');
			expect(track.high).toBe('');
			expect(track.scale).toBe('');
			expect(track.start, `${track.name} drew a band with no span behind it`).toBe('');
			expect(track.at).toBe('');
			expect(track.saidUnread, `${track.name} is unread and said nothing`).toBeGreaterThan(0);
		}

		const spanned = tracks.filter((track) => track.mode !== 'unread');
		expect(
			spanned.length,
			'no figure on the canary carries a span, so this oracle checked nothing'
		).toBeGreaterThan(0);

		for (const track of spanned) {
			const low = Number(track.low);
			const high = Number(track.high);
			const scale = Number(track.scale);
			expect(scale, `${track.name} drew a track with no length`).toBeGreaterThan(0);
			expect(low).toBeLessThanOrEqual(high);
			expect(high).toBeLessThanOrEqual(scale);

			// The band's near end is the window's low, as a share of the track.
			expect(Number.parseFloat(track.start)).toBeCloseTo((low / scale) * 100, 3);
			if (track.mode === 'drawn') {
				expect(Number.parseFloat(track.length)).toBeCloseTo(((high - low) / scale) * 100, 3);
				expect(track.saidMark, `${track.name} drew a band and called it a mark`).toBe(0);
			} else {
				// Printed instead of drawn, so the panel owes the reader the words.
				expect(track.length).toBe('');
				expect(track.saidMark, `${track.name} printed a mark and said nothing`).toBeGreaterThan(0);
			}

			// Nothing here is a fact only a pointer can reach: both ends and the
			// run's own reading are written out beside the band that drew them.
			expect(track.saidSpan, `${track.name} drew a band with no numbers beside it`).toBeGreaterThan(
				0
			);
			if (track.value === '') {
				expect(track.saidAbsent, `${track.name} has no reading and did not say so`).toBeGreaterThan(
					0
				);
				expect(track.at).toBe('');
			} else {
				expect(track.saidAbsent).toBe(0);
				expect(Number.parseFloat(track.at)).toBeCloseTo((Number(track.value) / scale) * 100, 3);
			}
		}
	});
});
