/**
 * Which unseen prerender route is a day nobody published, and which is a defect.
 *
 * Every route on this site is prerendered, so SvelteKit fails the build when a
 * route marked prerenderable produced no page. For the dated routes that is the
 * normal state of a fresh clone: their `entries()` read the committed digest
 * tree, and before the first pipeline run there is nothing in it. Failing there
 * means a clone cannot build the site until a day exists, which contradicts the
 * rule that a fresh clone runs on the defaults (CLAUDE.md section 1a).
 *
 * `handleUnseenRoutes: 'ignore'` would fix that and hide the case worth
 * catching - a dated page missing while days ARE published. So this asks the
 * digest tree instead, and it asks a smaller question than `entries()` does:
 * `entries()` lists the days, this only asks whether any day is there at all.
 * When the two answers disagree the build still fails, and so does any other
 * route that stops being reached.
 */

import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { join, relative, resolve, sep } from 'node:path';

const DATE_PART = /^\d{2,4}$/;

/** The digest tree the build reads. Same expression `src/lib/server/payload.ts` uses. */
function digestRoot() {
	return process.env.DIGEST_ROOT
		? resolve(process.env.DIGEST_ROOT)
		: join(process.cwd(), 'public', 'digest');
}

/**
 * @param {string} at
 * @returns {string[]}
 */
function dirsIn(at) {
	if (!existsSync(at)) return [];
	return readdirSync(at, { withFileTypes: true })
		.filter((entry) => entry.isDirectory() && DATE_PART.test(entry.name))
		.map((entry) => entry.name)
		.sort();
}

/**
 * What the tree holds: how many days, and whether any of them names a topic.
 *
 * Days are counted from directory names alone, and a payload is read only until
 * the first one that names a topic - so a tree with news in it costs one file.
 *
 * @param {string} root
 * @returns {{ days: number, topics: boolean }}
 */
function surveyDigest(root) {
	/** @type {string[]} */
	const files = [];
	for (const year of dirsIn(root)) {
		for (const month of dirsIn(join(root, year))) {
			for (const day of dirsIn(join(root, year, month))) {
				const file = join(root, year, month, day, 'digest.json');
				if (existsSync(file)) files.push(file);
			}
		}
	}
	const topics = files.some((file) => {
		const day = JSON.parse(readFileSync(file, 'utf8'));
		return Array.isArray(day.verticals) && day.verticals.length > 0;
	});
	return { days: files.length, topics };
}

/**
 * @param {string} route
 * @param {{ days: number, topics: boolean }} survey
 * @returns {boolean}
 */
function publishedNothing(route, survey) {
	// Rename either route directory and the id stops matching here, so the build fails.
	if (route === '/[date]') return survey.days === 0;
	// A day with no topic is a day with no item, which the pipeline does publish.
	if (route === '/[date]/[vertical]') return !survey.topics;
	return false;
}

/**
 * @param {{ days: number, topics: boolean }} survey
 * @param {string} root
 * @returns {string}
 */
function describe(survey, root) {
	const where = relative(process.cwd(), root).split(sep).join('/') || '.';
	if (survey.days === 0) return `no day is published under ${where}`;
	const days = `${survey.days} published ${survey.days === 1 ? 'day' : 'days'}`;
	const topics = survey.topics ? 'at least one names a topic' : 'none names a topic';
	return `${where} holds ${days}, and ${topics}`;
}

/**
 * SvelteKit's `prerender.handleUnseenRoutes`.
 *
 * @param {{ routes: string[], message: string }} details
 */
export function handleUnseenRoutes({ routes, message }) {
	const root = digestRoot();
	const survey = surveyDigest(root);
	const defects = routes.filter((route) => !publishedNothing(route, survey));

	if (defects.length > 0) {
		throw new Error(
			`${message}\n` +
				`${describe(survey, root)}, so ${defects.join(', ')} had a page to build and did not ` +
				'build it. Check the route entries() and the links that reach it.'
		);
	}

	console.log(
		`prerender: ${describe(survey, root)}, so ${routes.join(', ')} built no page. ` +
			'The site shows its empty state instead.'
	);
}
