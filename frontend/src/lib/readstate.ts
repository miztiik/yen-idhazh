/** What this reader has already read.
 *
 * `localStorage` only, never a cookie: a cookie is sent on every request, which
 * would put a reading history into the host's access logs. This never leaves
 * the device.
 *
 * The hard rule, and it is the one worth protecting: read-state may change how
 * an item LOOKS and may never change where it sits, whether it appears, or how
 * it ranks. The moment it does, two people at the same URL see different pages
 * and a shared link stops showing the recipient what the sender saw.
 *
 * Marks are held per digest date. One flat list of ids could not say which day
 * a mark was made on, so an id that came round again greyed out an article the
 * reader had never opened, and the list grew for ever. A date is the only thing
 * that makes a mark answerable, and it is what lets an old one be dropped.
 *
 * **One storage key per date, not one key holding every date.** A click then
 * writes the day the reader is on and nothing else, so marking a story costs
 * that day's own marks rather than everything the reader has ever read. Under
 * the single key every click re-read, re-parsed, re-spread and re-serialised
 * the whole history.
 *
 * **A mark expires by the calendar, not by position.** `ui.read_mark_days`
 * counts back from today, so a date the window no longer reaches goes on the
 * next load. That needs the device clock, which the rule it replaced
 * deliberately did not: keeping the newest N dates the store happened to hold
 * bounded it by how often a reader came back rather than by how long ago they
 * read, so a reader who opened one day a month kept marks from seven different
 * months. The price is stated rather than hidden - a clock set wrong keeps a
 * mark too long or drops it early - and one more thing follows from it: a mark
 * made on an archive day the window no longer reaches does not survive the next
 * load. The window is the promise, and it is the same span the archive lists as
 * rows of its own.
 */

/** One key a date: `idhazh:read:2026-08-23` -> `["ai-0417291083", ...]`. */
const PREFIX = 'idhazh:read:';

/** The one key every mark used to live under. It held `{ "2026-08-23": [...] }`,
 * and before that a bare array of ids with no date at all. Read once, then gone. */
const LEGACY_KEY = 'idhazh:read';

function available(): boolean {
	try {
		return typeof localStorage !== 'undefined';
	} catch {
		return false;
	}
}

function dayKey(date: string): string {
	return `${PREFIX}${date}`;
}

/** Every date the store holds marks for.
 *
 * Key names only - no value is parsed - so this costs the number of days held
 * and not the number of marks. The window bounds that number: after one pass of
 * `prune` the store holds at most `keepDays` of them.
 */
function storedDates(): string[] {
	const dates: string[] = [];
	try {
		for (let index = 0; index < localStorage.length; index += 1) {
			const key = localStorage.key(index);
			if (key !== null && key.startsWith(PREFIX)) dates.push(key.slice(PREFIX.length));
		}
	} catch {
		return [];
	}
	return dates;
}

/** The ids filed under one date, and nothing else read. */
function idsFor(date: string): string[] {
	try {
		const raw = localStorage.getItem(dayKey(date));
		if (!raw) return [];
		const parsed: unknown = JSON.parse(raw);
		if (!Array.isArray(parsed)) return [];
		return parsed.filter((id): id is string => typeof id === 'string');
	} catch {
		return [];
	}
}

function write(date: string, ids: readonly string[]): void {
	try {
		if (ids.length === 0) localStorage.removeItem(dayKey(date));
		else localStorage.setItem(dayKey(date), JSON.stringify(ids));
	} catch {
		/* quota or private mode; read-state is a convenience, not a requirement */
	}
}

/** The oldest digest date the window still reaches.
 *
 * Both sides are `YYYY-MM-DD`, which sorts as a date, and both are UTC because
 * the pipeline stamps a published day in UTC. `keepDays` counts today, so
 * fourteen days means today and the thirteen before it.
 */
function windowFloor(keepDays: number, now: Date): string {
	const days = Math.max(1, Math.trunc(keepDays));
	const floor = new Date(
		Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() - (days - 1))
	);
	return floor.toISOString().slice(0, 10);
}

/** Fold the single-key store into one key a date, then forget it.
 *
 * The dated map is carried over, because it holds marks a reader really made.
 * The bare array that came before it is not: nothing in it says which day an id
 * belonged to, and a wrong mark costs a reader an article where a lost one
 * costs them a click.
 */
function migrate(): void {
	let raw: string | null;
	try {
		raw = localStorage.getItem(LEGACY_KEY);
	} catch {
		return;
	}
	if (raw === null) return;
	try {
		const parsed: unknown = JSON.parse(raw);
		if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
			for (const [date, ids] of Object.entries(parsed as Record<string, unknown>)) {
				// A day already held under its own key was written later than this one.
				if (!Array.isArray(ids) || localStorage.getItem(dayKey(date)) !== null) continue;
				write(
					date,
					ids.filter((id): id is string => typeof id === 'string')
				);
			}
		}
	} catch {
		/* unreadable, so it goes the way the shape with no dates on it goes */
	}
	try {
		localStorage.removeItem(LEGACY_KEY);
	} catch {
		/* private mode; nothing here depends on it going away */
	}
}

/** Drop every date the window no longer reaches.
 *
 * Only a date OLDER than the floor goes. A date the clock has not reached yet
 * is kept, so a device clock running behind loses a reader nothing.
 */
function prune(keepDays: number, now: Date): void {
	const floor = windowFloor(keepDays, now);
	for (const date of storedDates()) {
		if (date >= floor) continue;
		try {
			localStorage.removeItem(dayKey(date));
		} catch {
			/* the next load tries again */
		}
	}
}

/** What this reader has read on this one day. Prunes the store as a side effect. */
export function loadRead(date: string, keepDays: number): Set<string> {
	if (!available()) return new Set();
	migrate();
	prune(keepDays, new Date());
	return new Set(idsFor(date));
}

export function markRead(itemId: string, current: Set<string>, date: string): Set<string> {
	const next = new Set(current);
	next.add(itemId);
	if (available()) write(date, [...next]);
	return next;
}

/** Forget this day only. The button sits on a day page and says what it does. */
export function forgetAll(date: string): Set<string> {
	if (available()) write(date, []);
	return new Set();
}

const HIDE_KEY = 'idhazh:hide-read';

export function loadHideRead(): boolean {
	if (!available()) return false;
	try {
		return localStorage.getItem(HIDE_KEY) === '1';
	} catch {
		return false;
	}
}

export function setHideRead(on: boolean): void {
	if (!available()) return;
	try {
		if (on) localStorage.setItem(HIDE_KEY, '1');
		else localStorage.removeItem(HIDE_KEY);
	} catch {
		/* same as above */
	}
}
