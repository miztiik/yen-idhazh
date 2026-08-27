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
		// The knobs search reads, and nothing search searches. The day payloads used
		// to be here so on-device search could reach the vectors inside them, which
		// cost every browsing visitor 1.7 MB gzipped. Search reads the month index
		// now, and fetches a day only when a result from it is on screen.
		assist: assistConfig()
	};
}
