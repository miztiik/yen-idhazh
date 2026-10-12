import { expect, test } from './support/door-page';
import { type MovementPolarity } from '../src/lib/charts/theme';
/** The four cases, and the point of all four together.
 *
 * Rows one and three both paint GOOD and their signs are opposite, so no rule
 * that reads the sign alone can pass. Rows one and two share a sign and differ
 * in verdict, so no rule that ignores the sign can pass either.
 */
const CASES: {
    label: string;
    movement: number;
    polarity: MovementPolarity;
    wanted: string;
}[] = [
    { label: 'Time to write one', movement: -0.12, polarity: 'lower-is-better', wanted: 'good' },
    { label: 'Failed', movement: -0.12, polarity: 'higher-is-better', wanted: 'bad' },
    {
        label: 'Published items with a chart',
        movement: 0.12,
        polarity: 'higher-is-better',
        wanted: 'good'
    },
    { label: 'Numbers not in the article', movement: 0.12, polarity: 'lower-is-better', wanted: 'bad' },
    { label: 'Summary length', movement: 0.12, polarity: 'no-agreed-direction', wanted: 'neutral' },
    { label: 'Model minutes', movement: 0, polarity: 'lower-is-better', wanted: 'neutral' }
];
test.describe('a card painted from its polarity', () => {
    test('the cases below hold a falling good and a rising good', () => {
        // The whole reason this block exists. Without both, a rule that read the
        // sign alone would pass every case in the list.
        expect(CASES.some((item) => item.movement < 0 && item.wanted === 'good'), 'no falling measure paints good, so a sign rule would satisfy this file').toBe(true);
        expect(CASES.some((item) => item.movement > 0 && item.wanted === 'good'), 'no rising measure paints good, so a sign rule would satisfy this file').toBe(true);
    });
});
