import { latestDate, loadDay } from '$lib/server/payload';

/** The home page reads the day it renders.
 *
 * It used to read one the root layout returned, which is why every other page
 * carried that day too - the console, the archive, an old dated page.
 */
export function load() {
	const latest = latestDate();
	const day = latest ? loadDay(latest) : null;
	return { day, today: day?.date ?? latest };
}
