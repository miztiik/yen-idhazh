import { expect, test } from '@playwright/test';
import { mkdirSync, rmSync, writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { rawListedThrough } from '../scripts/raw-listed-through.mjs';

const ROOT = resolve('test-results', 'raw-listed-through');

test('the newest staged raw listing is reported per ledger', () => {
	rmSync(ROOT, { recursive: true, force: true });
	mkdirSync(join(ROOT, 'state', 'raw', 'item-health', 'index'), { recursive: true });
	writeFileSync(join(ROOT, 'state', 'raw', 'item-health', 'index', '2026-09-05.json'), '{}');
	writeFileSync(join(ROOT, 'state', 'raw', 'item-health', 'index', '2026-09-06.json'), '{}');
	expect(rawListedThrough(ROOT)).toEqual({ 'item-health': '2026-09-06' });
});

test('no staged listing names no day', () => {
	rmSync(ROOT, { recursive: true, force: true });
	expect(rawListedThrough(ROOT)).toEqual({});
});
