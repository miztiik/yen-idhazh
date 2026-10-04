/** A run of consecutive ISO days, read in UTC so the suite cannot drift west. */
export function days(start: string, count: number): string[] {
	const first = new Date(`${start}T00:00:00Z`).getTime();
	return Array.from({ length: count }, (_, index) =>
		new Date(first + index * 86_400_000).toISOString().slice(0, 10)
	);
}
