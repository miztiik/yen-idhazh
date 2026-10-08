import { expect, test } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { copyFileSync, mkdirSync, rmSync, writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { rawListedThrough } from '../scripts/raw-listed-through.mjs';

const ROOT = resolve('test-results', 'raw-listed-through');

/** Stage one empty listing a day under `<staticRoot>/state/raw/<ledger>/index/`, as the site copy does. */
function stageListings(staticRoot: string, ledger: string, days: readonly string[]): void {
	const index = join(staticRoot, 'state', 'raw', ledger, 'index');
	mkdirSync(index, { recursive: true });
	for (const day of days) writeFileSync(join(index, `${day}.json`), '{}');
}

test('the newest staged raw listing is reported per ledger', () => {
	rmSync(ROOT, { recursive: true, force: true });
	mkdirSync(join(ROOT, 'state', 'raw', 'item-health', 'index'), { recursive: true });
	writeFileSync(join(ROOT, 'state', 'raw', 'item-health', 'index', '2026-09-05.json'), '{}');
	writeFileSync(join(ROOT, 'state', 'raw', 'item-health', 'index', '2026-09-06.json'), '{}');
	expect(rawListedThrough(ROOT)).toEqual({ 'item-health': '2026-09-06' });
});

test('a static folder with no staged listing names no day', () => {
	rmSync(ROOT, { recursive: true, force: true });
	mkdirSync(ROOT, { recursive: true });
	expect(rawListedThrough(ROOT)).toEqual({});
});

test('a static folder that is not there stops the build and names the folder', () => {
	expect(() => rawListedThrough(test.info().outputPath('no-static'))).toThrow(
		/^the static folder frontend\/test-results\/[^\\:]+\/no-static\/ is not there, so the build cannot say which raw days it listed$/
	);
});

test('THE ORACLE: called as the site build calls it, with no argument from frontend/, the script names each ledger\'s newest staged raw day', () => {
	const frontend = test.info().outputPath('frontend');
	const script = join(frontend, 'scripts', 'raw-listed-through.mjs');
	mkdirSync(join(frontend, 'scripts'), { recursive: true });
	copyFileSync(fileURLToPath(new URL('../scripts/raw-listed-through.mjs', import.meta.url)), script);
	stageListings(join(frontend, 'static'), 'item-health', ['2030-06-14', '2030-06-15']);
	stageListings(join(frontend, 'static'), 'seen', ['2030-06-12', '2030-06-13']);
	const baked = execFileSync(
		process.execPath,
		[
			'--input-type=module',
			'-e',
			`const { rawListedThrough } = await import(${JSON.stringify(pathToFileURL(script).href)}); process.stdout.write(JSON.stringify(rawListedThrough()));`
		],
		{ cwd: frontend, encoding: 'utf8' }
	);
	expect(JSON.parse(baked)).toEqual({ 'item-health': '2030-06-15', seen: '2030-06-13' });
});
