/** Validate a grouped registry and derive its immutable, environment-independent lookup. */
export const LEDGER_GRAINS = ['flat', 'day', 'tree', 'stamp', 'raw-and-compact'] as const;
export const LEDGER_LIFECYCLE_STATUSES = ['active', 'paused', 'retired'] as const;
export const LEDGER_SEGMENT_PATTERN = '^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$';
export const LEDGER_CONFIG_FIELDS = ['families'] as const;
export const LEDGER_FAMILY_FIELDS = ['name', 'lifecycle_status', 'description', 'onboarded', 'ledgers'] as const;
export const LEDGER_ENTRY_FIELDS = ['name', 'grain', 'prefix', 'publish_to_data_explorer', 'stem', 'suffix'] as const;

export type LedgerCatalogEntry = Readonly<{
	name: string;
	grain: (typeof LEDGER_GRAINS)[number];
	prefix: string;
	publish_to_data_explorer: boolean;
}>;
export type LedgerCatalogFamily = Readonly<{
	name: string;
	lifecycle_status: (typeof LEDGER_LIFECYCLE_STATUSES)[number];
	description: string;
	onboarded: string;
	ledgers: readonly LedgerCatalogEntry[];
}>;
export type LedgerCatalog = Readonly<{
	families: readonly LedgerCatalogFamily[];
	entries: readonly LedgerCatalogEntry[];
	get: (name: string) => LedgerCatalogEntry | undefined;
	require: (name: string) => LedgerCatalogEntry;
}>;

const SEGMENT = new RegExp(LEDGER_SEGMENT_PATTERN);

function object(value: unknown, where: string, fields: readonly string[]): Record<string, unknown> {
	if (value === null || typeof value !== 'object' || Array.isArray(value)) throw new Error(`${where} is not an object`);
	for (const key of Object.keys(value)) {
		if (!fields.includes(key)) throw new Error(`${where}.${key} is not a registry field`);
	}
	return value as Record<string, unknown>;
}

function text(value: unknown, where: string): string {
	if (typeof value !== 'string' || value.length === 0) throw new Error(`${where} is not a non-empty string`);
	return value;
}

function segment(value: unknown, where: string): string {
	const name = text(value, where);
	if (!SEGMENT.test(name)) throw new Error(`${where} is not a safe name or prefix segment`);
	return name;
}

function vocabulary<T extends string>(value: unknown, values: readonly T[], where: string): T {
	const found = values.find((candidate) => candidate === value);
	if (found === undefined) throw new Error(`${where} is not one of ${values.join(', ')}`);
	return found;
}

function list(value: unknown, where: string, nonEmpty = true): unknown[] {
	if (!Array.isArray(value) || (nonEmpty && value.length === 0)) throw new Error(`${where} is not a ${nonEmpty ? 'non-empty ' : ''}list`);
	return value;
}

function onboarding(value: unknown, where: string): string {
	const day = text(value, where);
	const instant = Date.parse(`${day}T00:00:00Z`);
	if (!/^\d{4}-\d{2}-\d{2}$/.test(day) || day.startsWith('0000') ||
		!Number.isFinite(instant) || new Date(instant).toISOString().slice(0, 10) !== day) {
		throw new Error(`${where} is not a real UTC date`);
	}
	return day;
}

function entryOf(value: unknown, family: string, where: string): LedgerCatalogEntry {
	const held = object(value, where, LEDGER_ENTRY_FIELDS);
	const name = segment(held.name, `${where}.name`);
	const grain = vocabulary(held.grain, LEDGER_GRAINS, `${where}.grain`);
	const parts = list(held.prefix, `${where}.prefix`).map((part) => segment(part, `${where}.prefix`));
	if (typeof held.publish_to_data_explorer !== 'boolean') throw new Error(`${where}.publish_to_data_explorer must be a boolean`);
	if (held.publish_to_data_explorer && grain !== 'raw-and-compact') throw new Error(`${name} enables publish_to_data_explorer but is not raw-and-compact`);
	for (const key of ['stem', 'suffix'] as const) {
		const value = held[key];
		if (value !== undefined && value !== null && typeof value !== 'string') throw new Error(`${where}.${key} is not a string or null`);
		const needed = key === 'stem' ? grain === 'flat' : ['flat', 'day', 'stamp'].includes(grain);
		if (needed !== (value !== undefined && value !== null)) throw new Error(`${name}.${key} must be ${needed ? 'set' : 'null'}`);
	}
	if (parts[0] !== family) throw new Error(`${name} prefix does not start with family ${family}`);
	if (grain === 'raw-and-compact' && (parts.at(-1) !== name || (name === family && parts.length !== 1))) {
		throw new Error(`${name} raw-and-compact prefix must end with its name and preserve its family`);
	}
	return Object.freeze({ name, grain, prefix: parts.join('/'), publish_to_data_explorer: held.publish_to_data_explorer });
}

export function parseLedgerCatalog(payload: unknown): LedgerCatalog {
	const held = object(payload, 'registry', LEDGER_CONFIG_FIELDS);
	const names = new Map<string, LedgerCatalogEntry>();
	const familyNames = new Set<string>();
	const families = list(held.families, 'families', false).map((value, index) => {
		const where = `families[${index}]`;
		const family = object(value, where, LEDGER_FAMILY_FIELDS);
		const name = segment(family.name, `${where}.name`);
		if (familyNames.has(name)) throw new Error(`duplicate family ${name}`);
		familyNames.add(name);
		const lifecycle_status = vocabulary(family.lifecycle_status, LEDGER_LIFECYCLE_STATUSES, `${where}.lifecycle_status`);
		const description = text(family.description, `${where}.description`);
		if (/[\r\n]/.test(description)) throw new Error(`${where}.description must be one line`);
		const onboarded = onboarding(family.onboarded, `${where}.onboarded`);
		const ledgers = list(family.ledgers, `${where}.ledgers`).map((value, index) => {
			const entry = entryOf(value, name, `${where}.ledgers[${index}]`);
			if (names.has(entry.name)) throw new Error(`duplicate ledger ${entry.name}`);
			names.set(entry.name, entry);
			return entry;
		});
		return Object.freeze({ name, lifecycle_status, description, onboarded, ledgers: Object.freeze(ledgers) });
	});
	const entries = Object.freeze([...names.values()]);
	const compact = entries.filter((entry) => entry.grain === 'raw-and-compact');
	for (const left of compact) {
		for (const right of compact) {
			if (left !== right && (left.prefix === right.prefix || right.prefix.startsWith(`${left.prefix}/`))) {
				throw new Error(`overlapping prefixes for ${left.name} and ${right.name}`);
			}
		}
	}
	return Object.freeze({
		families: Object.freeze(families),
		entries,
		get: (name: string) => names.get(name),
		require(name: string) {
			const entry = names.get(name);
			if (entry === undefined) throw new Error(`registry does not register ledger ${JSON.stringify(name)}`);
			return entry;
		}
	});
}

/** Remove unavailable consent choices without treating a public registry as an access control. */
export function consentedSelection(catalog: LedgerCatalog, selected: readonly string[]): { names: string[]; notice: string | null } {
	const names = selected.filter((name) => catalog.get(name)?.publish_to_data_explorer === true);
	const removed = selected.filter((name) => !names.includes(name));
	return { names, notice: removed.length === 0 ? null : `Removed ledgers not enabled for the Data explorer: ${removed.join(', ')}.` };
}

export function offersExample(catalog: LedgerCatalog, example: { ledgers: readonly string[] }): boolean {
	return example.ledgers.every((name) => catalog.get(name)?.publish_to_data_explorer === true);
}
