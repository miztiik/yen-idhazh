/** A day payload, fetched from the published site rather than inlined.
 *
 * The archive used to carry every committed day whole so a search result could
 * be rendered from one. That cost every visitor 1.7 MB gzipped to browse a
 * list. A result now names a day, and the day is fetched only when a result
 * from it is on screen. From 2026-09-01 this is also the loader a reading page
 * uses for the stories past its seed, so it is the one place in the browser
 * that reads a day.
 *
 * **Fetched once per page.** Ten results spanning ten days cost ten requests at
 * worst; ten results from one day cost one. A day already in hand is never
 * fetched again, and a day that failed is not retried on its own - a second
 * automatic attempt at a file the host does not have costs a reader a request
 * and tells them nothing. A reader who presses the retry control asks for one,
 * and `again` is how they get it.
 *
 * **Null is the designed state.** A result whose day cannot be read still
 * renders: it keeps the title, the date and the topic the index carried, and
 * loses the summary. The page never waits on this and never breaks on it.
 */

import { base } from '$app/paths';
import type { DigestDay, DigestItem } from '$lib/payload/types';

const days = new Map<string, Promise<DigestDay | null>>();

/** A published date, and nothing else. Three parts split on a dash is not the
 * same test: `not-a-date` splits into three truthy parts and would have become
 * `digest/not/a/date/digest.json` - a path built out of whatever arrived, which
 * is the shape of mistake Rule #11 is about. A date reaching here comes from a
 * route parameter or a search index entry, so it is checked rather than
 * trusted. */
const PUBLISHED_DATE = /^(\d{4})-(\d{2})-(\d{2})$/;

/** Where a day is served from. Absolute from `base`, never relative.
 *
 * Two ways a hand-built path goes wrong here, and both of them pass in
 * development. `trailingSlash: 'always'` puts every reading route on a
 * directory of its own, so one relative path resolves somewhere different on
 * `/2026-08-30/` than on `/2026-08-30/ai/`. And GitHub Pages serves this site
 * under a project path, so a path that skips `base` is right on a developer
 * machine and a 404 for every reader. One function builds every URL this module
 * asks for, which is what leaves one place for that to be right.
 *
 * Null for a date this cannot read - the same designed null the rest of the
 * module returns, rather than a thrown error.
 */
export function dayUrl(date: string, root: string = base): string | null {
	const parts = PUBLISHED_DATE.exec(date);
	if (parts === null) return null;
	const [, year, month, day] = parts;
	return `${root}/digest/${year}/${month}/${day}/digest.json`;
}

/** The day published on that date, or null when it cannot be read. */
export function loadDay(date: string, fetcher: typeof fetch = fetch): Promise<DigestDay | null> {
	const held = days.get(date);
	if (held) return held;
	const pending = readDay(date, fetcher);
	days.set(date, pending);
	return pending;
}

/** Whether a story carries everything the page reads off it without a guard.
 *
 * **This is the boundary the build stopped covering.** Every story used to be
 * serialised into a document, so a story that failed its contract failed the
 * build. A reading document carries a seed now and these arrive by fetch, so
 * the only check between a malformed story and a reader is this one.
 *
 * Four names, and each is here because something dereferences it directly:
 * `item_id` is the element id a deep link and the leading block both aim at,
 * and `title`, `summary` and `key_points` are what the in-page filter reads on
 * every keystroke. A story missing `key_points` renders and then throws a
 * `TypeError` the first time a reader types - a page that broke on an action
 * rather than on arrival, which is the worst shape this failure has.
 *
 * It is deliberately not a schema. A browser validating twenty-three fields
 * would need a validator on the reading path (Rule #1, Rule #8), and the
 * contract is checked where it can be checked properly: `idhazh validate-days`
 * opens every story of every committed day in CI and before every publish.
 */
function renderable(item: DigestItem): boolean {
	return (
		typeof item?.item_id === 'string' &&
		item.item_id !== '' &&
		typeof item.title === 'string' &&
		typeof item.summary === 'string' &&
		Array.isArray(item.key_points)
	);
}

async function readDay(date: string, fetcher: typeof fetch): Promise<DigestDay | null> {
	const url = dayUrl(date);
	if (url === null) return null;
	try {
		const response = await fetcher(url);
		if (!response.ok) {
			console.warn(`[digest] the stories of ${date} are not available (${response.status})`);
			return null;
		}
		const payload = (await response.json()) as DigestDay;
		if (!Array.isArray(payload?.items)) return null;
		// Degrade, do not fail (`CLAUDE.md` section 1a). One story the page cannot
		// render must not cost a reader the other three hundred, so it is dropped
		// and counted. The console is the whole logging surface (section 1b), so
		// the count goes there - a reader can hand it back, and nothing they could
		// do would fix it.
		const items = payload.items.filter(renderable);
		if (items.length !== payload.items.length) {
			console.warn(
				`[digest] ${date}: ${payload.items.length - items.length} of ${payload.items.length} ` +
					'stories are not readable and were dropped'
			);
		}
		return { ...payload, items };
	} catch (error) {
		console.warn(`[digest] the stories of ${date} could not be read`, error);
		return null;
	}
}

/** How a page's wait is going. Four states, and the last is the new one.
 *
 * `unreachable` covers every way a fetch can fail, a 404 included, and that is
 * not a shortcut. A reading route exists only for a day that published, so a
 * payload the host will not serve is a day that went missing after publication
 * - never a day that was never published. **Missing is decided at build time
 * and Unreachable in the browser**, so neither has to guess which it is, and a
 * reader whose train went into a tunnel is never told the day does not exist.
 */
export type DayStatus = 'loading' | 'slow' | 'ready' | 'unreachable';

export interface DayWatch {
	/** Told on every change, so the page holds no timer of its own. */
	onStatus: (status: DayStatus, day: DigestDay | null) => void;
	/** How long the wait may last before it is worth one sentence. It comes from
	 * `ui.payload_slow_ms` and is never a number written here (Rule #6). */
	slowMs: number;
	/** Forget a held answer first. This is what a retry control calls, and it is
	 * the only way a day that failed is fetched a second time. */
	again?: boolean;
	fetcher?: typeof fetch;
}

/** The day, with the wait reported as it happens.
 *
 * There is no spinner and no bar. The frame a reader already has is readable,
 * so there is nothing to fill, and past `slowMs` the page says one sentence. A
 * byte readout was weighed and refused: the response is compressed, so its
 * length is the compressed length, and a bar built on that prints precision the
 * number does not carry.
 */
export function watchDay(date: string, watch: DayWatch): Promise<DigestDay | null> {
	if (watch.again) days.delete(date);
	let settled = false;
	watch.onStatus('loading', null);
	const slow = setTimeout(() => {
		if (!settled) watch.onStatus('slow', null);
	}, watch.slowMs);
	return loadDay(date, watch.fetcher).then((day) => {
		settled = true;
		clearTimeout(slow);
		watch.onStatus(day === null ? 'unreachable' : 'ready', day);
		return day;
	});
}

/** Take the reader to the story their link named, once it is on the page.
 *
 * A browser honours a fragment at the moment the document loads and never
 * again. That was free while every story sat in the document; it stops being
 * free the moment the stories past the seed arrive by fetch, because the
 * element the link names does not exist yet when the browser looks for it. So
 * the shell calls this on arrival, and a page that fetches calls it again once
 * its stories have rendered.
 *
 * It focuses as well as scrolls. A story is not a focusable element, so a
 * reader following a deep link with a keyboard would otherwise land at the top
 * of the document and have to tab back down to what they were sent to read.
 *
 * The id goes to `getElementById`, which takes a literal id and not a selector,
 * so a fragment a reader was handed cannot become a query (Rule #11).
 *
 * True when it found the element, so a caller can tell "no such story here"
 * from "no fragment at all".
 */
export function restoreAnchor(hash?: string): boolean {
	if (typeof document === 'undefined') return false;
	const id = (hash ?? window.location.hash).replace(/^#/, '');
	if (id === '') return false;
	const target = document.getElementById(id);
	if (target === null) return false;
	if (!target.hasAttribute('tabindex')) target.setAttribute('tabindex', '-1');
	target.scrollIntoView();
	target.focus({ preventScroll: true });
	return true;
}

/** One item out of a day already in hand, or null. */
export function itemOf(day: DigestDay | null, itemId: string): DigestItem | null {
	return day?.items.find((item) => item.item_id === itemId) ?? null;
}
