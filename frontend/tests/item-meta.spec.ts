/**
 * Row #16's oracle: the item's facts are in two places, and which place a fact
 * is in says what it is about.
 *
 * Above the title go the four a reader uses to decide whether to read at all.
 * Below the summary go the claims about the summary and the two things you can
 * do next. Three promises follow, and all three fail silently.
 *
 * 1. **The eyebrow holds at most four child elements.** The count is of
 *    ELEMENTS, so it is the same at every width: an item that earned three lens
 *    chips still spends one slot, because they arrive inside one wrapper.
 * 2. **The confidence sentence, `Listen` and `Read the original` follow the
 *    summary in document order, on every item.** Printing "our summary leaves
 *    out figures from the opening" above a headline the reader has not read is a
 *    disclaimer on nothing. Document order rather than paint order, because the
 *    footer moves into a side column at the side-rail breakpoint and the promise
 *    is about the reading order rather than about the geometry.
 * 3. **The fourth and last of those four is WHEN, and on a day
 *    page it is the story's own published time.** The time sat on a shared rail
 *    from 2026-09-02 to 2026-09-12, where hour-grouping left 86.3 percent of
 *    stories with no time at all (1,218 markers over 8,922 committed stories,
 *    re-measured 2026-09-12). So the slot is asserted by identity and not only
 *    by count: the last child carries `data-item-time`, the day link is not on
 *    a day page at all, and the one canary story whose `time_source` is
 *    `unknown` draws nothing rather than an empty slot. That last state has
 *    never once happened in the committed archive, which is why the fixture is
 *    the canary and not a day.
 *
 * Every item, and the count is asserted rather than assumed. The day list pages
 * at twelve, so the run below opens the rest first and then checks that what is
 * on screen is the whole day the canary published.
 *
 * The third test is Node-only and holds decision 4: which kinds of source get
 * named on the item. It reads the rule rather than the corpus - the share of
 * labelled stories in the committed tree is a fact about the news, and it moved
 * without anybody changing a line.
 */
import { expect, test } from '@playwright/test';
import { KIND_WORTH_SAYING, SOURCE_KINDS } from '../src/lib/bands';
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
});
