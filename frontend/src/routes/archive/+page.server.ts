import { indexMonths, loadDay, publishedDates } from '$lib/server/payload';
import { archiveRecentDays, assistConfig } from '$lib/server/config';
import { archiveCalendar, type ArchiveDay } from '$lib/archive-calendar';
import type { DigestDay, DigestVerticalRef } from '$lib/payload/types';

export const prerender = true;

export function load() {
	const loaded = publishedDates()
		.map((date) => loadDay(date))
		.filter((day): day is DigestDay => day !== null);

	// Every topic name any committed day used. About twenty strings, so it is a
	// bounded fact this page may carry - unlike the stories themselves, which the
	// browser fetches a month at a time.
	const verticalNames: Record<string, string> = {};
	// And how many stories each of them holds across the whole archive. One
	// integer a topic, so it grows per topic and never per story. It is the pill
	// count, and it is the honest denominator for a topic-filtered list while
	// months are still unread - the page has never counted them itself.
	const verticalCounts: Record<string, number> = {};
	for (const day of loaded) {
		for (const ref of day.verticals) {
			verticalNames[ref.id] = ref.display_name;
			verticalCounts[ref.id] = (verticalCounts[ref.id] ?? 0) + ref.count;
		}
	}
	const verticals: DigestVerticalRef[] = Object.keys(verticalCounts)
		.sort()
		.map((id) => ({
			id,
			display_name: verticalNames[id] as string,
			count: verticalCounts[id] as number
		}));

	const days: ArchiveDay[] = loaded.map((day) => ({
		date: day.date,
		items: day.items.length,
		partial: day.partial
	}));

	return {
		// The newest few days, as rows carrying the date, the story count and
		// whether every story finished. A shortcut into the calendar below and never
		// the only way in - the same days sit inside their month as well.
		recent: days.slice(0, archiveRecentDays()),
		// Every published day, grouped by month and then by year. What a reader sees
		// grows by one row a month; what the document carries for a day is a
		// day-of-month number and a short link, where it used to be a dated row.
		calendar: archiveCalendar(days),
		dayCount: days.length,
		// The months a browser may ask for, and how many stories they hold between
		// them. Both grow per month and per day, never per story, which is what
		// keeps this page a fixed size while the archive grows.
		months: indexMonths(),
		stories: loaded.reduce((count, day) => count + day.items.length, 0),
		verticalNames,
		verticals,
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
