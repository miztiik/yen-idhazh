import { loadDay, publishedDates } from '$lib/server/payload';
import type { DigestDay } from '$lib/payload/types';

export const prerender = true;

export function load() {
	const loaded = publishedDates()
		.map((date) => loadDay(date))
		.filter((day): day is DigestDay => day !== null);

	return {
		days: loaded.map((day) => ({
			date: day.date,
			items: day.items.length,
			partial: day.partial
		})),
		// The same payloads, whole, for on-device search. They are already on this
		// page's prerendered data - no extra request, which is the constraint the
		// layout row fixed - and the vectors inside them are what makes the search
		// possible without the browser embedding anything but a query.
		payloads: loaded
	};
}
