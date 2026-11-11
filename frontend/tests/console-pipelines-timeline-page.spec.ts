/** Recorded endpoints, cumulative costs and article inspection survive the real browser handoff. */
import { expect, test } from './support/door-page';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import type { Row } from '../src/lib/data/ledger';
import { newestRunRows } from '../src/lib/console/queries/shared';

test('shard timings rank recorded windows and work independently, with articles on demand', async ({ page }) => {
	const errors: string[] = [];
	page.on('pageerror', (error) => errors.push(error.message));
	page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()); });
	page.on('response', (response) => { if (response.status() === 404) errors.push(`404 ${response.url()}`); });
	const answer = JSON.parse(readFileSync(resolve('..', 'tests', 'fixtures', 'console', 'pipelines', 'runTimelineQuery.json'), 'utf8'));
	const rows = newestRunRows(answer.rows as Row[]);
	const shards = [...new Set(rows.map((row) => Number(row.machine_shard)))];
	const zero = Math.min(...rows.map((row) => Date.parse(String(row.item_started_at))));
	const end = Math.max(...rows.map((row) => Date.parse(String(row.item_ended_at))));
	const expected = shards.map((shard) => {
		const own = rows.filter((row) => Number(row.machine_shard) === shard);
		const start = Math.min(...own.map((row) => Date.parse(String(row.item_started_at))));
		const finished = Math.max(...own.map((row) => Date.parse(String(row.item_ended_at))));
		return { shard, start: start - zero, elapsed: finished - start,
			work: own.reduce((sum, row) => sum + Number(row.item_total_ms), 0), count: own.length };
	});

	await page.goto('/console/');
	const panel = page.locator('[data-run-timeline]');
	await expect(panel).toHaveAttribute('data-timeline-view', 'elapsed');
	await expect(panel).toHaveAttribute('data-timeline-span-ms', String(end - zero));
	await expect(panel.locator('[data-timeline-bar]')).toHaveCount(shards.length);
	await expect(panel).not.toContainText('Items at once');
	const drawn = () => panel.locator('[data-timeline-bar]').evaluateAll((bars) => bars.map((bar) => ({
		shard: Number(bar.getAttribute('data-timeline-shard')),
		value: Number(bar.getAttribute('data-timeline-value-ms')),
		start: Number(bar.getAttribute('data-timeline-start-ms'))
	})));
	expect(await drawn()).toEqual([...expected].sort((a, b) => b.elapsed - a.elapsed || a.shard - b.shard)
		.map((row) => ({ shard: row.shard, value: row.elapsed, start: row.start })));
	const first = panel.locator('[data-timeline-bar]').first();
	const track = await first.locator('.track').boundingBox();
	const fill = await first.locator('.fill').boundingBox();
	if (track === null || fill === null) throw new Error('The recorded interval has no drawn geometry.');
	const longest = [...expected].sort((a, b) => b.elapsed - a.elapsed || a.shard - b.shard)[0];
	expect(Math.abs(fill.width - track.width * longest.elapsed / (end - zero))).toBeLessThan(1);
	expect(Math.abs(fill.x - track.x - track.width * longest.start / (end - zero))).toBeLessThan(1);

	await panel.locator('[data-shape-option="work"]').click();
	await expect(panel).toHaveAttribute('data-timeline-view', 'work');
	const byWork = [...expected].sort((a, b) => b.work - a.work || a.shard - b.shard);
	expect(await drawn()).toEqual(byWork.map((row) => ({ shard: row.shard, value: row.work, start: 0 })));
	const inspected = byWork.find((row) => row.count > 1);
	if (inspected === undefined) throw new Error('Article ordering needs a shard with more than one article.');
	await panel.locator(`[data-timeline-shard="${inspected.shard}"]`).getByRole('button').click();
	const details = panel.locator('[data-timeline-details]');
	await expect(details).toHaveAttribute('open', '');
	await expect(details.locator('summary').first()).toContainText(`Shard ${inspected.shard}`);
	await expect(details.locator('[data-timeline-item]')).toHaveCount(inspected.count);
	const costs = await details.locator('[data-timeline-item]').evaluateAll((items) =>
		items.map((item) => Number(item.getAttribute('data-timeline-item-work-ms'))));
	expect(costs).toEqual([...costs].sort((a, b) => b - a));
	await details.getByLabel('Article order').selectOption('start');
	const starts = await details.locator('[data-timeline-item]').evaluateAll((items) =>
		items.map((item) => Number(item.getAttribute('data-timeline-item-start-ms'))));
	expect(starts).toEqual([...starts].sort((a, b) => a - b));
	await details.locator('[data-timeline-item]').first().locator('summary').click();
	await expect(details.locator('[data-timeline-item]').first()).toContainText('Parked queue wait');
	await expect(details.locator('[data-timeline-item]').first()).toContainText('Call readings are details within the model stage');

	await page.goto('/');
	await expect(page.locator('main')).toBeVisible();
	expect(errors).toEqual([]);
});
