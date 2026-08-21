import { loadDay, publishedDates } from '$lib/server/payload';

export const prerender = true;

export function load() {
	return {
		days: publishedDates().map((date) => {
			const day = loadDay(date);
			return {
				date,
				items: day?.items.length ?? 0,
				partial: day?.partial ?? false
			};
		})
	};
}
