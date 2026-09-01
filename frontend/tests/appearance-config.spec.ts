/** The appearance config's read-side migration, driven in both directions.
 *
 * `config/appearance.json` was split off `config/idhazh.json` on 2026-08-29.
 * The move is only safe if a checkout that has not been migrated resolves to
 * exactly what it resolved to before, so that is what this file proves. The
 * fixtures set every field to a NON-DEFAULT value: a merge that always
 * returned the defaults would pass a fixture built from them and fail here.
 */

import { expect, test } from '@playwright/test';
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { mergeLayers } from '../src/lib/server/config';

const REPO = join(dirname(fileURLToPath(import.meta.url)), '..', '..');

interface Knobs {
	sections: string[];
	archive_page_size: number;
	show_filter: boolean;
	tagline: string;
}

const DEFAULTS: Knobs = {
	sections: ['notice', 'leads', 'topics', 'items'],
	archive_page_size: 25,
	show_filter: true,
	tagline: 'A daily digest that checks its own work.'
};

/** Nothing here equals a default. That is what stops a stub from passing. */
const CHOSEN: Knobs = {
	sections: ['items', 'topics'],
	archive_page_size: 9,
	show_filter: false,
	tagline: 'Chosen, not defaulted.'
};

test.describe('the appearance config migration', () => {
	test('an unmigrated checkout resolves to what the new file resolves to', () => {
		// Before the split: every knob in the legacy block, no appearance file.
		const before = mergeLayers(DEFAULTS, CHOSEN, undefined);
		// After the split: every knob in the new file, legacy block deleted.
		const after = mergeLayers(DEFAULTS, undefined, CHOSEN);

		expect(before).toEqual(after);
		expect(before).toEqual(CHOSEN);
		// And neither is the default, so the assertion above has teeth.
		expect(before).not.toEqual(DEFAULTS);
	});

	test('the new file wins a field the legacy block also sets', () => {
		const resolved = mergeLayers(DEFAULTS, { archive_page_size: 4 }, { archive_page_size: 7 });
		expect(resolved.archive_page_size).toBe(7);
	});

	test('a legacy value survives a new file that does not mention it', () => {
		// The reason the legacy block is a middle layer and not a discarded one:
		// a partly migrated file must not snap a knob back to a default nobody
		// chose.
		const resolved = mergeLayers(DEFAULTS, CHOSEN, { archive_page_size: 7 });
		expect(resolved.tagline).toBe(CHOSEN.tagline);
		expect(resolved.show_filter).toBe(false);
		expect(resolved.archive_page_size).toBe(7);
	});

	test('a fresh clone with neither file runs on the defaults', () => {
		expect(mergeLayers(DEFAULTS, undefined, undefined)).toEqual(DEFAULTS);
	});
});

test.describe('the committed appearance file', () => {
	test('exists and carries every block the surface is drawn from', () => {
		const path = join(REPO, 'config', 'appearance.json');
		expect(existsSync(path)).toBe(true);
		const parsed = JSON.parse(readFileSync(path, 'utf8')) as Record<string, unknown>;
		for (const block of [
			'digest',
			'console',
			'assist',
			'frame',
			'theme',
			'chart',
			'icons',
			'motion',
			'version'
		]) {
			expect(parsed, `config/appearance.json is missing ${block}`).toHaveProperty(block);
		}
	});

	test('the frame is wide enough to be a frame, and the console is wider', () => {
		// The bounds live in the Pydantic contract and are enforced at build
		// time. This asserts the COMMITTED values sit inside them, so a hand
		// edit that skipped the contract still fails a gate.
		const parsed = JSON.parse(
			readFileSync(join(REPO, 'config', 'appearance.json'), 'utf8')
		) as { frame: { reading_max_px: number; console_max_px: number; measure_ch: number } };

		expect(parsed.frame.reading_max_px).toBeGreaterThanOrEqual(960);
		expect(parsed.frame.console_max_px).toBeGreaterThanOrEqual(parsed.frame.reading_max_px);
		expect(parsed.frame.measure_ch).toBeGreaterThanOrEqual(52);
		expect(parsed.frame.measure_ch).toBeLessThanOrEqual(80);
	});

	test('the server draws a chart no wider than its container can ever be', () => {
		// A server that prerenders wider than the frame is wrong on every first
		// paint and self-corrects only once a script runs, which is the one
		// moment a static site is supposed to be already finished.
		const parsed = JSON.parse(
			readFileSync(join(REPO, 'config', 'appearance.json'), 'utf8')
		) as { frame: { console_max_px: number }; chart: { width_px: number } };

		expect(parsed.chart.width_px).toBeLessThanOrEqual(parsed.frame.console_max_px);
	});
});
