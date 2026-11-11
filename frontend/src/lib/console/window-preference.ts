/** Keep a console window in memory even when optional browser storage fails. */

export const WINDOW_PREFERENCE_KEY = 'idhazh:console-window';

export interface WindowStorage {
	getItem(key: string): string | null;
	setItem(key: string, value: string): void;
}

export interface WindowChoice {
	readonly days: number;
	select(days: number): void;
}

export function createWindowPreference(
	initial: number,
	presets: readonly number[],
	changed: (days: number) => void,
	warn: (message: string, cause: unknown) => void = console.warn
): WindowChoice & { mount(storage: () => WindowStorage): void } {
	if (!presets.includes(initial)) throw new Error('The initial window must be a configured preset.');
	let days = initial;
	let storage: (() => WindowStorage) | null = null;
	function select(next: number): void {
		if (!presets.includes(next)) throw new Error('The window must be a configured preset.');
		days = next;
		changed(next);
		if (storage === null) return;
		try {
			storage().setItem(WINDOW_PREFERENCE_KEY, String(next));
		} catch (cause) {
			warn('[console] Window preference could not be saved; the selected window remains active.', cause);
		}
	}
	return {
		get days() { return days; },
		select,
		mount(open) {
			storage = open;
			let stored: string | null;
			try {
				stored = open().getItem(WINDOW_PREFERENCE_KEY);
			} catch (cause) {
				warn('[console] Window preference could not be read; keeping the in-memory window.', cause);
				return;
			}
			if (stored === null) return;
			const next = Number(stored);
			if (!presets.includes(next) || String(next) !== stored) {
				warn('[console] Stored window is not a configured preset; keeping the in-memory window.', null);
				return;
			}
			days = next;
			changed(next);
		}
	};
}
