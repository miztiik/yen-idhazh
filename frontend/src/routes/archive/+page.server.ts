/** Provide registered month names and a recent browsing bound without opening historical days. */
import { indexMonths, publishedDates } from '$lib/server/payload';
import { archiveTopViewports, archiveWindowDays, assistConfig } from '$lib/server/config';

export const prerender = true;

export function load() {
	return {
		// All registered months are available to an explicit archive query.
		months: indexMonths(undefined, -1),
		latest: publishedDates(undefined, 1)[0] ?? '',
		windowDays: archiveWindowDays(),
		topViewports: archiveTopViewports(),
		assist: assistConfig()
	};
}
