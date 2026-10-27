/** Deterministic lenses rules over bounded fixtures; no browser, build, or layout matrix. */
import { expect, test } from '@playwright/test';
import { MAX_LENS_CHIPS, lensLabel, shownLenses } from '../src/lib/payload/lenses';
import taxonomy from '../../config/taxonomy.json' with { type: 'json' };

const lensIds = taxonomy.lenses.map((lens) => lens.id);
const unregisteredId = (existing: readonly string[]) => {
    let id = 'unregistered-lens';
    while (existing.includes(id)) id += '-x';
    return id;
};

test.describe('the chips, without a browser', () => {
    test('configured names follow the taxonomy and unknown ids remain visible', () => {
        expect(Object.fromEntries(taxonomy.lenses.map((lens) => [lens.id, lens.display_name])))
            .toEqual(expect.objectContaining(Object.fromEntries(lensIds.map((id) => [id, lensLabel(id)]))));
        const unknown = unregisteredId(lensIds);
        expect(shownLenses([unknown, ...lensIds])).toEqual([...lensIds, unknown].slice(0, MAX_LENS_CHIPS));
        expect(lensLabel(unknown)).toBe(unknown);
        expect(shownLenses(undefined)).toEqual([]);
        expect(shownLenses([])).toEqual([]);
    });
    test('the configured order chooses named ids before unknown ids', () => {
        const unknown = unregisteredId(lensIds);
        const shown = shownLenses([unknown, ...lensIds]);
        expect(shown).toEqual([...lensIds, unknown].slice(0, MAX_LENS_CHIPS));
    });
});
