/** Which dated changes a chart can draw and read, from one declared rule. */
import type { DateStamp } from '../../data/ledger';
import type { ReadoutInput, ReadoutLine } from '../readout';

export interface RuleChange {
	readonly date: DateStamp;
	readonly kind: 'settings' | 'checker';
	readonly words: string;
}

export type ModelRule =
	| { readonly changes: readonly RuleChange[]; readonly note: string | null }
	| { readonly declined: string };

export const LEGACY_MODEL_RULE: ModelRule = {
	declined: 'This caller supplied no record of settings changes.'
};

export function checkedRule(rule: ModelRule): ModelRule {
	if ('declined' in rule) {
		if (rule.declined.trim().split(/\s+/).length < 5) {
			throw new Error('A declined model rule needs at least five words explaining why.');
		}
		return rule;
	}
	const seen = new Set<string>();
	for (const change of rule.changes) {
		if (!/^\d{4}-\d{2}-\d{2}$/.test(change.date)) throw new Error('A rule change needs a UTC date.');
		if (change.kind !== 'settings' && change.kind !== 'checker') throw new Error('A rule change needs settings or checker kind.');
		if (!change.words.trim()) throw new Error('A rule change needs words for its readout.');
		const key = `${change.date} ${change.kind}`;
		if (seen.has(key)) throw new Error(`Two model rule changes name ${key}.`);
		seen.add(key);
	}
	return rule;
}

export function ruleDeclaration(rule: ModelRule): { value: 'yes' | 'no'; none?: string } {
	checkedRule(rule);
	return 'declined' in rule ? { value: 'no', none: rule.declined } : { value: 'yes' };
}

export function ruleEvents(rule: ModelRule, dates: readonly string[]): NonNullable<ReadoutInput['events']> {
	checkedRule(rule);
	const lines = dates.map((date): ReadoutLine[] =>
		'declined' in rule ? [] : rule.changes.filter((change) => change.date === date).map((change) => ({
			label: change.kind === 'settings' ? 'Settings changed' : 'Checker changed',
			value: change.words,
			swatch: 'var(--color-text-tertiary)'
		}))
	);
	return { lines };
}

export interface RuleBoundary {
	date: string;
	x: number;
	kind: RuleChange['kind'];
}

export function ruleBoundaries(rule: ModelRule, dates: readonly string[], columns: readonly number[], left: number): RuleBoundary[] {
	checkedRule(rule);
	if ('declined' in rule) return [];
	return dates.flatMap((date, index) => {
		const changes = rule.changes.filter((change) => change.date === date);
		if (changes.length === 0) return [];
		return [{
			date,
			x: index === 0 ? left : (columns[index - 1] + columns[index]) / 2,
			kind: changes.some((change) => change.kind === 'settings') ? 'settings' as const : 'checker' as const
		}];
	});
}
