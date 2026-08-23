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
 */

const KEY = 'idhazh:read';

/** `{ "2026-08-23": ["a1b2", ...] }`. A bare array is the old shape. */
type Marks = Record<string, string[]>;

function available(): boolean {
	try {
		return typeof localStorage !== 'undefined';
	} catch {
		return false;
	}
}

/** Read the store, migrating or discarding anything that is not today's shape.
 *
 * The old shape was a bare array of ids with no date. There is no honest way to
 * decide which day those belonged to, so it is dropped rather than guessed at -
 * a wrong mark costs a reader an article, and a lost mark costs them a click.
 */
function read(): Marks {
	if (!available()) return {};
	try {
		const raw = localStorage.getItem(KEY);
		if (!raw) return {};
		const parsed: unknown = JSON.parse(raw);
		if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return {};
		const marks: Marks = {};
		for (const [date, ids] of Object.entries(parsed as Record<string, unknown>)) {
			if (Array.isArray(ids)) marks[date] = ids.filter((id): id is string => typeof id === 'string');
		}
		return marks;
	} catch {
		return {};
	}
}

/** Drop every day outside the window, newest first. Dates sort as strings. */
function prune(marks: Marks, keepDays: number): Marks {
	const keep = Object.keys(marks)
		.sort()
		.reverse()
		.slice(0, Math.max(keepDays, 1));
	return Object.fromEntries(keep.map((date) => [date, marks[date]]));
}

/** What this reader has read on this one day. Prunes the store as a side effect. */
export function loadRead(date: string, keepDays: number): Set<string> {
	const marks = prune(read(), keepDays);
	persist(marks);
	return new Set(marks[date] ?? []);
}

export function markRead(itemId: string, current: Set<string>, date: string): Set<string> {
	const next = new Set(current);
	next.add(itemId);
	persist({ ...read(), [date]: [...next] });
	return next;
}

/** Forget this day only. The button sits on a day page and says what it does. */
export function forgetAll(date: string): Set<string> {
	const marks = read();
	delete marks[date];
	persist(marks);
	return new Set();
}

function persist(marks: Marks): void {
	if (!available()) return;
	try {
		if (Object.keys(marks).length === 0) localStorage.removeItem(KEY);
		else localStorage.setItem(KEY, JSON.stringify(marks));
	} catch {
		/* quota or private mode; read-state is a convenience, not a requirement */
	}
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
