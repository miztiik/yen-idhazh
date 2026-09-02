/**
 * Row #18's oracle: the reading page's columns are a zone model, and no zone in
 * it is a pixel count.
 *
 * Five zones, and every one of them is a `rem` knob in `config/appearance.json`
 * that `scripts/build-frame-css.mjs` writes into CSS:
 *
 * | zone | token | from |
 * | --- | --- | --- |
 * | the day's time rail | `--zone-time` | the small breakpoint; below it the marker is a rule across the top of its group and there is no column at all |
 * | the source mark | `--zone-mark` | every width |
 * | the card | `minmax(0, 1fr)`, its text at `--measure` | every width |
 * | the item's footer rail | `--zone-rail` | the middle breakpoint |
 * | the day's aside | `--zone-aside` | the wide breakpoint, and the rail retires |
 *
 * What makes this a gate rather than a screenshot is the second pass. Every
 * assertion runs again with the root font size raised from 16px to 22px, and
 * each zone has to have moved by the same factor. A `rem` zone moves; a `px`
 * one does not, and a track written as `14rem` today can be written as `224px`
 * tomorrow with no visible difference at the default font size. Measured on
 * this suite's own build: the mark went 28 -> 38.5, the rail 224 -> 308, the
 * aside 288 -> 396 and the time rail 88 -> 121, all 1.375x, which is 22/16.
 *
 * The zone widths are read off the page rather than written here, so this file
 * cannot disagree with the config: a knob moved in `appearance.json` moves the
 * expectation with it. What is written here is the SHAPE - how many tracks
 * there are at each width, and which token each one takes.
 *
 * One combination this fixture cannot reach: a day that has BOTH an aside and
 * items, because the canary publishes one desk and a block allowing two stories
 * a desk needs three to draw. That case is measured on the committed digest
 * instead, with hardware and date, in
 * `docs/reference/measurements.md`. What is checked here is each half - the
 * item's tracks on a day with no aside, and the aside's own geometry against
 * the stylesheet the build shipped.
 */

import { expect, test, type Page } from '@playwright/test';
import { readdirSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { leadingStories } from '../src/lib/day-shape';
import { loadDay } from '../src/lib/server/payload';

const HERE = dirname(fileURLToPath(import.meta.url));
/** The tree the preview server serves, so a route here is a route that exists. */
const BUILD = join(HERE, '..', 'build');
/** The tree that built it. `loadDay` reads the day the page rendered. */
const CANARY = resolve(HERE, '..', '..', 'backend', 'var', 'canary', 'digest');

/** Never a date written here: a hardcoded one passes on an empty page the
 * moment the fixture moves. */
const DAY = readdirSync(BUILD, { withFileTypes: true })
	.filter((entry) => entry.isDirectory() && /^\d{4}-\d{2}-\d{2}$/.test(entry.name))
	.map((entry) => entry.name)
	.sort()
	.at(-1) as string;

/** Whether the fixture day earns a leading block at all, which is what decides
 * whether the aside exists. A fact the fixture owns, computed the same way the
 * page computes it - never a count read off a locator, because a renamed
 * selector would then turn this file off and report green. */
const day = loadDay(DAY, CANARY);
const LEADS = day ? leadingStories(day.leads ?? [], day.items).length : 0;

/** One width inside each band the three committed breakpoints cut.
 * `frame.breakpoints_px` is [640, 1024, 1400].
 *
 * The widest band depends on the fixture, and that is the behaviour rather than
 * a fixture accident: the item gives its trailing rail back to a day that grew
 * an aside, and keeps it on a day that did not. Every committed day before
 * 2026-09-01 has no leading block, because the block did not exist yet.
 */
const BANDS = [
	{ name: 'below the small breakpoint', width: 360, tracks: 2, trailing: null, railed: false },
	{ name: 'between small and middle', width: 801, tracks: 2, trailing: null, railed: true },
	{
		name: 'between middle and wide',
		width: 1280,
		tracks: 3,
		trailing: '--zone-rail',
		railed: true
	},
	{
		name: 'at and above wide',
		width: 1536,
		tracks: LEADS > 0 ? 2 : 3,
		trailing: LEADS > 0 ? null : '--zone-rail',
		railed: true
	}
] as const;

/** The two root font sizes every assertion runs at, and what the second must do
 * to the first. Not a browser zoom: zoom scales the CSS pixel itself, so a
 * `px` zone would move too and the check would pass on a layout that ignores
 * the reader's font size entirely. */
const ROOT_PX = [16, 22] as const;
const SCALE = 22 / 16;

interface Reading {
	rootFontPx: number;
	remPx: number;
	zoneMark: number;
	zoneRail: number;
	zoneAside: number;
	/** The rail's own track, or null below the small breakpoint where the stream
	 * is not a grid and the marker is a rule across the top of its group. */
	zoneTime: number | null;
	frameUsed: number;
	frameContentBox: number;
	itemTracks: number[];
	itemUsed: number;
	proseUsed: number;
	proseMaxWidth: number;
	asideUsed: number | null;
	railUsed: number | null;
	/** The whole leading column of the stream, gap included, so the fill check
	 * below compares like with like. */
	timeColumn: number | null;
	scrollWidth: number;
	clientWidth: number;
}

async function read(page: Page, rootPx: number): Promise<Reading> {
	await page.evaluate((px) => {
		document.documentElement.style.fontSize = `${px}px`;
	}, rootPx);
	// Two frames between the write and the read. A rect taken in the same task
	// as the style write comes back stale, and the check then compares a layout
	// against itself and passes for free.
	await page.evaluate(
		() => new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done)))
	);

	return page.evaluate(() => {
		const root = getComputedStyle(document.documentElement);
		const remPx = parseFloat(root.fontSize);
		const zone = (name: string) => parseFloat(root.getPropertyValue(name)) * remPx;
		const width = (el: Element | null) =>
			el ? Math.round(el.getBoundingClientRect().width * 100) / 100 : null;

		const frame = document.querySelector('.frame') as HTMLElement;
		const framePad =
			parseFloat(getComputedStyle(frame).paddingLeft) +
			parseFloat(getComputedStyle(frame).paddingRight);
		const item = document.querySelector('article.item') as HTMLElement;
		const prose = document.querySelector('[data-item-summary]') as HTMLElement;
		const stream = document.querySelector('[data-time-rail]');
		const streamStyle = stream ? getComputedStyle(stream) : null;
		// Below the small breakpoint the stream is not a grid at all, so there is
		// no leading track to read and the marker is a rule across the group.
		const railed = streamStyle?.display === 'grid';
		const railTrack = railed
			? parseFloat((streamStyle as CSSStyleDeclaration).gridTemplateColumns.split(' ')[0] as string)
			: null;

		return {
			rootFontPx: remPx,
			remPx,
			zoneMark: zone('--zone-mark'),
			zoneRail: zone('--zone-rail'),
			zoneAside: zone('--zone-aside'),
			zoneTime: railTrack,
			frameUsed: width(frame) as number,
			frameContentBox: Math.round((frame.getBoundingClientRect().width - framePad) * 100) / 100,
			itemTracks: getComputedStyle(item)
				.gridTemplateColumns.split(' ')
				.map((track) => parseFloat(track)),
			itemUsed: width(item) as number,
			proseUsed: width(prose) as number,
			proseMaxWidth: parseFloat(getComputedStyle(prose).maxWidth),
			asideUsed: width(document.querySelector('.day-aside')),
			railUsed: width(document.querySelector('.item .item-rail')),
			timeColumn:
				railTrack === null
					? null
					: Math.round(
							(railTrack + parseFloat((streamStyle as CSSStyleDeclaration).columnGap)) * 100
						) / 100,
			scrollWidth: document.documentElement.scrollWidth,
			clientWidth: document.documentElement.clientWidth
		};
	});
}

test.describe('the reading page spends its width in named zones', () => {
	for (const band of BANDS) {
		test(`${band.name} (${band.width}px): the zone model, at two root font sizes`, async ({
			page
		}) => {
			const seen: Reading[] = [];

			for (const rootPx of ROOT_PX) {
				await page.setViewportSize({ width: band.width, height: 900 });
				await page.goto('/');
				const reading = await read(page, rootPx);
				seen.push(reading);

				expect(
					reading.rootFontPx,
					'the root font size did not take, so nothing below is about a rem'
				).toBeCloseTo(rootPx, 1);

				// --- The shape --------------------------------------------------
				expect(
					reading.itemTracks.length,
					`at ${band.width}px the item should be ${band.tracks} tracks, ` +
						`and it is ${reading.itemTracks.join(' + ')}`
				).toBe(band.tracks);

				// The mark leads at every width, and it is the token rather than a
				// consequence of whatever the monogram happens to measure.
				expect(reading.itemTracks[0], 'the leading track is --zone-mark').toBeCloseTo(
					reading.zoneMark,
					1
				);

				if (band.trailing) {
					expect(
						reading.itemTracks[reading.itemTracks.length - 1],
						'the trailing track is --zone-rail'
					).toBeCloseTo(reading.zoneRail, 1);
				}

				// --- The measure is on the text, never on the shell -------------
				expect(
					reading.proseUsed,
					`the summary is ${reading.proseUsed}px against a measure of ${reading.proseMaxWidth}px`
				).toBeLessThanOrEqual(reading.proseMaxWidth + 0.5);

				// --- The page uses the box it has -------------------------------
				// From the small breakpoint the day's time rail takes a leading
				// column off the content box, and at and above the wide one the aside
				// takes a trailing one. So what has to fill the box is every zone
				// together, which is the honest form of the check. Below the small
				// breakpoint there is no rail column - a 328px content box cannot hold
				// one and a readable line - and the item is the whole box again.
				expect(
					reading.zoneTime !== null,
					band.railed
						? `at ${band.width}px the stream should draw a time rail column`
						: `at ${band.width}px the stream should have no time rail column`
				).toBe(band.railed);
				const timeColumn = reading.timeColumn ?? 0;
				if (band.width >= 1400 && LEADS > 0) {
					expect(reading.asideUsed, 'the day grows an aside at the wide breakpoint').toBeCloseTo(
						reading.zoneAside,
						1
					);
					expect(
						(reading.itemUsed + timeColumn + (reading.asideUsed as number)) /
							reading.frameContentBox,
						'the rail, the stream and the aside together fill the frame'
					).toBeGreaterThan(0.9);
				} else {
					expect(reading.asideUsed, 'the aside is a wide-breakpoint zone only').toBeNull();
					expect(
						(reading.itemUsed + timeColumn) / reading.frameContentBox,
						'the rail and the stream together fill the frame'
					).toBeGreaterThan(0.9);
				}

				// A zone that spends width it does not have is a sideways scroll.
				expect(reading.scrollWidth, `${band.width}px at ${rootPx}px root scrolls sideways`).toBeLessThanOrEqual(
					reading.clientWidth
				);
			}

			// --- No zone is a pixel count -----------------------------------
			const [small, large] = seen;
			const moved: Record<string, [number, number]> = {
				'--zone-mark': [small.itemTracks[0], large.itemTracks[0]]
			};
			if (band.railed) {
				moved['--zone-time'] = [small.zoneTime as number, large.zoneTime as number];
			}
			if (band.trailing) {
				moved['--zone-rail'] = [
					small.itemTracks[small.itemTracks.length - 1],
					large.itemTracks[large.itemTracks.length - 1]
				];
			}
			if (band.width >= 1400 && LEADS > 0) {
				moved['--zone-aside'] = [small.asideUsed as number, large.asideUsed as number];
			}

			for (const [name, [before, after]] of Object.entries(moved)) {
				expect(
					after / before,
					`${name} was ${before}px at a 16px root and ${after}px at 22px. ` +
						`A rem zone scales by ${SCALE}; a pixel count does not move at all.`
				).toBeCloseTo(SCALE, 2);
			}
		});
	}

	test('the aside is a zone beside the stream, and the day controls keep the frame', async ({
		page
	}) => {
		// The canary day publishes one desk, and a block that allows two stories
		// a desk needs three to draw - so this fixture earns no leading block and
		// the aside has no call site on it. The zone model is CSS rather than
		// markup, so it is driven here against the stylesheet the build actually
		// shipped: the skeleton below is the shape `DigestList` emits, dropped
		// into the real frame on a real page, and every rule that reaches it is
		// the one a reader gets. Skipping instead would leave the widest layout
		// this row draws with no check at all.
		const skeleton = `
			<div class="day">
				<div class="day-head"><section data-filter-bar>controls</section></div>
				<div class="day-aside"><section data-leading>leads</section></div>
				<div class="day-head"></div>
				<div class="day-stream"><p>stories</p></div>
			</div>`;

		async function frameAt(width: number, rootPx: number) {
			await page.setViewportSize({ width, height: 900 });
			await page.goto('/');
			return page.evaluate(
				({ markup, px }) => {
					document.documentElement.style.fontSize = `${px}px`;
					const main = document.querySelector('main') as HTMLElement;
					main.innerHTML = markup;
					const box = (selector: string) => {
						const el = document.querySelector(selector);
						return el ? el.getBoundingClientRect() : null;
					};
					const root = getComputedStyle(document.documentElement);
					const rem = parseFloat(root.fontSize);
					const frame = document.querySelector('.frame') as HTMLElement;
					const style = getComputedStyle(frame);
					return {
						remPx: rem,
						zoneAside: parseFloat(root.getPropertyValue('--zone-aside')) * rem,
						frameContentBox:
							frame.getBoundingClientRect().width -
							parseFloat(style.paddingLeft) -
							parseFloat(style.paddingRight),
						aside: box('.day-aside'),
						stream: box('.day-stream'),
						head: box('.day-head')
					};
				},
				{ markup: skeleton, px: rootPx }
			);
		}

		const wide = await frameAt(1536, 16);
		const asideBox = wide.aside as DOMRect;
		const streamBox = wide.stream as DOMRect;
		const headBox = wide.head as DOMRect;

		expect(asideBox.width, 'the aside is exactly --zone-aside').toBeCloseTo(wide.zoneAside, 1);
		expect(asideBox.left, 'the aside stands beside the stream').toBeGreaterThanOrEqual(
			streamBox.right - 1
		);
		expect(asideBox.top, 'the aside starts level with the stream').toBeCloseTo(streamBox.top, 0);
		// The day's controls keep the whole content box. A control that follows
		// the reader down the page has to be one band, and at the width a
		// two-column split leaves, the filter panel's pills wrap under its field.
		expect(headBox.width, 'the day controls span both columns').toBeCloseTo(
			wide.frameContentBox,
			0
		);
		expect(
			(streamBox.width + asideBox.width) / wide.frameContentBox,
			'the stream and the aside together fill the frame'
		).toBeGreaterThan(0.9);

		// The same zone at a larger root font size, because a zone that does not
		// move is a pixel count wearing a token's name.
		const larger = await frameAt(1536, 22);
		expect(
			(larger.aside as DOMRect).width / asideBox.width,
			`the aside was ${asideBox.width}px at a 16px root and ` +
				`${(larger.aside as DOMRect).width}px at 22px`
		).toBeCloseTo(SCALE, 2);

		// And below the wide breakpoint there is no second column at all: the
		// leads draw above the stream, where `digest.sections` puts them.
		const narrow = await frameAt(1280, 16);
		expect(
			(narrow.aside as DOMRect).width,
			'the aside is a wide-breakpoint zone and stacks below it'
		).toBeCloseTo(narrow.frameContentBox, 0);
	});
});
