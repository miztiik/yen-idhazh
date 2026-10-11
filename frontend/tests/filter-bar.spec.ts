/** Deterministic filter bar rules over bounded fixtures; no browser, build, or layout matrix. */
import { expect, test, type Page, type Request } from '@playwright/test';
import { filterNeedle, indexDay, shortlist } from '../src/lib/day-shape';
import type { DigestItem } from '../src/lib/payload/types';
function item(id: string, title: string, summary = ''): DigestItem {
    return {
        item_id: id,
        vertical: 'ai',
        title,
        source_url: `https://example.test/${id}`,
        source_id: 'test',
        source_name: 'Test',
        source_kind: 'reporting',
        published_at: null,
        summary,
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
function kept(items: DigestItem[], needle: string | null): DigestItem[] {
    return shortlist(indexDay(items), needle, null, new Set<string>(), '').visible;
}
test.describe('the filter rule', () => {
    test('a field narrows nothing until it holds enough to narrow by', () => {
        expect(filterNeedle('', 2)).toBeNull();
        expect(filterNeedle('a', 2)).toBeNull();
        expect(filterNeedle('  a  ', 2)).toBeNull();
        expect(filterNeedle('AI', 2)).toBe('ai');
        expect(filterNeedle('  Reactor ', 2)).toBe('reactor');
        expect(filterNeedle('', 0)).toBeNull();
        expect(filterNeedle('a', 1)).toBe('a');
    });
    test('the needle reads the title and the summary', () => {
        const items = [
            item('one', 'A reactor in Kerala'),
            item('two', 'Something else', 'the reactor is cooled by seawater'),
            item('three', 'Another thing', 'a second reactor is planned'),
            item('four', 'Nothing to do with it')
        ];
        expect(kept(items, 'reactor').map((story) => story.item_id)).toEqual([
            'one',
            'two',
            'three'
        ]);
        expect(kept(items, null)).toEqual(items);
    });
    test('the filter reads the list it is handed, never one captured earlier', () => {
        const seed = [item('one', 'A reactor in Kerala')];
        const whole = [...seed, item('two', 'A second reactor'), item('three', 'A pumpjack')];
        expect(kept(seed, 'reactor')).toHaveLength(1);
        expect(kept(whole, 'reactor'), 'the filter narrowed the seed rather than the day that arrived').toHaveLength(2);
        const index = indexDay(whole);
        expect(index.fields).toHaveLength(3);
        expect(index.at.get('three'), 'the index does not know where the day ends').toBe(2);
    });
});
class Watched {
    readonly urls: string[] = [];
    readonly offOrigin: string[] = [];
    take(request: Request): void {
        const url = new URL(request.url());
        this.urls.push(url.pathname);
        this.origins.push(url.origin);
    }
    readonly origins: string[] = [];
    strangers(page: Page): string[] {
        const mine = new URL(page.url()).origin;
        return [...new Set(this.origins.filter((origin) => origin !== mine))];
    }
    count(pattern: RegExp): number {
        return this.urls.filter((url) => pattern.test(url)).length;
    }
    distinct(pattern: RegExp): number {
        return new Set(this.urls.filter((url) => pattern.test(url))).size;
    }
}
