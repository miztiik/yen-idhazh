import { error } from '@sveltejs/kit';
import { loadDay, publishedDates } from '$lib/server/payload';

export const prerender = true;

/** Only verticals actually present get a page, so no route leads to an empty room. */
export function entries() {
	const found: { date: string; vertical: string }[] = [];
	for (const date of publishedDates()) {
		const day = loadDay(date);
		for (const vertical of day?.verticals ?? []) {
			found.push({ date, vertical: vertical.id });
		}
	}
	return found;
}

export function load({ params }: { params: { date: string; vertical: string } }) {
	const day = loadDay(params.date);
	if (!day) error(404, `No digest was published for ${params.date}.`);
	if (!day.verticals.some((ref) => ref.id === params.vertical)) {
		error(404, `Nothing was published under ${params.vertical} on ${params.date}.`);
	}
	return { day, date: params.date, vertical: params.vertical };
}
