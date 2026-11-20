/** When does a panel's UTC span need its own label? */
import type { TimeWindow } from '../charts/viewport';
import { shortDate } from '../format';

export function rangeBounds(range?: { from: string; to: string } | null): TimeWindow | null {
	return range == null ? null : { start: range.from, end: range.to };
}

export function sameBounds(a: TimeWindow | null, b: TimeWindow | null): boolean {
	return a !== null && b !== null && a.start === b.start && a.end === b.end;
}

export function utcSpan(span: TimeWindow): string {
	return `${shortDate(span.start)}${span.start === span.end ? '' : ` - ${shortDate(span.end)}`} UTC`;
}

export function coverageException(span: TimeWindow, common: TimeWindow | null): string | null {
	if (common === null) return 'Separate record';
	if (sameBounds(span, common)) return null;
	if (span.end < common.end) return 'Older records only';
	if (span.end > common.end) return 'Later records';
	return span.start > common.start ? 'Shorter coverage' : 'Wider coverage';
}
