/** Track the current UTC day of a mounted reading page, including midnight and resume. */

/** Browser clock, timer and lifecycle boundaries, also usable without a browser. */
export interface UtcDayRuntime {
	now(): number;
	schedule(run: () => void, delayMs: number): () => void;
	page: EventTarget;
	document: EventTarget;
}

/** One timer per reading page; a resumed page reads the clock rather than adding a day. */
export function trackUtcDay(
	show: (date: string) => void,
	runtime: UtcDayRuntime = {
		now: () => Date.now(),
		schedule(run, delayMs) {
			const timer = window.setTimeout(run, delayMs);
			return () => window.clearTimeout(timer);
		},
		page: window,
		document
	}
): () => void {
	let cancel: (() => void) | null = null;
	let previous: string | null = null;
	let stopped = false;

	const refresh = () => {
		if (stopped) return;
		cancel?.();
		const now = new Date(runtime.now());
		const today = now.toISOString().slice(0, 10);
		if (today !== previous) {
			previous = today;
			show(today);
		}
		const midnight = new Date(now);
		midnight.setUTCHours(24, 0, 0, 0);
		cancel = runtime.schedule(refresh, midnight.getTime() - now.getTime());
	};

	refresh();
	runtime.document.addEventListener('visibilitychange', refresh);
	runtime.page.addEventListener('pageshow', refresh);
	runtime.page.addEventListener('focus', refresh);

	return () => {
		stopped = true;
		cancel?.();
		runtime.document.removeEventListener('visibilitychange', refresh);
		runtime.page.removeEventListener('pageshow', refresh);
		runtime.page.removeEventListener('focus', refresh);
	};
}
