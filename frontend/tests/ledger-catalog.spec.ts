/** Prove registry validation and consent on the named config and bounded mutations. */
import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { configuredCatalog } from '../src/lib/data/configured-catalog';
import { consentedSelection, parseLedgerCatalog } from '../src/lib/data/ledger-catalog';

function registry() {
	return JSON.parse(readFileSync(new URL('../../config/ledgers.json', import.meta.url), 'utf8'));
}

test('the catalog preserves grouped ownership and normalizes each checked prefix once', () => {
	const payload = registry();
	const catalog = parseLedgerCatalog(payload);
	expect(catalog.families.map((family) => family.name)).toEqual(payload.families.map((family: { name: string }) => family.name));
	for (const family of payload.families) {
		for (const entry of family.ledgers) {
			expect(catalog.require(entry.name)).toEqual({
				name: entry.name, grain: entry.grain, prefix: entry.prefix.join('/'),
				publish_to_data_explorer: entry.publish_to_data_explorer
			});
		}
	}
	expect(catalog.get('unregistered-ledger')).toBeUndefined();
	expect(() => catalog.require('unregistered-ledger')).toThrow(/does not register/);
	expect(Object.isFrozen(catalog)).toBe(true);
	expect(Object.isFrozen(catalog.entries)).toBe(true);
	expect(Object.isFrozen(catalog.families[0].ledgers)).toBe(true);
	expect(Object.isFrozen(catalog.entries[0])).toBe(true);
	payload.families[0].ledgers[0].prefix[0] = 'changed-after-parsing';
	expect(catalog.require('dispatches').prefix).toBe('feed-ingest-plan/dispatches');
});

test('native Node and browser-compatible imports validate the same committed catalog', () => {
	const output = execFileSync(process.execPath, ['--input-type=module', '-e',
		"import { configuredCatalog as c } from './src/lib/data/configured-catalog.ts'; console.log(JSON.stringify(c.entries));"
	], { cwd: process.cwd(), encoding: 'utf8' });
	expect(JSON.parse(output)).toEqual(configuredCatalog.entries);
});

test('a safe new runtime name resolves from the supplied catalog without a compiled name list', () => {
	const payload = registry();
	payload.families[0].ledgers.push({
		name: 'new-records', grain: 'raw-and-compact', prefix: ['feed-ingest-plan', 'new-records'],
		publish_to_data_explorer: false
	});
	expect(parseLedgerCatalog(payload).require('new-records').prefix).toBe('feed-ingest-plan/new-records');
});

const invalidConsent = [undefined, null, 0, 1, 'true', 'false', [], {}];
for (const value of invalidConsent) {
	test(`consent must be explicitly boolean, not ${JSON.stringify(value)}`, () => {
		const payload = registry();
		payload.families[0].ledgers[0].publish_to_data_explorer = value;
		expect(() => parseLedgerCatalog(payload)).toThrow(/publish_to_data_explorer.*boolean/);
	});
}

test('consent cannot enable a grain the compact reader cannot query', () => {
	const payload = registry();
	const entry = payload.families.flatMap((family: { ledgers: { name: string }[] }) => family.ledgers)
		.find((entry: { name: string }) => entry.name === 'score-distribution');
	entry.publish_to_data_explorer = true;
	expect(() => parseLedgerCatalog(payload)).toThrow(/not raw-and-compact/);
});

for (const prefix of [[], ['..'], ['.'], ['/absolute'], ['C:'], ['feed/dispatches'], ['feed\\dispatches'], [''], ['dispatches', 1], ['UPPER'], ['space here']]) {
	test(`unsafe prefix ${JSON.stringify(prefix)} is refused`, () => {
		const payload = registry();
		payload.families[0].ledgers[1].prefix = prefix;
		expect(() => parseLedgerCatalog(payload)).toThrow(/prefix/);
	});
}

test('duplicates, overlapping paths and family disagreements are refused before lookup', () => {
	const duplicateFamily = registry();
	duplicateFamily.families.push(duplicateFamily.families[0]);
	expect(() => parseLedgerCatalog(duplicateFamily)).toThrow(/duplicate family/);
	const duplicateLedger = registry();
	duplicateLedger.families[0].ledgers.push(duplicateLedger.families[0].ledgers[0]);
	expect(() => parseLedgerCatalog(duplicateLedger)).toThrow(/duplicate ledger/);
	const overlap = registry();
	overlap.families[0].ledgers[1].prefix = ['feed-ingest-plan', 'editorial-selections', 'dispatches'];
	expect(() => parseLedgerCatalog(overlap)).toThrow(/overlapping prefixes/);
	const misplaced = registry();
	misplaced.families[0].ledgers[1].prefix = ['elsewhere', 'dispatches'];
	expect(() => parseLedgerCatalog(misplaced)).toThrow(/family/);
	const wrongEnd = registry();
	wrongEnd.families[0].ledgers[1].prefix = ['feed-ingest-plan', 'wrong-name'];
	expect(() => parseLedgerCatalog(wrongEnd)).toThrow(/must end/);
	const selfFamily = registry();
	selfFamily.families[1].ledgers[0].prefix = ['run-shards', 'deep', 'run-shards'];
	expect(() => parseLedgerCatalog(selfFamily)).toThrow(/preserve its family/);
});

test('required family metadata, real dates, vocabularies and grain fields are validated', () => {
	for (const fields of [
		{ lifecycle_status: 'unknown' }, { description: '' }, { description: 'two\nlines' },
		{ name: '../unsafe' }, { onboarded: '2026-02-29' }, { onboarded: '2026-13-01' },
		{ onboarded: '0000-01-01' }, { onboarded: undefined }, { ledgers: [] }, { extra: true }
	]) {
		const payload = registry();
		Object.assign(payload.families[0], fields);
		expect(() => parseLedgerCatalog(payload), JSON.stringify(fields)).toThrow();
	}
	for (const fields of [
		{ name: 'BAD' }, { grain: 'unknown' }, { grain: undefined }, { prefix: undefined },
		{ stem: 'unexpected' }, { suffix: '.json' }, { extra: true }
	]) {
		const payload = registry();
		Object.assign(payload.families[0].ledgers[0], fields);
		expect(() => parseLedgerCatalog(payload), JSON.stringify(fields)).toThrow();
	}
});

test('paused and retired consent stays readable while disabled selections are removed with notice', () => {
	for (const status of ['paused', 'retired']) {
		const payload = registry();
		payload.families[0].lifecycle_status = status;
		const catalog = parseLedgerCatalog(payload);
		expect(consentedSelection(catalog, ['dispatches'])).toEqual({ names: ['dispatches'], notice: null });
		payload.families[0].ledgers[1].publish_to_data_explorer = false;
		const refreshed = parseLedgerCatalog(payload);
		expect(consentedSelection(refreshed, ['dispatches', 'host-fingerprint'])).toEqual({
			names: ['host-fingerprint'],
			notice: 'Removed ledgers not enabled for the Data explorer: dispatches.'
		});
		expect(consentedSelection(refreshed, ['unregistered-ledger']).names).toEqual([]);
	}
});
