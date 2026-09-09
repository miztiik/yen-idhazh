import { uiConfig } from '$lib/server/config';

export const prerender = true;
export const trailingSlash = 'always';

/** Server-only, and every page is prerendered, so this runs in Node at build
 * time and never in a reader's browser.
 *
 * Whatever this returns is inlined into every page beneath it, so **nothing
 * here may come from a day**. One fact about the newest day rewrites the bytes
 * of every older page the next time a day publishes - a page a reader already
 * holds goes stale for a reason that has nothing to do with what it says. The
 * config is what is left, and it moves only when a person edits it.
 */
export function load() {
	return { ui: uiConfig() };
}
