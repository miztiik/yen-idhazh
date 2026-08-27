import { indexMonths, loadDay, publishedDates } from '$lib/server/payload';
import { assistConfig } from '$lib/server/config';
import type { DigestDay } from '$lib/payload/types';

export const prerender = true;

export function load() {
	const loaded = publishedDates()
		.map((date) => loadDay(date))
		.filter((day): day is DigestDay => day !== null);

	// Every topic name any committed day used. About twenty strings, so it is a
	// bounded fact this page may carry - unlike the stories themselves, which the
	// browser fetches a month at a time.
	const verticalNames: Record<string, string> = {};
	for (const day of loaded) {
		for (const ref of day.verticals) verticalNames[ref.id] = ref.display_name;
	}

	return {
		days: loaded.map((day) => ({
			date: day.date,
			items: day.items.length,
			partial: day.partial
		})),
		// The months a browser may ask for, and how many stories they hold between
		// them. Both grow per month and per day, never per story, which is what
		// keeps this page a fixed size while the archive grows.
		months: indexMonths(),
		stories: loaded.reduce((count, day) => count + day.items.length, 0),
		verticalNames,
		// The newest day states the window, because its run is the one that last
		// read the knob. `layout.md` requires the archive to say it before
		// anything is ever deleted.
		retentionMonths: loaded[0]?.retention_window_months ?? -1,
		// The same payloads, whole, for on-device search. They are already on this
		// page's prerendered data - no extra request, which is the constraint the
		// layout row fixed - and the vectors inside them are what makes the search
		// possible without the browser embedding anything but a query.
		payloads: loaded,
		assist: assistConfig()
	};
}
