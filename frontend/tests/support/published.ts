/** Which dates and topics the fixture published, read off the digest tree.
 *
 * **A spec used to read this out of `build/`**, because a build wrote one
 * directory per published day and one inside it per topic. From 2026-09-09 it
 * writes neither: one document answers every dated address and the browser
 * fetches the day it names. A listing of `build/` therefore finds no date at
 * all, and a spec that took its fixture day from there got `undefined` - which
 * reads as a broken loader rather than as a tree that stopped holding dates.
 *
 * The canary digest is a fixed fixture. It is what the browser suite builds
 * from, so its day and topics are stable test inputs rather than archive data.
 *
 * **A date is never written into a spec.** A hardcoded one passes on an empty
 * page the moment the fixture moves, which is the failure this file exists to
 * make impossible.
 */

import { readdirSync, readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));

/** The canary tree `build_canary_day.py` writes and `npm run build:canary`
 * renders. Resolved off this file rather than off `process.cwd()`, because a
 * playwright run started from the repository root would otherwise look in the
 * wrong place - see `docs/reference/agent-notes.md`. */
export const CANARY = resolve(HERE, '..', '..', '..', 'backend', 'var', 'canary', 'digest');

function dirs(at: string): string[] {
	return readdirSync(at, { withFileTypes: true })
		.filter((entry) => entry.isDirectory())
		.map((entry) => entry.name)
		.sort();
}

/** Every date in the fixed canary fixture, oldest first. */
export function publishedDates(): string[] {
	const found: string[] = [];
	for (const year of dirs(CANARY)) {
		for (const month of dirs(join(CANARY, year))) {
			for (const day of dirs(join(CANARY, year, month))) {
				found.push(`${year}-${month}-${day}`);
			}
		}
	}
	return found.sort();
}

/** The newest date in the fixed canary fixture. */
export function newestDate(): string {
	const dates = publishedDates();
	if (dates.length === 0) throw new Error(`the canary fixture has no published day under ${CANARY}`);
	return dates[dates.length - 1];
}

/** The payload of one day, as JSON. */
export function payloadOf(date: string): Record<string, unknown> {
	const [year, month, day] = date.split('-');
	return JSON.parse(readFileSync(join(CANARY, year, month, day, 'digest.json'), 'utf8'));
}

/** The topics that day published stories under, in the payload's own order.
 *
 * Read through `desk_count`, so a topic listed only because its feeds carried a
 * story the day then published elsewhere is not in here. A route for one of
 * those answers `Not here`, which is what the page does on purpose - a pill
 * leading to an empty room is a dead end rather than a way in. */
export function topicsOf(date: string): string[] {
	const verticals = payloadOf(date).verticals;
	if (!Array.isArray(verticals)) return [];
	return verticals
		.filter((ref) => {
			const entry = ref as { count: number; desk_count?: number | null };
			return (entry.desk_count ?? entry.count) > 0;
		})
		.map((ref) => String((ref as { id: unknown }).id));
}

/** One topic of that day. Which one is the fixture's business. */
export function topicOf(date: string): string {
	const topics = topicsOf(date);
	if (topics.length === 0) throw new Error(`${date} published no topic`);
	return topics[0];
}
