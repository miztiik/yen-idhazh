/** Deterministic item time rules over bounded fixtures; no browser, build, or layout matrix. */
import { expect, test } from '@playwright/test';
import { orderByTime } from '../src/lib/day-shape';
import { itemTime, type TimeForm } from '../src/lib/format';
import type { DigestItem } from '../src/lib/payload/types';
const RELATIVE = [
    /\bago\b/i,
    /\bjust now\b/i,
    /\bin \d/i,
    /\b(a|an|\d+)\s+(second|minute|hour|day|week|month|year)s?\b/i,
    /\bmoments?\b/i,
    /\byesterday\b/i,
    /\btoday\b/i,
    /\btomorrow\b/i
];
function refuseRelative(label: string, where: string): void {
    for (const form of RELATIVE) {
        expect(form.test(label), `${where} printed a relative time: "${label}"`).toBe(false);
    }
}
function story(id: string, at: string | null, source: string | null): DigestItem {
    return {
        item_id: id,
        vertical: 'ai',
        title: `Story ${id}`,
        source_url: `https://example.test/${id}`,
        source_id: 'test',
        source_name: 'Test',
        source_kind: 'reporting',
        published_at: at,
        time_source: source,
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
    } as DigestItem;
}
test.describe('the day runs newest first, and every time it prints is attributed', () => {
    test('the re-order keeps every story it was given, and never counts upward', () => {
        const day = '2026-08-20';
        const items = [
            story('ai-01', `${day}T06:20:00Z`, 'feed'),
            story('ai-02', null, 'unknown'),
            story('ai-03', `${day}T14:05:00Z`, 'feed'),
            story('ai-04', '2026-08-19T23:40:00Z', 'feed'),
            story('ai-05', `${day}T14:05:00Z`, 'first_seen'),
            story('ai-06', '2019-06-11T08:15:00Z', null),
            story('ai-07', null, null)
        ];
        const ordered = orderByTime(items);
        expect(ordered.length, 'the re-order changed the story count').toBe(items.length);
        expect(ordered.map((item) => item.item_id).sort(), 'the re-order changed which stories the day holds').toEqual(items.map((item) => item.item_id).sort());
        let seenUndated = false;
        for (let i = 0; i < ordered.length - 1; i += 1) {
            const here = ordered[i].published_at;
            const next = ordered[i + 1].published_at;
            if (here === null)
                seenUndated = true;
            expect(seenUndated && next !== null, `a dated story sits below an undated one at ${i}`).toBe(false);
            if (here !== null && next !== null) {
                expect(here >= next, `${here} is above ${next}, so the stream counts upward`).toBe(true);
            }
        }
    });
    test('every clock a payload can carry prints its own form', () => {
        const day = '2026-08-20';
        const cases: {
            at: string | null;
            source: string | null;
            form: TimeForm;
            label: string;
        }[] = [
            { at: `${day}T14:05:00Z`, source: 'feed', form: 'clock', label: '14:05' },
            { at: `${day}T14:05:00Z`, source: null, form: 'clock', label: '14:05' },
            { at: '2026-08-19T23:40:00Z', source: 'feed', form: 'dated', label: '08-19 23:40' },
            { at: '2026-08-19T23:40:00Z', source: null, form: 'dated', label: '08-19 23:40' },
            { at: '2026-06-11T08:15:00Z', source: null, form: 'dated', label: '06-11 08:15' },
            { at: '2019-06-11T08:15:00Z', source: null, form: 'dated', label: '2019-06-11 08:15' },
            { at: `${day}T06:20:00Z`, source: 'first_seen', form: 'first-seen', label: '06:20' },
            { at: null, source: 'unknown', form: 'none', label: '' }
        ];
        for (const one of cases) {
            const time = itemTime(one.at, one.source, day);
            const named = `${one.source ?? 'unrecorded'} at ${one.at ?? 'no time'}`;
            expect(time.label, named).toBe(one.label);
            expect(time.form, named).toBe(one.form);
            refuseRelative(time.label, named);
            expect(/[A-Za-z]/.test(time.label), `${named} prints a word`).toBe(false);
            expect(time.form === 'first-seen', named).toBe(one.source === 'first_seen');
            expect(time.form === 'none', named).toBe(!one.at);
            expect(time.label === '', named).toBe(!one.at);
        }
        expect([...new Set(cases.map((one) => one.form))].sort(), 'a form no case reaches is a branch with no test').toEqual(['clock', 'dated', 'first-seen', 'none']);
    });
    test('an unattributed stamp is drawn exactly like a feed stamp, and takes no mark', () => {
        const day = '2026-08-20';
        const attributed = itemTime(`${day}T14:05:00Z`, 'feed', day);
        const unattributed = itemTime(`${day}T14:05:00Z`, null, day);
        expect(unattributed, 'the unlabelled stamp is drawn differently from a feed stamp').toEqual(attributed);
        expect(unattributed.form, 'an unlabelled stamp took the first-seen mark').not.toBe('first-seen');
        expect(unattributed.label, 'an unlabelled stamp was blanked').not.toBe('');
    });
});
