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

interface PublishedItem {
	item_id: string;
	source_form: string;
	truncated: boolean;
	reader_note: string | null;
}

/** Every item the canary day published, read off the payload the page renders. */
function publishedItems(date: string): PublishedItem[] {
	const [year, month, day] = date.split('-');
	const raw = readFileSync(join(CANARY, year, month, day, 'digest.json'), 'utf8');
	return (JSON.parse(raw) as { items: PublishedItem[] }).items;
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

test('the root empty state offers a way out that no later run can move', () => {
	const page = readFileSync(resolve(ROOT, 'frontend', 'src', 'routes', '+page.svelte'), 'utf8');
	const copy = readFileSync(
		resolve(ROOT, 'frontend', 'src', 'lib', 'components', 'EmptyDay.svelte'),
		'utf8'
	);

	// It used to name the newest day and link straight to it. That name is read
	// off the newest day on disk and the root layout handed it to every page,
	// so publishing rewrote the bytes of every older page carrying this panel.
	// `/` is the same destination under a name no later run can change, and
	// `day-states.spec.ts` holds the panel to two ways on.
	expect(page).not.toContain('data.latest');
	expect(copy).not.toContain('run notice above');
	expect(copy).not.toContain('Latest day -');
	expect(copy).toContain("Today's digest");
	expect(copy).toContain('All days');
});

test('the root load does not read the build clock', () => {
	const source = readFileSync(resolve(ROOT, 'frontend', 'src', 'routes', '+page.server.ts'), 'utf8');

	expect(source).not.toContain('new Date');
	// The date the page shows comes off the newest committed day and nothing
	// else. This used to assert `day?.date ?? latest`, which was the same rule
	// written as a fallback; since 2026-09-10 the load carries a seed rather than
	// a whole day, so there is no day object to read a date off and `latest` is
	// the only source there is.
	expect(source).toContain('latestDate()');
	expect(source).toContain('today: latest');
});

test('reader source limits are sentences in the page text', () => {
	const item = readFileSync(
		resolve(ROOT, 'frontend', 'src', 'lib', 'components', 'DigestItem.svelte'),
		'utf8'
	);
	// The sentence moved to the day notice, which is where the day is. The
	// footer stated it on every route, including the ones that show no day.
	const notice = readFileSync(
		resolve(ROOT, 'frontend', 'src', 'lib', 'components', 'DayNotice.svelte'),
		'utf8'
	);

	expect(item).toContain('item.reader_note');
	expect(item).not.toContain('Brief');
	expect(notice).toContain(
		'{day.items_failed} did not finish, because we could not read enough of the page to summarize'
	);
});

/**
 * Two source limits on one item, in one paragraph, in order.
 *
 * `reader_note` joins a sentence for each limit an item carries, and an item
 * that is both an abstract and cut carries two. Until the canary day published
 * one, that pair had a unit test and no page: measured 2026-08-29 over every
 * committed digest payload, no published item carries an abstract note at all.
 * The one sentence a reader would actually meet was the one nothing rendered.
 *
 * The item is found in the payload rather than named here, so the assertion
 * follows the fixture instead of pinning a position in it. What is pinned is the
 * sentence, because the sentence is the product.
 */
test('an item that is both an abstract and cut says both, in one paragraph', async ({ page }) => {
	const date = latestFixtureDay();
	const both = publishedItems(date).filter(
		(entry) => entry.source_form === 'abstract' && entry.truncated
	);

	// An assertion rather than a skip. A skip reads as nothing in a long pass
	// list, so a fixture that stopped carrying this item would switch the check
	// off in silence.
	expect(both, 'the canary day publishes no item that is both an abstract and cut').toHaveLength(
		1
	);
	expect(both[0].reader_note).toBe(
		"This is a summary of the paper's abstract. The full paper is a PDF. " +
			'We could only read the first 75 percent of this page.'
	);

	await page.goto(`/${date}/`);

	const article = page.locator(`article#${both[0].item_id}`);
	await expect(article, 'the day page renders no article for that item').toHaveCount(1);
	const note = article.locator('p').filter({ hasText: 'The full paper is a PDF.' });
	await expect(note, 'the item renders no reader note').toHaveCount(1);
	// One element holding both sentences. Split across two paragraphs, or either
	// sentence alone, and this fails.
	await expect(note).toHaveText(both[0].reader_note as string);
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
