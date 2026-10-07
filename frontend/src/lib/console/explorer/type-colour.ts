/** Which colour token prints a column's engine type, so the type's family reads at a glance.
 *
 * The family comes from `classifyType()`, which the answer table and the chart read too; this
 * file only says which token each family is printed in, and the label is painted with exactly
 * the token returned here. Whole numbers and decimals share the editor's number colour, every
 * date, time and interval shares one, and a list, a struct, a blob and a name no rule knows take
 * the tertiary colour - so `timestamp[]`, a list, is never painted as a time.
 */
import { classifyType, type TypeFamily } from './type-family';

export const TYPE_COLOURS = ['--type-text', '--type-number', '--type-time', '--type-truth', '--color-text-tertiary'] as const;
export type TypeColour = (typeof TYPE_COLOURS)[number];

const FAMILY_COLOURS: Record<TypeFamily, TypeColour> = {
	whole: '--type-number',
	decimal: '--type-number',
	date: '--type-time',
	timestamp: '--type-time',
	time: '--type-time',
	interval: '--type-time',
	truth: '--type-truth',
	text: '--type-text',
	bytes: '--color-text-tertiary',
	nested: '--color-text-tertiary',
	other: '--color-text-tertiary'
};

export function typeColour(engineType: string): TypeColour {
	return FAMILY_COLOURS[classifyType(engineType)];
}
