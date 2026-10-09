/** Which adjacent input positions are defined without crossing a gap? */
export function indexedRuns<T>(
	items: readonly T[],
	isDefined: (item: T, index: number) => boolean
): number[][] {
	const runs: number[][] = [];
	let current: number[] = [];
	items.forEach((item, index) => {
		if (isDefined(item, index)) {
			current.push(index);
		} else if (current.length > 0) {
			runs.push(current);
			current = [];
		}
	});
	if (current.length > 0) runs.push(current);
	return runs;
}
