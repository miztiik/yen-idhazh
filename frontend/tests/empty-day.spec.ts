import { expect, test } from '@playwright/test';
import { readdirSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';

const ROOT = resolve(process.cwd(), '..');
const CANARY = resolve(ROOT, 'backend', 'var', 'canary', 'digest');

function dirs(at: string): string[] {
	return readdirSync(at, { withFileTypes: true })
		.filter((entry) => entry.isDirectory())
		.map((entry) => entry.name)
		.sort();
}

function latestFixtureDay(): string {
	const year = dirs(CANARY).at(-1) as string;
	const month = dirs(join(CANARY, year)).at(-1) as string;
	const day = dirs(join(CANARY, year, month)).at(-1) as string;
	const raw = readFileSync(join(CANARY, year, month, day, 'digest.json'), 'utf8');
	return (JSON.parse(raw) as { date: string }).date;
}

function longDate(date: string): string {
	const months = [
		'January',
		'February',
		'March',
		'April',
		'May',
		'June',
		'July',
		'August',
		'September',
		'October',
		'November',
		'December'
	];
	const [year, month, day] = date.split('-').map(Number);
	return `${day} ${months[month - 1]} ${year}`;
}

test('the home page names the payload date, not the build clock', async ({ page }) => {
	const date = latestFixtureDay();

	await page.goto('/');

	await expect(page.locator('main').getByText(longDate(date)).first()).toBeVisible();
});

test('the root empty state cannot point at an absent notice or hide the latest link', () => {
	const page = readFileSync(resolve(ROOT, 'frontend', 'src', 'routes', '+page.svelte'), 'utf8');
	const copy = readFileSync(
		resolve(ROOT, 'frontend', 'src', 'lib', 'components', 'EmptyDay.svelte'),
		'utf8'
	);

	expect(page).toContain('latest={data.latest}');
	expect(copy).not.toContain('run notice above');
	expect(copy).toContain('Latest day -');
});

test('the root load does not read the build clock', () => {
	const source = readFileSync(resolve(ROOT, 'frontend', 'src', 'routes', '+page.server.ts'), 'utf8');

	expect(source).not.toContain('new Date');
	expect(source).toContain('loadDay(latest)?.date');
});

test('reader source limits are sentences in the page text', () => {
	const item = readFileSync(
		resolve(ROOT, 'frontend', 'src', 'lib', 'components', 'DigestItem.svelte'),
		'utf8'
	);
	const footer = readFileSync(
		resolve(ROOT, 'frontend', 'src', 'lib', 'components', 'SiteFooter.svelte'),
		'utf8'
	);

	expect(item).toContain('item.reader_note');
	expect(item).not.toContain('Brief');
	expect(footer).toContain(
		'We skipped {facts.items_failed} stories today because we could not read enough of the page to'
	);
});

/**
 * The home page is the one page every reader lands on, and its topic pills were
 * dead for as long as they have existed: the pills build their address from a
 * `datePrefix`, the dated routes pass one, and the root passed nothing - so
 * every pill pointed at `/<vertical>/`, a route this site does not have.
 *
 * Asserted by walking the links rather than by pinning the prefix, because the
 * defect was never the prefix. It was that nothing checked a link on the home
 * page went anywhere. A test that only pinned the attribute would pass the day
 * someone changed the route shape underneath it.
 */
test('every internal link on the home page goes somewhere', async ({ page }) => {
	await page.goto('/');

	const targets = await page
		.locator('main a[href], nav a[href]')
		.evaluateAll((links) =>
			links
				.map((link) => (link as HTMLAnchorElement).href)
				.filter((href) => href.startsWith(window.location.origin))
				.filter((href, index, all) => all.indexOf(href) === index)
		);

	expect(targets.length).toBeGreaterThan(0);

	const dead: string[] = [];
	for (const href of targets) {
		const response = await page.goto(href);
		if (!response || response.status() >= 400) {
			dead.push(`${href} -> ${response ? response.status() : 'no response'}`);
		}
	}

	expect(dead, `dead links on the home page:\n${dead.join('\n')}`).toEqual([]);
});
