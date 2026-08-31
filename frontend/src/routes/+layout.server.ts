import { uiConfig } from '$lib/server/config';
import { latestDate, loadDay } from '$lib/server/payload';

export const prerender = true;
export const trailingSlash = 'always';

/** Server-only, and every page is prerendered, so this runs in Node at build
 * time and never in a reader's browser.
 *
 * Whatever this returns is inlined into every page beneath it, including the
 * ones that render no day at all. So what it hands the footer is the single
 * fact the footer still states - never the day it was read from, and never a
 * fact about today's run, which `DayNotice` prints beside the day it describes.
 */
export function load() {
	const latest = latestDate();
	const day = latest ? loadDay(latest) : null;
	return {
		ui: uiConfig(),
		latest,
		footer: day ? { retention_window_months: day.retention_window_months } : null
	};
}
