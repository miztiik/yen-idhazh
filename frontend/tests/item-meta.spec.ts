/** Which publisher kinds should a reader see on a story? */
import { expect, test } from '@playwright/test';
import { KIND_WORTH_SAYING, SOURCE_KINDS, sourceKindCopy } from '../src/lib/bands';

test.describe('the item names the speaker only where the speaker has a stake', () => {
    test('four kinds, each with copy, and never the one that is most of the tree', () => {
        // Four kinds carry copy. `government` is a ministry announcing its own
        // policy and `research` is a paper nobody has reviewed - both a speaker
        // with something to gain, both arriving in a reporter's typeface until
        // 2026-09-01.
        //
        // Excluding `reporting` is the whole lever, and it is checked here rather
        // than by measuring the share of labelled stories in the committed tree.
        // That share moves when the news moves, so it went red on a day that
        // arrived rather than on a change that broke, and it read every published
        // day to say so (`CLAUDE.md` Guardrail #12).
        expect([...KIND_WORTH_SAYING].sort()).toEqual([
            'announcement',
            'community',
            'government',
            'research'
        ]);
        for (const kind of KIND_WORTH_SAYING) {
            expect(SOURCE_KINDS[kind], `${kind} has no copy to print`).toBeTruthy();
        }
        expect(KIND_WORTH_SAYING, 'labelling reporting would label most of the page').not.toContain('reporting');
    });

    test('a configured kind supplies its label and an old unknown kind stays explicit', () => {
        const kind = {
            id: 'independent-review', display_name: 'Independent review',
            status: 'active', retired_on: null, show_on_item: true,
            counts_as_reporting: false, requires_reporting_for_lead: true
        };
        expect(sourceKindCopy(kind.id, [kind])).toEqual({
            label: 'Independent review', showOnItem: true, registered: true
        });
        expect(sourceKindCopy('old-publisher-kind', [])).toEqual({
            label: 'old-publisher-kind (unregistered source kind)',
            showOnItem: true, registered: false
        });
    });
});
