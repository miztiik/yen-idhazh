/** Deterministic item time rules over bounded fixtures; no browser, build, or layout matrix. */
import { expect, test } from '@playwright/test';
import { orderByTime } from '../src/lib/day-shape';
import { itemTime, type TimeForm } from '../src/lib/format';
import type { DigestItem } from '../src/lib/payload/types';
import { trackUtcDay, type UtcDayRuntime } from '../src/lib/track-utc-day';
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
            { at: `${day}T14:05:00Z`, source: 'feed', form: 'clock', label: '14:05 UTC' },
            { at: `${day}T14:05:00Z`, source: null, form: 'clock', label: '14:05 UTC' },
            { at: '2026-08-19T23:40:00Z', source: 'feed', form: 'dated', label: '19 Aug 2026 23:40 UTC' },
            { at: '2026-08-19T23:40:00Z', source: null, form: 'dated', label: '19 Aug 2026 23:40 UTC' },
            { at: '2026-06-11T08:15:00Z', source: null, form: 'dated', label: '11 Jun 2026 08:15 UTC' },
            { at: '2019-06-11T08:15:00Z', source: null, form: 'dated', label: '11 Jun 2019 08:15 UTC' },
            { at: `${day}T06:20:00Z`, source: 'first_seen', form: 'first-seen', label: '06:20 UTC' },
            { at: '2026-08-19T23:40:00Z', source: 'first_seen', form: 'first-seen', label: '19 Aug 2026 23:40 UTC' },
            { at: `${day}T14:05:00Z`, source: 'unknown', form: 'none', label: '' },
            { at: null, source: 'unknown', form: 'none', label: '' }
        ];
        for (const one of cases) {
            const time = itemTime(one.at, one.source, day, day);
            const named = `${one.source ?? 'unrecorded'} at ${one.at ?? 'no time'}`;
            expect(time.label, named).toBe(one.label);
            expect(time.form, named).toBe(one.form);
            refuseRelative(time.label, named);
            const hasTime = Boolean(one.at) && one.source !== 'unknown';
            expect(time.label.endsWith(' UTC'), `${named} identifies its timezone`).toBe(hasTime);
            expect(time.form === 'first-seen', named).toBe(one.source === 'first_seen');
            expect(time.form === 'none', named).toBe(!hasTime);
            expect(time.label === '', named).toBe(!hasTime);
        }
        expect([...new Set(cases.map((one) => one.form))].sort(), 'a form no case reaches is a branch with no test').toEqual(['clock', 'dated', 'first-seen', 'none']);
    });
    test('only an article and edition both on actual UTC today omit the full date', () => {
        const cases: {
            at: string;
            edition: string;
            today: string | null;
            label: string;
        }[] = [
            { at: '2026-11-16T06:20:00Z', edition: '2026-11-16', today: '2026-11-16', label: '06:20 UTC' },
            { at: '2026-11-15T23:30:00Z', edition: '2026-11-15', today: '2026-11-16', label: '15 Nov 2026 23:30 UTC' },
            { at: '2026-11-15T23:46:00Z', edition: '2026-11-16', today: '2026-11-16', label: '15 Nov 2026 23:46 UTC' },
            { at: '2026-11-16T00:00:00Z', edition: '2026-11-15', today: '2026-11-16', label: '16 Nov 2026 00:00 UTC' },
            { at: '2026-11-16T06:20:00Z', edition: '2026-11-16', today: null, label: '16 Nov 2026 06:20 UTC' },
            { at: '2026-12-31T23:59:00Z', edition: '2026-12-31', today: '2027-01-01', label: '31 Dec 2026 23:59 UTC' },
            { at: '2027-01-01T00:00:00Z', edition: '2027-01-01', today: '2027-01-01', label: '00:00 UTC' },
            { at: '2027-01-01T00:00:00Z', edition: '2027-01-01', today: '2027-01-02', label: '01 Jan 2027 00:00 UTC' }
        ];
        for (const one of cases) {
            expect(itemTime(one.at, 'feed', one.edition, one.today).label,
                `${one.at} in edition ${one.edition}, read on ${one.today ?? 'no browser clock'}`)
                .toBe(one.label);
        }
    });
    test('an unattributed stamp is drawn exactly like a feed stamp, and takes no mark', () => {
        const day = '2026-08-20';
        for (const today of [day, '2026-08-21', null]) {
            const attributed = itemTime(`${day}T14:05:00Z`, 'feed', day, today);
            const unattributed = itemTime(`${day}T14:05:00Z`, null, day, today);
            expect(unattributed, 'the unlabelled stamp is drawn differently from a feed stamp').toEqual(attributed);
            expect(unattributed.form, 'an unlabelled stamp took the first-seen mark').not.toBe('first-seen');
            expect(unattributed.label, 'an unlabelled stamp was blanked').not.toBe('');
        }
    });
    test('the mounted UTC day refreshes at midnight and resume, and stops on teardown', () => {
        let now = Date.parse('2026-12-31T23:59:59.500Z');
        let sequence = 0;
        const scheduled = new Map<number, { run: () => void; delayMs: number }>();
        const runtime: UtcDayRuntime = {
            now: () => now,
            schedule(run, delayMs) {
                const id = ++sequence;
                scheduled.set(id, { run, delayMs });
                return () => { scheduled.delete(id); };
            },
            page: new EventTarget(),
            document: new EventTarget()
        };
        const days: string[] = [];
        const labels: string[] = [];
        const stop = trackUtcDay((today) => {
            days.push(today);
            labels.push(itemTime('2026-12-31T23:30:00Z', 'feed', '2026-12-31', today).label);
        }, runtime);

        expect(days).toEqual(['2026-12-31']);
        expect(labels).toEqual(['23:30 UTC']);
        expect(scheduled.size, 'one reading page owns one midnight timer').toBe(1);
        expect([...scheduled.values()][0].delayMs, 'the next UTC midnight is half a second away').toBe(500);
        runtime.page.dispatchEvent(new Event('focus'));
        expect(days, 'same-day focus does not publish a second day').toEqual(['2026-12-31']);
        expect(scheduled.size, 'focus replaces rather than adds a timer').toBe(1);

        now = Date.parse('2027-01-01T00:00:00Z');
        const [id, midnight] = [...scheduled.entries()][0];
        scheduled.delete(id);
        midnight.run();
        expect(days).toEqual(['2026-12-31', '2027-01-01']);
        expect(labels.at(-1), 'the open edition becomes dated across the year boundary')
            .toBe('31 Dec 2026 23:30 UTC');

        const resumes = [
            { at: '2027-01-03T08:15:00Z', target: runtime.document, event: 'visibilitychange' },
            { at: '2027-01-04T08:15:00Z', target: runtime.page, event: 'pageshow' },
            { at: '2027-01-05T08:15:00Z', target: runtime.page, event: 'focus' }
        ];
        for (const resume of resumes) {
            now = Date.parse(resume.at);
            resume.target.dispatchEvent(new Event(resume.event));
            expect(days.at(-1), 'resume reads actual UTC today after delayed background timers')
                .toBe(resume.at.slice(0, 10));
            expect(scheduled.size, 'resume retains one midnight timer').toBe(1);
            expect([...scheduled.values()][0].delayMs, 'resume schedules the next UTC midnight')
                .toBe(Date.parse(`${resume.at.slice(0, 10)}T23:59:59.999Z`) + 1 - now);
        }

        const queued = [...scheduled.values()][0].run;
        const published = days.length;
        stop();
        expect(scheduled.size, 'unmount cancels the midnight timer').toBe(0);
        now = Date.parse('2027-01-06T08:15:00Z');
        for (const resume of resumes) resume.target.dispatchEvent(new Event(resume.event));
        queued();
        expect(days.length, 'neither lifecycle events nor a queued callback update an unmounted reader').toBe(published);
        expect(scheduled.size).toBe(0);
    });
});
