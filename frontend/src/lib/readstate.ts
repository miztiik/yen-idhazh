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
 */

const KEY = 'idhazh:read';

function available(): boolean {
	try {
		return typeof localStorage !== 'undefined';
	} catch {
		return false;
	}
}

export function loadRead(): Set<string> {
	if (!available()) return new Set();
	try {
		const raw = localStorage.getItem(KEY);
		return new Set(raw ? (JSON.parse(raw) as string[]) : []);
	} catch {
		return new Set();
	}
}

export function markRead(itemId: string, current: Set<string>): Set<string> {
	const next = new Set(current);
	next.add(itemId);
	persist(next);
	return next;
}

export function forgetAll(): Set<string> {
	if (available()) {
		try {
			localStorage.removeItem(KEY);
		} catch {
			/* storage refused; the page still renders */
		}
	}
	return new Set();
}

function persist(items: Set<string>): void {
	if (!available()) return;
	try {
		localStorage.setItem(KEY, JSON.stringify([...items]));
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
