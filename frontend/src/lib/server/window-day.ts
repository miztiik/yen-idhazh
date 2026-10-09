/** Which day does every console window end on?
 *
 * The newest day the site published a digest, `latestDate()`. The owner ruled on
 * 2026-10-05 that every console window ends there, so two builds of the same data
 * draw the same windows, and a record whose rows stop leaves its panels empty for
 * the window rather than moving the window back to its own last rows. The build
 * clock places no window. With `console.today_anchor` at `centre` the day sits in
 * the middle of the window instead (`windowOfDays`).
 *
 * When the site has published no day there is nothing to draw on any route, and
 * the build's own UTC day keeps every window a real span of days, so the page
 * still renders (`CLAUDE.md` section 12).
 *
 * Imports nothing that needs a Vite alias: the browser suite loads it in plain Node.
 */

// Relative, not `$lib`, for the reason in the module docstring.
import { dayKey } from '../charts/viewport';
import { DIGEST_ROOT, latestDate } from './payload';

/** The day every console window ends on, read from the days published under `root`. */
export function windowDay(root: string = DIGEST_ROOT): string {
	return latestDate(root, 1) ?? dayKey(new Date());
}
