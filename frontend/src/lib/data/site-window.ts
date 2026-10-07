/**
 * Which UTC days of a ledger does the site copy keep, and may it have dropped older ones?
 *
 * The site build copies each published ledger's indexes trimmed to a window: the
 * `windowDays` UTC days that end on the newest day the ledger's indexes name. It keeps
 * every entry that overlaps that window, so a month or a year can reach further back, and
 * drops every entry that ends before it. `frontend/scripts/published-ledgers.mjs` trims by
 * this rule, and the Data explorer asks the archive for older days only when this rule says
 * the copy may have dropped some, so the two cannot disagree.
 *
 * Pure: it imports types only, so the site build loads it in plain Node.
 */

import type { DateStamp } from './slice-shapes';

const DAY_MS = 86_400_000;

/** The oldest UTC day the site copy keeps: the first of the `windowDays` days that end on
 *  `newest`, the newest day the ledger's indexes name. */
export function siteKeepsFrom(newest: DateStamp, windowDays: number): DateStamp {
	return new Date(Date.parse(`${newest}T00:00:00Z`) - (windowDays - 1) * DAY_MS).toISOString().slice(0, 10);
}

/** Whether the site copy may have dropped days before `siteFirst`, the oldest day the site's
 *  own indexes name. A dropped entry ended before the first day the copy keeps. An index names
 *  every day after its first, so the entry that holds that day was kept, and the site's first
 *  day is on or before it; a later first day means nothing was dropped. A ledger whose first
 *  entry holds that day reads the same as a trimmed one, and costs one needless archive read. */
export function siteMayHaveTrimmed(siteFirst: DateStamp, newest: DateStamp, windowDays: number): boolean {
	return siteFirst <= siteKeepsFrom(newest, windowDays);
}
