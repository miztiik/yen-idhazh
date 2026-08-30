import { consoleShell } from '$lib/server/console-shell';

export const prerender = true;

/** The band and the strip, derived once for all three console routes.
 *
 * It runs in Node at build time, like every other load on this site, and what
 * it returns is inlined into each of the three prerendered documents. That is
 * the point: three routes that each derived their own band would eventually
 * disagree about which one of them is worst.
 */
export function load() {
	return consoleShell();
}
