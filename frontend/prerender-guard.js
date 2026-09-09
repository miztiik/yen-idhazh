/**
 * An unseen prerender route is a defect. There are no longer any exceptions.
 *
 * SvelteKit fails a build when a route marked prerenderable produced no page.
 * Until 2026-09-09 the two dated routes were prerendered off the committed
 * digest tree, so a fresh clone with no published day produced no dated page
 * and the build failed - which contradicts the rule that a fresh clone runs on
 * the defaults (CLAUDE.md section 1a). This file existed to tell that normal
 * state apart from a page that went missing while days WERE published, by
 * asking the digest tree rather than switching the check off.
 *
 * Both dated routes are rendered in the browser now, from one shell, so neither
 * is prerenderable and neither can be unseen. What is left prerendered is `/`,
 * `/archive/`, `/evals/` and the three console routes - six routes that read no
 * committed day to decide whether they exist, so every one of them produces a
 * page on every build, on a fresh clone included. An unseen route among them is
 * a defect with no innocent reading, and this says so.
 *
 * `handleUnseenRoutes: 'ignore'` would allow the same builds and allow every
 * other unseen route with them. The point of a handler here is the sentence a
 * failing build prints: which routes, and what to look at.
 */

/**
 * SvelteKit's `prerender.handleUnseenRoutes`.
 *
 * @param {{ routes: string[], message: string }} details
 */
export function handleUnseenRoutes({ routes, message }) {
	throw new Error(
		`${message}\n` +
			`${routes.join(', ')} is prerendered and built no page. Every prerendered route on this ` +
			'site renders without reading a published day, so no state of the digest tree excuses ' +
			'this. Check the route file, its page options, and the links that reach it.'
	);
}
