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
