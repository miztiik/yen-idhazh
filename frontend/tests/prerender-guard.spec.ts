import { expect, test } from '@playwright/test';
import config from '../svelte.config.js';

/**
 * An unseen prerender route is a defect, and since 2026-09-09 there is no
 * innocent reading of one.
 *
 * The guard used to have a real question to answer. `/[date]` and
 * `/[date]/[vertical]` were prerendered off the committed digest tree, so a
 * clone that had never run the pipeline produced no dated page and SvelteKit
 * exited 1 - a build that could not run until a day existed, against the rule
 * that a fresh clone runs on the defaults (CLAUDE.md section 1a). The guard read
 * the tree and excused exactly those two routes when it was empty.
 *
 * Both dated routes render in the browser now, from one shell, so neither is
 * prerenderable and neither can be unseen. What is left prerendered is `/`,
 * `/archive/`, `/evals/` and the three console routes, and not one of them reads
 * a published day to decide whether it exists.
 *
 * These drive the real handler off the real config, so the wiring stays under
 * test with the rule. Nothing here reads the digest tree, because the handler no
 * longer does - which is the change.
 */

const handleUnseenRoutes = config.kit.prerender.handleUnseenRoutes;

function unseen(routes: string[]): () => void {
	return () => handleUnseenRoutes({ routes, message: 'routes were not prerendered' });
}

test('a prerendered route that built no page fails the build', () => {
	expect(unseen(['/archive'])).toThrow(/is prerendered and built no page/);
});

test('the two routes the old guard excused are not excused any more', () => {
	// Neither is prerendered, so neither can arrive here - and if one does, a
	// route file has grown a `prerender = true` that nothing else would catch.
	expect(unseen(['/[date]'])).toThrow(/is prerendered and built no page/);
	expect(unseen(['/[date]/[vertical]'])).toThrow(/is prerendered and built no page/);
});

test('the failure names every route it was handed', () => {
	expect(unseen(['/evals', '/console/model'])).toThrow(/\/evals, \/console\/model/);
});

/**
 * The message is a record leaving the process, so it carries no absolute path
 * and no drive letter (CLAUDE.md section 2). The old handler printed where the
 * digest tree was and had to be careful about it; this one names routes, which
 * is a shape that cannot carry a path - and that is worth an assertion rather
 * than an assumption.
 */
test('the failure names no absolute path and no drive letter', () => {
	let said = '';
	try {
		unseen(['/archive'])();
	} catch (error) {
		said = String(error);
	}
	expect(said, 'the handler did not throw').not.toBe('');
	expect(said).not.toMatch(/[A-Za-z]:[\\/]/);
	expect(said).not.toContain('\\');
});

/**
 * The reason this is a handler and not `handleUnseenRoutes: 'ignore'`. Ignoring
 * would allow the same builds and allow every other unseen route with them, and
 * it would say nothing when it did. What a handler buys is the sentence.
 */
test('the build is told what to look at', () => {
	expect(unseen(['/archive'])).toThrow(/route file, its page options, and the links that reach it/);
});
