/** Which colour token prints a column's engine type, so the type's family reads at a glance.
 *
 * The engine is DuckDB, and these are the names it prints for a column's type:
 * `VARCHAR`, `BIGINT`, `DECIMAL(18,4)`, `TIMESTAMP WITH TIME ZONE`, `VARCHAR[]`,
 * `STRUCT(a INTEGER)`. The label is painted with exactly the token returned
 * here. A list or a struct takes the tertiary colour whatever it holds, because
 * `timestamp[]` is a list rather than a time, and so does a name no rule knows.
 */

export const TYPE_COLOURS = ['--type-text', '--type-number', '--type-time', '--type-truth', '--color-text-tertiary'] as const;
export type TypeColour = (typeof TYPE_COLOURS)[number];

const LIST_OR_STRUCT = /\[\d*\]$|^(STRUCT|MAP|UNION)\(/;

const RULES: readonly (readonly [TypeColour, RegExp])[] = [
	['--type-text', /^(VARCHAR|UUID)$|^ENUM\(/],
	['--type-number', /^U?(TINYINT|SMALLINT|INTEGER|BIGINT|HUGEINT)$|^(BIGNUM|FLOAT|DOUBLE)$|^DECIMAL\(/],
	['--type-time', /^(DATE|INTERVAL|TIME|TIME_NS|TIMESTAMP|TIMESTAMP_S|TIMESTAMP_MS|TIMESTAMP_NS)$|^TIME(STAMP)? WITH TIME ZONE$/],
	['--type-truth', /^BOOLEAN$/]
];

export function typeColour(engineType: string): TypeColour {
	const type = engineType.trim().toUpperCase();
	if (LIST_OR_STRUCT.test(type)) return '--color-text-tertiary';
	return RULES.find(([, rule]) => rule.test(type))?.[0] ?? '--color-text-tertiary';
}
