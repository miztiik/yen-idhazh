/** Which UTC instant, and so which UTC day, does the engine's text for a date or a timestamp name?
 *
 * The answer table sorts a date or a timestamp column by the instant, to the nanosecond, and the
 * date chart puts each row on its UTC day. Both are read from the text alone, so the browser's
 * time zone cannot change them (CLAUDE.md section 2). The day the text prints is not always the
 * UTC day: the engine prints a timestamp with a time zone in a whole-hour offset it takes from the
 * page's zone, so on a page in Berlin 23:30 UTC prints as `00:30:00+01` on the next day.
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

const NANOSECONDS_A_DAY = 86_400_000_000_000n;

/** The UTC day, `YYYY-MM-DD`, of the instant a date or a timestamp names. `null` for text that
 *  names no instant, and for a day outside the years 0000 to 9999, which that form cannot hold. */
export function readUtcDay(text: string): string | null {
	const at = readUtcNanoseconds(text);
	if (at === null) return null;
	// BigInt division rounds toward zero, so an instant before 1970 is moved down to its own day.
	const days = at / NANOSECONDS_A_DAY - (at % NANOSECONDS_A_DAY < 0n ? 1n : 0n);
	const day = new Date(Number(days) * 86_400_000).toISOString().slice(0, 10);
	return /^\d{4}-\d\d-\d\d$/.test(day) ? day : null;
}
