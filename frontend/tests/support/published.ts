/** Which dates and topics the fixture published, read off the digest tree.
 *
 * **A spec used to read this out of `build/`**, because a build wrote one
 * directory per published day and one inside it per topic. From 2026-09-09 it
 * writes neither: one document answers every dated address and the browser
 * fetches the day it names. A listing of `build/` therefore finds no date at
 * all, and a spec that took its fixture day from there got `undefined` - which
 * reads as a broken loader rather than as a tree that stopped holding dates.
 *
 * The digest tree is the right source anyway, and it always was. It is what the
 * page renders from, so a date taken from it is a date the site has something to
 * say about - where a date taken from `build/` only ever meant a build wrote a
 * directory.
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

/** The committed tree, for a real-mode spec. */
export const COMMITTED = resolve(HERE, '..', '..', 'public', 'digest');

function dirs(at: string): string[] {
	return readdirSync(at, { withFileTypes: true })
		.filter((entry) => entry.isDirectory())
		.map((entry) => entry.name)
		.sort();
}

/** Every date the tree published, oldest first. */
export function publishedDates(root: string = CANARY): string[] {
	const found: string[] = [];
	for (const year of dirs(root)) {
		for (const month of dirs(join(root, year))) {
			for (const day of dirs(join(root, year, month))) {
				found.push(`${year}-${month}-${day}`);
			}
		}
	}
	return found.sort();
}

/** The newest date the tree published. */
export function newestDate(root: string = CANARY): string {
	const dates = publishedDates(root);
	if (dates.length === 0) throw new Error(`no day is published under ${root}`);
	return dates[dates.length - 1];
}

/** The payload of one day, as JSON. */
export function payloadOf(date: string, root: string = CANARY): Record<string, unknown> {
	const [year, month, day] = date.split('-');
	return JSON.parse(readFileSync(join(root, year, month, day, 'digest.json'), 'utf8'));
}

/** The topics that day published stories under, in the payload's own order.
 *
 * Read through `desk_count`, so a topic listed only because its feeds carried a
 * story the day then published elsewhere is not in here. A route for one of
 * those answers `Not here`, which is what the page does on purpose - a pill
 * leading to an empty room is a dead end rather than a way in. */
export function topicsOf(date: string, root: string = CANARY): string[] {
	const verticals = payloadOf(date, root).verticals;
	if (!Array.isArray(verticals)) return [];
	return verticals
		.filter((ref) => {
			const entry = ref as { count: number; desk_count?: number | null };
			return (entry.desk_count ?? entry.count) > 0;
		})
		.map((ref) => String((ref as { id: unknown }).id));
}

/** One topic of that day. Which one is the fixture's business. */
export function topicOf(date: string, root: string = CANARY): string {
	const topics = topicsOf(date, root);
	if (topics.length === 0) throw new Error(`${date} published no topic`);
	return topics[0];
}
