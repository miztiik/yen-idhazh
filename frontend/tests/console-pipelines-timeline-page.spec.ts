/** Recorded endpoints, cumulative costs and article inspection survive the real browser handoff. */
import { expect, test } from './support/door-page';
import { THROUGH, packedPipelines, servePipelines, timedRow } from './support/pipelines-ledgers';

test('shard timings rank recorded windows and work independently, with articles on demand', async ({ page }) => {
	const errors: string[] = [];
	page.on('pageerror', (error) => errors.push(error.message));
	page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()); });
	page.on('response', (response) => { if (response.status() === 404) errors.push(`404 ${response.url()}`); });
	const shards = [2, 7, 11, 19, 31, 43, 59];
	const began = Date.parse(`${THROUGH}T00:00:00Z`);
	const rows = shards.flatMap((shard, index) => [0, 1].map((article) => {
		const start = began + index * 1000 + article * 2000;
		const cost = (shards.length - index) * 100;
		return timedRow(THROUGH, {
			run_id: `${THROUGH}-2`, item_id: `article-${shard}-${article}`, machine_shard: shard,
			item_started_at: new Date(start).toISOString(),
			item_ended_at: new Date(start + (index + 1) * 5000 + article * 1000).toISOString(),
			item_total_ms: 800 + cost, summarize_ms: 600 + cost, summary_ms: 430 + cost
		});
	}));
	const root = await packedPipelines('timeline-sparse-shards', [{ covers: THROUGH, rows }]);
	await servePipelines(page, root);
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
	await expect(panel).toHaveAttribute('data-timeline-shards', shards.join(' '));
	await expect(panel.locator('[data-timeline-coverage]')).toContainText(`${shards.length} shards with article records.`);
	await expect(panel.locator('[data-timeline-coverage]')).toContainText('Workers without linked article records are not listed.');
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
	await first.scrollIntoViewIfNeeded();
	await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
	await first.hover();
	const tooltip = page.locator('[data-chart-tooltip="run-timeline"]');
	await expect(tooltip).toBeVisible();
	await expect(tooltip.locator('strong')).toHaveText(`Shard ${longest.shard}`);
	await expect(tooltip).toContainText('Recorded window');
	await expect(tooltip).toContainText('Item work');
	await page.keyboard.press('Escape');
	await expect(tooltip).toHaveCount(0);

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
