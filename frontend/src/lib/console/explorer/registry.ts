
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

function isLedgerName(name: unknown): name is LedgerName {
	return typeof name === 'string' && /^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$/.test(name);
}

export function flattenRegistry(registry: LedgerRegistry): RegistryLedger[] {
	return registry.families.flatMap((family) => family.ledgers);
}

export async function fetchRegistry(fetcher: typeof fetch = fetch): Promise<LedgerRegistry> {
	const response = await fetcher(`${base}/config/ledgers.json`, { cache: 'no-store' });
	if (!response.ok) throw new Error(`config/ledgers.json did not arrive (${response.status})`);
	const payload = await response.json();
	if (payload === null || typeof payload !== 'object' || !Array.isArray(payload.families)) {
		throw new Error('config/ledgers.json is not a ledger registry');
	}
	const families: RegistryFamily[] = payload.families.map((raw: any) => ({
		name: String(raw.name ?? ''),
		lifecycle_status: String(raw.lifecycle_status ?? ''),
		description: String(raw.description ?? ''),
		onboarded: String(raw.onboarded ?? ''),
		ledgers: Array.isArray(raw.ledgers)
			? raw.ledgers.filter((ledger: any) => isLedgerName(ledger.name)).map((ledger: any) => ({ name: ledger.name, grain: String(ledger.grain ?? '') }))
			: []
	}));
	return { families };
}
