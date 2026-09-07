/** A day payload, fetched from the published site rather than inlined.
 *
 * The archive used to carry every committed day whole so a search result could
 * be rendered from one. That cost every visitor 1.7 MB gzipped to browse a
 * list. A result now names a day, and the day is fetched only when a result
 * from it is on screen. From 2026-09-01 this is also the loader a reading page
 * uses for the stories past its seed, so it is the one place in the browser
 * that reads a day.
 *
 * **Fetched once per ask, and shared.** Ten results spanning ten days cost ten
 * requests at worst; ten results from one day cost one, and two callers that
 * ask while the request is in flight get that one request rather than two.
 *
 * **A failure is not an answer, so it is not held.** Until 2026-09-06 a fetch
 * that failed left a null in the held set and every later ask for that date got
 * the null back, so one flaky connection finished that day for the rest of the
 * session. The archive is where that bit: it fetches the day behind every
 * search result and has no retry control at all. The next ask now really asks,
 * and it is still one request per ask rather than one per render, because
 * nothing on a render path asks.
 *
 * **Null is the designed state.** A result whose day cannot be read still
 * renders: it keeps the title, the date and the topic the index carried, and
 * loses the summary. The page never waits on this and never breaks on it.
 */

import { base } from '$app/paths';
import type { DigestDay, DigestItem } from '$lib/payload/types';

/** One date this session has asked for.
 *
 * `revision` is the payload's own `generated_at`, which is what a republish
 * moves and nothing else does. It is null while the request is in flight and
 * for a payload that declares no revision, and both mean the same thing: this
 * day may not be reused for one the host is serving now.
 */
interface HeldDay {
	revision: string | null;
	payload: DigestDay | null;
	day: Promise<DigestDay | null>;
}

/** How many days one session keeps in hand.
 *
 * A reading route needs one - the day it is drawing. The archive needs a whole
 * answer at once: it fetches the day behind every result on screen, and
 * `assist.result_limit` is 10, so one search can put ten distinct dates in
 * flight together. Twelve is that answer, plus the day the reader arrived from,
 * plus one spare.
 *
 * **It is a count and not a byte ceiling, because a browser cannot measure a
 * parsed payload.** What a count costs is measurable off the tree: over the 17
 * committed days on 2026-09-06 a served day is 11,547 bytes of JSON at its
 * smallest, 1,066,895 at the median and 1,924,051 at its largest, so twelve of
 * them is about 12.8 MB of text at the median and 23.1 MB at the worst, and
 * more once parsed. Uncapped there was no worst: this map only ever grew, so a
 * session that ran five searches over fifty distinct days held all fifty for as
 * long as the tab was open.
 *
 * **Dropping one costs a request and never a story.** A page that drew a day
 * holds its own reference to it, so eviction only means the next ask for that
 * date fetches again.
 */
const HELD_DAYS = 12;

const days = new Map<string, HeldDay>();

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
	return requestDay(date, fetcher, false);
}

/** One ask for a date, answered from what the session holds or from the host.
 *
 * `again` is the reader pressing the retry control. It goes back to the host
 * whatever this session holds, because the reader is asking about the host and
 * not about this session.
 */
function requestDay(
	date: string,
	fetcher: typeof fetch,
	again: boolean
): Promise<DigestDay | null> {
	const held = days.get(date);
	if (held !== undefined && !again) {
		// Asked-for-last is held-longest, so the cap drops the day this session
		// has come back to least recently rather than the one it met first.
		days.delete(date);
		days.set(date, held);
		return held.day;
	}
	if (held !== undefined) days.delete(date);
	return fetchDay(date, fetcher, held ?? null);
}

function fetchDay(
	date: string,
	fetcher: typeof fetch,
	previous: HeldDay | null
): Promise<DigestDay | null> {
	// The record exists before the request settles, because the settling has to
	// know whether it is still the request this date is holding. An `again` or an
	// eviction between the two replaces it, and a late arrival may not overwrite
	// what took its place.
	const entry: HeldDay = { revision: null, payload: null, day: Promise.resolve(null) };
	entry.day = readDay(date, fetcher).then((fresh) => settle(date, entry, previous, fresh));
	hold(date, entry);
	return entry.day;
}

function settle(
	date: string,
	entry: HeldDay,
	previous: HeldDay | null,
	fresh: DigestDay | null
): DigestDay | null {
	const ours = days.get(date) === entry;
	if (fresh === null) {
		// A day that could not be read is not an answer, so nothing holds one.
		if (ours) days.delete(date);
		return null;
	}
	// The revision is the key. A day that came back unchanged is the day the page
	// already holds, so it is handed back as the same value and every index built
	// on it survives; a day that came back at another revision, or at none this
	// can read, replaces it.
	const revision = typeof fresh.generated_at === 'string' && fresh.generated_at !== ''
		? fresh.generated_at
		: null;
	const unchanged =
		revision !== null && previous !== null && previous.payload !== null
			? previous.revision === revision
			: false;
	const day = unchanged && previous?.payload ? previous.payload : fresh;
	if (ours) {
		entry.revision = revision;
		entry.payload = day;
	}
	return day;
}

/** Newest ask last, oldest ask first, and never more than the cap. */
function hold(date: string, entry: HeldDay): void {
	days.delete(date);
	days.set(date, entry);
	for (const oldest of days.keys()) {
		if (days.size <= HELD_DAYS) break;
		days.delete(oldest);
	}
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
	/** Go back to the host about a day this session already holds. This is what
	 * the retry control calls. A failed day is no longer held, so a plain ask
	 * already reaches the host; what this adds is asking about a day the session
	 * has an answer for - and the answer is kept when the revision comes back
	 * unchanged. */
	again?: boolean;
	fetcher?: typeof fetch;
	/** Stop telling this watcher anything once it aborts. The shared request is
	 * never cancelled - another caller may be waiting on the same one, and the
	 * day-cache still fills for the next ask - but a status past the abort is a
	 * status about a day this watcher no longer wants. A reading page whose date
	 * changed while a watch was in flight aborts the old one here, so the old
	 * day cannot arrive on the new page. */
	signal?: AbortSignal;
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
	const { signal } = watch;
	let settled = false;
	// Every status goes through here, so an aborted watch is told nothing - not
	// the slow note, not the final one. The request itself runs on, because the
	// day-cache and any other caller waiting on it still want the answer.
	const report = (status: DayStatus, day: DigestDay | null) => {
		if (signal?.aborted !== true) watch.onStatus(status, day);
	};
	report('loading', null);
	const slow = setTimeout(() => {
		if (!settled) report('slow', null);
	}, watch.slowMs);
	const stop = () => {
		settled = true;
		clearTimeout(slow);
	};
	signal?.addEventListener('abort', stop, { once: true });
	return requestDay(date, watch.fetcher ?? fetch, watch.again === true).then((day) => {
		stop();
		signal?.removeEventListener('abort', stop);
		report(day === null ? 'unreachable' : 'ready', day);
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

/** One lookup index per day, built the first time anything asks that day a
 * question and shared by everything that asks it another.
 *
 * **The key is the payload itself, and that is what makes it revision-owned.**
 * A fetch that finds a republished day hands back a different object, so an
 * index can never answer for a payload it was not built from; a fetch that
 * finds the day unchanged hands back the same object, so the index survives.
 * Keying on the date string would do neither. Weak, so an index is collected
 * with the day it describes and holds nothing open.
 */
const lookups = new WeakMap<DigestDay, Map<string, DigestItem>>();

/** One item out of a day already in hand, or null.
 *
 * A search result names a day and a story, and the archive resolves one of
 * these per result on screen and again every time a day arrives. Walking the
 * day for each of them costs the day's whole length per lookup - 731 stories on
 * the heaviest committed day - for an answer the day could hold once.
 *
 * Both fallbacks are unchanged and both are designed states: a day that could
 * not be read is null, and a story the day does not hold is null.
 */
export function itemOf(day: DigestDay | null, itemId: string): DigestItem | null {
	if (!day) return null;
	let byId = lookups.get(day);
	if (byId === undefined) {
		byId = new Map(day.items.map((item) => [item.item_id, item]));
		lookups.set(day, byId);
	}
	return byId.get(itemId) ?? null;
}
