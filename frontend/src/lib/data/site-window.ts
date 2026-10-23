/**
 * Which UTC days of a ledger does the site staging copy keep?
 *
 * The site build copies each published ledger's indexes trimmed to a window: the
 * `windowDays` UTC days that end on the newest day the ledger's indexes name. It keeps
 * every entry that overlaps that window, so a month or a year can reach further back, and
 * drops every entry that ends before it. `frontend/scripts/published-ledgers.mjs` trims by
 * this rule. The explorer's repository source does not use this window.
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
