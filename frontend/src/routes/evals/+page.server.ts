import { evalRows } from '$lib/server/payload';

export const prerender = true;

/** Read at build time, never recomputed. The dashboard shows the committed
 * numbers or it shows nothing - it never re-derives a score. */
export function load() {
	return evalRows();
}
