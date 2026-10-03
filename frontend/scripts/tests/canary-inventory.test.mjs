import assert from 'node:assert/strict';
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import test from 'node:test';
import { canaryFiles } from '../canary-inventory.mjs';

test('one generated run inventories named drawings and state shards, not stale drawings', () => {
	const root = mkdtempSync(join(tmpdir(), 'idhazh-canary-inventory-'));
	function write(name, value) {
		const path = join(root, ...name.split('/'));
		mkdirSync(dirname(path), { recursive: true });
		writeFileSync(path, value);
	}
	try {
		write('digest/2026/08/20/digest.json', JSON.stringify({
			items: [{ item_id: 'ai-05', visual: {
				state: 'rendered', data_path: 'digest/2026/08/20/ai-05.json'
			} }]
		}));
		write('digest/2026/08/20/ai-05.json', '{}');
		write('digest/2026/08/20/ai-16.json', '{}');
		write('publication.json', '{}');
		write('telemetry/2026/08.json', '{}');
		write('state/feed-health/2026/08/20.csv', 'utc_date\n2026-08-20\n');
		write('state/content-similarity-judge/fitted-thresholds/2026/08/20.csv', 'utc_date\n2026-08-20\n');
		write('state/content-similarity-judge/merge-line-holdout-scores/2026/08/20.csv', 'utc_date\n2026-08-20\n');
		write('state/unrelated/2026/08/20.csv', 'utc_date\n2026-08-20\n');
		assert.deepEqual(canaryFiles(root, join(root, 'state')), {
			publicFiles: [
				'digest/2026/08/20/ai-05.json',
				'digest/2026/08/20/digest.json',
				'telemetry/2026/08.json'
			],
			stateFiles: [
				'content-similarity-judge/fitted-thresholds/2026/08/20.csv',
				'content-similarity-judge/merge-line-holdout-scores/2026/08/20.csv',
				'feed-health/2026/08/20.csv'
			]
		});
	} finally {
		rmSync(root, { recursive: true, force: true });
	}
});
