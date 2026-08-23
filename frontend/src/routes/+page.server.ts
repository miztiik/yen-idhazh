import { latestDate, loadDay } from '$lib/server/payload';

export function load() {
	const latest = latestDate();
	return { today: latest ? loadDay(latest)?.date ?? latest : null };
}
