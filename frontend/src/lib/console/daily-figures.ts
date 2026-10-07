/** What a route's table of daily figures says about the days it holds: the line
 * that opens it, the table's first sentence, and the note that sends a reader
 * to it.
 *
 * Pipelines and Summaries open their tables under the same words, so the words
 * are written once. "Day by day" and "newest first" need a second day, so a
 * window of one day names only the day the table holds. The words are Reader's.
 *
 * Pure and browser safe on purpose, so a logic test hands it the day counts it
 * writes.
 */

import { nameSpan } from './span-words';

/** The line that opens the table: `Show these figures day by day, over these 7 days`. */
export function dailyFiguresSummary(windowDays: number): string {
	return windowDays === 1
		? `Show these figures for ${nameSpan(windowDays)}`
		: `Show these figures day by day, over ${nameSpan(windowDays)}`;
}

/** What the table's rows are, the first sentence inside it. */
export function dailyFiguresRows(windowDays: number): string {
	return windowDays === 1
		? `One row for ${nameSpan(windowDays)}.`
		: 'One row per day in the open window, newest first.';
}

/** Where the Pipelines flow, which has no strip of its own, sends a reader for
 * each stage's count, quoting the line that opens the table. */
export function dailyFiguresPointer(windowDays: number): string {
	return windowDays === 1
		? `Open "${dailyFiguresSummary(windowDays)}" below for each stage's count.`
		: `Open "Show these figures day by day" below for each stage's count on every day.`;
}
