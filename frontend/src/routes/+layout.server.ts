import { uiConfig } from '$lib/server/config';
import { latestDate, loadDay } from '$lib/server/payload';

export const prerender = true;
export const trailingSlash = 'always';

/** Server-only, and every page is prerendered, so this runs in Node at build
 * time and never in a reader's browser.
 *
 * Whatever this returns is inlined into every page beneath it, so what it
 * hands the footer is four facts and never the day they were read from.
 */
export function load() {
	const latest = latestDate();
	const day = latest ? loadDay(latest) : null;
	const lastRun = day?.runs.at(-1) ?? null;
	return {
		ui: uiConfig(),
		latest,
		day,
		footer: day
			? {
					date: day.date,
					run: lastRun ? { n: lastRun.n, at: lastRun.at } : null,
					items_failed: day.items_failed,
					retention_window_months: day.retention_window_months
				}
			: null
	};
}
