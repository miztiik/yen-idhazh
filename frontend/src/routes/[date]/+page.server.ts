import { error } from '@sveltejs/kit';
import { loadDay, publishedDates } from '$lib/server/payload';

export const prerender = true;

export function entries() {
	return publishedDates().map((date) => ({ date }));
}

export function load({ params }: { params: { date: string } }) {
	const day = loadDay(params.date);
	// A date that was never published stays a 404. Redirecting to today would
	// leave a reader unable to tell a dead link from a live one.
	if (!day) error(404, `No digest was published for ${params.date}.`);
	return { day, date: params.date };
}
