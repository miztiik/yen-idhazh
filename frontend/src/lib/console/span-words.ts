/** What words a console sentence names the days of its window with.
 *
 * Two kinds, and only two, so the 1-day preset never prints "1 days" and one
 * edit here moves every windowed sentence: the days on screen, `these 7 days`
 * or `this one day`, and a bare count, `7 days` or `1 day`. A count over the
 * window takes the bare count - `on 5 of 7 days`, `on 1 of 1 day` - because
 * "of this one day" breaks. The words are Reader's.
 *
 * Pure and browser safe on purpose: no config read and no `$lib` alias, so a
 * logic test hands it the day counts it writes.
 */

import { plural } from '../format';

/** The days on screen, as a sentence names them: `these 7 days`, `this one day`. */
export function nameSpan(days: number): string {
	return days === 1 ? 'this one day' : `these ${days} days`;
}

/** The same words opening a sentence or labelling a row: `These 7 days`, `This one day`. */
export function openWithSpan(days: number): string {
	const words = nameSpan(days);
	return `${words.charAt(0).toUpperCase()}${words.slice(1)}`;
}

/** A bare count of days, the words the days control speaks: `7 days`, `1 day`.
 * `kind` says which days, where the count is not of every day: `1 measured day`. */
export function countDays(days: number, kind = ''): string {
	const day = kind === '' ? 'day' : `${kind} day`;
	return plural(days, day, `${day}s`);
}
