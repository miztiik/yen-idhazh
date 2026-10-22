import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { checkStatement } from '../src/lib/data/statement';
import { consoleConfig, explorerConfig } from '../src/lib/server/config';
import { parseLedgerCatalog, offersExample } from '../src/lib/data/ledger-catalog';

/**
 * Can every configured Data explorer example be run as written?
 *
 * Each example in `console.explorer_examples` is held to what the page checks before it runs a
 * question: one read-only statement inside the character limit, ledgers the registry
 * `config/ledgers.json` lists, and a span that is one of `console.window_presets`. Whether an
 * example finds rows is a fact about the data on a given day, so no test here asks it.
 */

const repo = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');

/** Every ledger the registry lists, read from the one config file that lists them. */
function registered(): Set<string> {
	const registry = JSON.parse(readFileSync(path.join(repo, 'config', 'ledgers.json'), 'utf8')) as { families: { ledgers: { name: string }[] }[] };
	return new Set(registry.families.flatMap((family) => family.ledgers.map((ledger) => ledger.name)));
}

test('every configured example is one read-only statement the page will run', () => {
	const explorer = explorerConfig();
	expect(explorer.examples.length, 'no example is configured, so this proves nothing').toBeGreaterThan(0);
	for (const example of explorer.examples) {
		expect(checkStatement(example.sql, explorer.query_max_chars).refusal, `${example.id} is refused`).toBeNull();
	}
});

test('every configured example names only registered ledgers and uses a configured preset', () => {
	const ledgers = registered();
	const presets = consoleConfig().window_presets;
	for (const example of explorerConfig().examples) {
		expect(example.ledgers.length, `${example.id} names no ledger`).toBeGreaterThan(0);
		expect(example.ledgers.filter((ledger) => !ledgers.has(ledger)), `${example.id} names a ledger the registry does not list`).toEqual([]);
		expect(presets, `${example.id} asks for ${example.days} days, which is not a preset`).toContain(example.days);
	}
});

test('offered examples require every ledger consent but not available data or an active family', () => {
	const payload = JSON.parse(readFileSync(path.join(repo, 'config', 'ledgers.json'), 'utf8'));
	const example = explorerConfig().examples.find((example) => offersExample(parseLedgerCatalog(payload), example));
	expect(example, 'at least one configured example must be offered').toBeDefined();
	if (example === undefined) throw new Error('No consented example');
	for (const family of payload.families) family.lifecycle_status = 'retired';
	expect(offersExample(parseLedgerCatalog(payload), example)).toBe(true);
	for (const family of payload.families) {
		for (const entry of family.ledgers) {
			if (entry.name === example.ledgers[0]) entry.publish_to_data_explorer = false;
		}
	}
	expect(offersExample(parseLedgerCatalog(payload), example)).toBe(false);
	expect(offersExample(parseLedgerCatalog(payload), { ledgers: ['unregistered-ledger'] })).toBe(false);
});