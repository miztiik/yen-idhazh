import { uiConfig } from '$lib/server/config';
import { latestDate, loadDay } from '$lib/server/payload';

export const prerender = true;
export const trailingSlash = 'always';

/** Server-only, and every page is prerendered, so this runs in Node at build
 * time and never in a reader's browser. */
export function load() {
	const latest = latestDate();
	return {
		ui: uiConfig(),
		latest,
		day: latest ? loadDay(latest) : null
	};
}
