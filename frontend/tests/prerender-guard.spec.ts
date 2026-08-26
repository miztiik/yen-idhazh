import { expect, test } from '@playwright/test';
import { cpSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import config from '../svelte.config.js';

/**
 * The build used to fail on a clone that had never run the pipeline: `/[date]`
 * and `/[date]/[vertical]` are prerendered, their entries come from the
 * committed digest tree, and an empty tree produces no page. SvelteKit calls
 * that an unseen route and exits 1.
 *
 * These drive the real handler off the real config, so the wiring is under test
 * with the rule. The fixtures are the canary day and copies of it - no invented
 * payload, and nothing written inside the repository.
 */

const ROOT = resolve(process.cwd(), '..');
const CANARY = resolve(ROOT, 'backend', 'var', 'canary', 'digest');

const handleUnseenRoutes = config.kit.prerender.handleUnseenRoutes;

const DATED = '/[date]';
const TOPIC = '/[date]/[vertical]';

const temporary: string[] = [];

function scratch(): string {
	const path = mkdtempSync(join(tmpdir(), 'yi-prerender-'));
	temporary.push(path);
	return path;
}

/** The canary day, copied out, with every topic taken off it. */
function dayWithNoTopic(): string {
	const root = scratch();
	cpSync(CANARY, root, { recursive: true });
	for (const file of payloadsUnder(root)) {
		const day = JSON.parse(readFileSync(file, 'utf8'));
		day.verticals = [];
		day.items = [];
		writeFileSync(file, JSON.stringify(day));
	}
	return root;
}

function payloadsUnder(root: string): string[] {
	const found: string[] = [];
	for (const year of readdirSync(root)) {
		for (const month of readdirSync(join(root, year))) {
			for (const day of readdirSync(join(root, year, month))) {
				found.push(join(root, year, month, day, 'digest.json'));
			}
		}
	}
	return found;
}

function unseen(root: string, routes: string[]): () => void {
	return () => {
		const previous = process.env.DIGEST_ROOT;
		process.env.DIGEST_ROOT = root;
		try {
			handleUnseenRoutes({ routes, message: 'routes were not prerendered' });
		} finally {
			if (previous === undefined) delete process.env.DIGEST_ROOT;
			else process.env.DIGEST_ROOT = previous;
		}
	};
}

test.afterAll(() => {
	for (const path of temporary) rmSync(path, { recursive: true, force: true });
});

test('a clone that has never run the pipeline still builds', () => {
	expect(unseen(scratch(), [DATED, TOPIC])).not.toThrow();
});

test('a day that published nothing still builds', () => {
	expect(unseen(dayWithNoTopic(), [TOPIC])).not.toThrow();
});

test('a dated page missing while days are published fails the build', () => {
	expect(unseen(CANARY, [DATED])).toThrow(/had a page to build and did not build it/);
});

test('a topic page missing while days name topics fails the build', () => {
	expect(unseen(CANARY, [TOPIC])).toThrow(/had a page to build and did not build it/);
});

test('a day directory holding no payload is not a published day', () => {
	const root = scratch();
	mkdirSync(join(root, '2026', '08', '26'), { recursive: true });

	expect(unseen(root, [DATED, TOPIC])).not.toThrow();
});

/**
 * The reason this is a handler and not `handleUnseenRoutes: 'ignore'`. Every
 * other route is reached by a link, so one that stops being prerendered is a
 * dead page nobody asked for - the empty tree excuses the dated routes and
 * nothing else.
 */
test('a static route that stopped being reached fails even on an empty tree', () => {
	expect(unseen(scratch(), ['/archive'])).toThrow(/had a page to build and did not build it/);
});
