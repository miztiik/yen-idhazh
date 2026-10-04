import { base } from '$app/paths';
import type { LedgerName } from '$lib/data/ledger';

export type RegistryLedger = {
	name: LedgerName;
	grain: string;
};
export type RegistryFamily = {
	name: string;
	lifecycle_status: string;
	description: string;
	onboarded: string;
	ledgers: RegistryLedger[];
};
export type LedgerRegistry = { families: RegistryFamily[] };

function named(value: unknown, where: string): string {
	if (typeof value !== 'string' || value.length === 0) throw new Error(`${where} is not a string`);
	return value;
}

function isLedgerName(name: unknown): name is LedgerName {
	return typeof name === 'string' && /^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$/.test(name);
}

function ledgerOf(raw: unknown, where: string): RegistryLedger {
	if (raw === null || typeof raw !== 'object') throw new Error(`${where} is not an object`);
	const held = raw as Record<string, unknown>;
	if (!isLedgerName(held.name)) throw new Error(`${where}.name is not a ledger name`);
	return { name: held.name, grain: named(held.grain, `${where}.grain`) };
}

function familyOf(raw: unknown, at: number): RegistryFamily {
	if (raw === null || typeof raw !== 'object') throw new Error(`families[${at}] is not an object`);
	const held = raw as Record<string, unknown>;
	if (!Array.isArray(held.ledgers) || held.ledgers.length === 0) {
		throw new Error(`families[${at}].ledgers is not a non-empty list`);
	}
	return {
		name: named(held.name, `families[${at}].name`),
		lifecycle_status: named(held.lifecycle_status, `families[${at}].lifecycle_status`),
		description: named(held.description, `families[${at}].description`),
		onboarded: named(held.onboarded, `families[${at}].onboarded`),
		ledgers: held.ledgers.map((ledger, index) => ledgerOf(ledger, `families[${at}].ledgers[${index}]`))
	};
}

export function flattenRegistry(registry: LedgerRegistry): RegistryLedger[] {
	return registry.families.flatMap((family) => family.ledgers);
}

export async function fetchRegistry(fetcher: typeof fetch = fetch): Promise<LedgerRegistry> {
	const response = await fetcher(`${base}/config/ledgers.json`, { cache: 'no-store' });
	if (!response.ok) throw new Error(`config/ledgers.json did not arrive (${response.status})`);
	const payload = await response.json();
	if (payload === null || typeof payload !== 'object' || !Array.isArray((payload as Record<string, unknown>).families)) {
		throw new Error('config/ledgers.json is not a ledger registry');
	}
	return { families: ((payload as Record<string, unknown>).families as unknown[]).map(familyOf) };
}
