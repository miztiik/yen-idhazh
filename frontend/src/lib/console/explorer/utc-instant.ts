/** Which UTC instant does the engine's text for a date or a timestamp name, to the nanosecond?
 *
 * The answer table sorts a date or a timestamp column by it. It is read from the text alone, so
 * the browser's time zone cannot change it (CLAUDE.md section 2).
 */

/** A date or a timestamp as the engine prints it: the day, a time of day to the nanosecond, and
 *  the offset from UTC that a timestamp with a time zone carries. A `T` and a `Z` are read as
 *  ISO 8601 writes them. Text with no offset is UTC (CLAUDE.md section 2). */
const DAY_TEXT = /^(\d{4,})-(\d\d)-(\d\d)(?:[ T](\d\d):(\d\d):(\d\d)(?:\.(\d{1,9}))?)?(?:Z|([+-])(\d\d)(?::(\d\d))?(?::(\d\d))?)?$/;

/** Nanoseconds from 1970-01-01 00:00 UTC to the instant a date or a timestamp names, read from
 *  the engine's text, so neither the browser's time zone nor a millisecond clock changes the
 *  order. `null` for text that names no instant, such as `infinity` or a date `(BC)`. */
export function readUtcNanoseconds(text: string): bigint | null {
	const part = DAY_TEXT.exec(text);
	if (part === null) return null;
	const [, year, month, day, hour = '0', minute = '0', second = '0', fraction = '', sign = '+', offsetHour = '0', offsetMinute = '0', offsetSecond = '0'] = part;
	const offset = (sign === '-' ? -1 : 1) * ((Number(offsetHour) * 60 + Number(offsetMinute)) * 60 + Number(offsetSecond));
	const at = new Date(0);
	// Not `Date.UTC`, which reads a year below 100 as 1900 plus that year.
	at.setUTCFullYear(Number(year), Number(month) - 1, Number(day));
	at.setUTCHours(Number(hour), Number(minute), Number(second) - offset);
	const ms = at.getTime();
	return Number.isNaN(ms) ? null : BigInt(ms) * 1_000_000n + BigInt(fraction.padEnd(9, '0'));
}
