/** Formatting a reader sees. Deterministic, so two builds agree. */

const MONTHS = [
	'January',
	'February',
	'March',
	'April',
	'May',
	'June',
	'July',
	'August',
	'September',
	'October',
	'November',
	'December'
];

export function longDate(date: string): string {
	const [year, month, day] = date.split('-').map(Number);
	if (!year || !month || !day) return date;
	return `${day} ${MONTHS[month - 1]} ${year}`;
}

export function shortDate(date: string): string {
	const [year, month, day] = date.split('-').map(Number);
	if (!year || !month || !day) return date;
	return `${dayMonth(date)} ${year}`;
}

/** "20 Aug" - the short form without the year, for a dense axis. */
export function dayMonth(date: string): string {
	const [year, month, day] = date.split('-').map(Number);
	if (!year || !month || !day) return date;
	return `${day} ${MONTHS[month - 1]!.slice(0, 3)}`;
}

/** "2026-08" -> "August 2026". What a reader is told a search covered. */
export function monthName(month: string): string {
	const [year, index] = month.split('-').map(Number);
	if (!year || !index || index < 1 || index > 12) return month;
	return `${MONTHS[index - 1]} ${year}`;
}

export function clockUtc(timestamp: string): string {
	return timestamp.slice(11, 16) + ' UTC';
}

/** Initials of the first two meaningful words: "Ars Technica - AI" -> "AT". */
export function monogram(name: string): string {
	const skip = new Set(['the', 'a', 'an', 'of', 'and', 'for']);
	const words = name
		.split(/[\s\-/|]+/)
		.map((word) => word.replace(/[^A-Za-z0-9.]/g, ''))
		.filter((word) => word.length > 0 && !skip.has(word.toLowerCase()));
	if (words.length === 0) return '??';
	if (words.length === 1) return words[0]!.slice(0, 2).toUpperCase();
	return (words[0]![0]! + words[1]![0]!).toUpperCase();
}

/** Stable per source, so a publication keeps its colour between visits. */
export function swatchIndex(sourceId: string): number {
	let hash = 0;
	for (let i = 0; i < sourceId.length; i += 1) {
		hash = (hash * 31 + sourceId.charCodeAt(i)) >>> 0;
	}
	return hash % 8;
}

export function plural(count: number, one: string, many: string): string {
	return `${count} ${count === 1 ? one : many}`;
}
