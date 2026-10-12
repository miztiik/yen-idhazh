/** Deterministic lenses rules over bounded fixtures; no browser, build, or layout matrix. */
import { expect, test } from '@playwright/test';
import { MAX_LENS_CHIPS, lensLabel, shownLenses } from '../src/lib/payload/lenses';
test.describe('the chips, without a browser', () => {
    test('an id the payload carries is kept, named or not', () => {
        expect(shownLenses(['ai-roi'])).toEqual(['ai-roi']);
        expect(shownLenses(['not-a-lens'])).toEqual(['not-a-lens']);
        expect(shownLenses(undefined)).toEqual([]);
        expect(shownLenses([])).toEqual([]);
    });
    test('a chip reads its committed name, and falls back to the raw id', () => {
        expect(lensLabel('china')).toBe('China');
        expect(lensLabel('ai-roi')).toBe('Return on AI investment');
        expect(lensLabel('supply-chain')).toBe('supply-chain');
    });
    test('a named id takes a slot before an unnamed one', () => {
        expect(shownLenses(['supply-chain', 'china'])).toEqual(['china', 'supply-chain']);
        expect(shownLenses(['supply-chain', 'war', 'china'])).toEqual(['china', 'war']);
    });
    test('more than the cap is cut, in configured order and not payload order', () => {
        const shown = shownLenses(['war', 'chips', 'china']);
        expect(shown).toHaveLength(MAX_LENS_CHIPS);
        expect(shown).toEqual(['chips', 'china']);
    });
});
