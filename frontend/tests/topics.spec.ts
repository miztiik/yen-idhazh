/** Deterministic topics rules over bounded fixtures; no browser, build, or layout matrix. */
import { expect, test } from '@playwright/test';
import { leadingStories, splitPills } from '../src/lib/day-shape';
import type { DigestItem, DigestLead, DigestVerticalRef } from '../src/lib/payload/types';
const MOVE_MIN = 2;
function ref(id: string, count: number): DigestVerticalRef {
    return { id, display_name: id.toUpperCase(), count };
}
function item(id: string, vertical: string): DigestItem {
    return {
        item_id: id,
        vertical,
        title: `Story ${id}`,
        source_url: `https://example.test/${id}`,
        source_id: 'test',
        source_name: 'Test',
        source_kind: 'reporting',
        published_at: null,
        summary: id,
        lenses: [],
        events: [],
        entities: [],
        band: 'high',
        band_reason: null,
        source_form: 'article',
        reader_note: null,
        truncated: false,
        visual: null,
        introduced_by_run: 1,
        updated_at: null
    };
}
function lead(id: string, reason: string): DigestLead {
    return { item_id: id, reason };
}
test('the leading block draws the day payload in the order it was given', () => {
    const items = [item('ai-1', 'ai'), item('world-1', 'world'), item('ai-2', 'ai')];
    const leads = [
        lead('ai-2', "Four of today's stories are about Nvidia."),
        lead('world-1', 'The lead story on our World desk.')
    ];
    const stories = leadingStories(leads, items);
    expect(stories.map((story) => story.item_id)).toEqual(['ai-2', 'world-1']);
    expect(stories[0].title).toBe('Story ai-2');
    expect(stories[0].reason).toBe("Four of today's stories are about Nvidia.");
});
test('a lead the page cannot reach is dropped, and the rest of the block still draws', () => {
    const stories = leadingStories([lead('ai-1', 'A reason.'), lead('ai-9', 'Another.')], [item('ai-1', 'ai')]);
    expect(stories.map((story) => story.item_id)).toEqual(['ai-1']);
});
test('a day with no block asks for nothing to be drawn', () => {
    expect(leadingStories([], [item('ai-1', 'ai')])).toEqual([]);
});
test('the topic row reads biggest first, and the active topic never folds away', () => {
    const verticals = [ref('ai', 9), ref('world', 4), ref('energy', 1)];
    const auto = new Set(['energy']);
    const split = splitPills(verticals, 'energy', 2, MOVE_MIN, auto);
    expect(split.shown.map((vertical) => vertical.id)).toEqual(['ai', 'world', 'energy']);
    expect(split.folded).toEqual([]);
    expect(splitPills(verticals, null, 2, MOVE_MIN, auto).folded.map((vertical) => vertical.id)).toEqual(['energy']);
});
const PREVIOUS_ORDER = [
    ref('ai', 9),
    ref('business-economy', 10),
    ref('energy', 30),
    ref('india', 8),
    ref('world', 40)
];
test('the topic row is a pure function of the payload', () => {
    const once = splitPills(PREVIOUS_ORDER, null, 5, MOVE_MIN);
    const twice = splitPills(PREVIOUS_ORDER, null, 5, MOVE_MIN);
    expect(once.shown.map((vertical) => vertical.id)).toEqual(twice.shown.map((vertical) => vertical.id));
    expect(once.shown.map((vertical) => vertical.id)[0]).toBe('world');
});
test('a desk ahead by the margin takes the front of the row', () => {
    const shown = splitPills(PREVIOUS_ORDER, null, 5, MOVE_MIN).shown;
    expect(shown.slice(0, 2).map((vertical) => vertical.id)).toEqual(['world', 'energy']);
});
test('a lead under the margin moves nothing, and that is the whole rule', () => {
    const shown = splitPills(PREVIOUS_ORDER, null, 5, MOVE_MIN).shown;
    expect(shown.map((vertical) => vertical.id)).toEqual([
        'world',
        'energy',
        'ai',
        'business-economy',
        'india'
    ]);
    expect(splitPills(PREVIOUS_ORDER, null, 5, 1).shown.map((vertical) => vertical.id)).toEqual([
        'world',
        'energy',
        'business-economy',
        'ai',
        'india'
    ]);
});
test('a curated desk is never folded away, and an auto-created one may be', () => {
    const verticals = [ref('ai', 40), ref('energy', 20), ref('india', 6), ref('world', 30)];
    const split = splitPills(verticals, null, 2, MOVE_MIN, new Set(['energy']));
    expect(split.shown.map((vertical) => vertical.id)).toEqual(['ai', 'world', 'india']);
    expect(split.folded.map((vertical) => vertical.id)).toEqual(['energy']);
    expect(split.shown.length).toBeGreaterThan(2);
});
test('the desk the reader is on stays on the row even when it was proposed', () => {
    const verticals = [ref('ai', 40), ref('energy', 1)];
    const split = splitPills(verticals, 'energy', 1, MOVE_MIN, new Set(['energy']));
    expect(split.shown.map((vertical) => vertical.id)).toEqual(['ai', 'energy']);
    expect(split.folded).toEqual([]);
});
