import { expect, test } from '@playwright/test';
import { mkdirSync, readFileSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { loadDay, publishedDates } from '../src/lib/server/payload';
import type { PublicationInventory } from '../src/lib/server/publication';
const ROOT = resolve(process.cwd(), '..');
const PUBLISHED_INVENTORY_FIXTURE = resolve(ROOT, 'tests', 'fixtures', 'contracts', 'publication-inventory', 'published.json');
function writeNamedInventory(root: string, paths: string[], dates: string[]): void {
    const template = JSON.parse(readFileSync(PUBLISHED_INVENTORY_FIXTURE, 'utf8')) as PublicationInventory;
    const entries = paths.map((path) => ({
        root: 'public' as const,
        path,
        bytes: statSync(join(root, ...path.split('/'))).size,
        items: 0
    }));
    const inventory: PublicationInventory = {
        ...template,
        dates,
        entries,
        total_bytes: entries.reduce((sum, entry) => sum + entry.bytes, 0),
        total_items: 0
    };
    writeFileSync(join(root, 'publication.json'), `${JSON.stringify(inventory)}\n`);
}
const NEVER_PUBLISHED = '2001-09-11';
test.describe('a day whose payload is not there', () => {
    test('a missing payload has no day to load', () => {
        const root = test.info().outputPath('missing-day');
        expect(loadDay(NEVER_PUBLISHED, root), 'a day with no payload loaded anyway').toBeNull();
    });
});
test.describe('a day whose payload cannot be read', () => {
    /**
     * The build used to die here, and a build that dies publishes nothing.
     *
     * One unreadable file took down the whole site, including every other day in
     * the tree, so no reader ever reached a screen for it - which is the same as
     * not having designed one. The day now drops out and the reader meets the
     * quiet-day panel or the missing-day screen instead.
     *
     * The readable payload in the same tree is the control: without it this
     * passes on a loader that returns null for everything.
     */
    test('an unreadable payload drops its day instead of taking the build down', () => {
        const root = test.info().outputPath('unreadable-day');
        try {
            const digestRoot = join(root, 'digest');
            const readable = join(digestRoot, '2026', '01', '02');
            const corrupt = join(digestRoot, '2026', '01', '03');
            mkdirSync(readable, { recursive: true });
            mkdirSync(corrupt, { recursive: true });
            writeFileSync(join(readable, 'digest.json'), JSON.stringify({ date: '2026-01-02', items: [], verticals: [], runs: [] }));
            // Truncated mid-object, which is what an interrupted write leaves.
            writeFileSync(join(corrupt, 'digest.json'), '{"date": "2026-01-03", "items": [');
            writeNamedInventory(root, ['digest/2026/01/02/digest.json', 'digest/2026/01/03/digest.json'], ['2026-01-03', '2026-01-02']);
            expect(loadDay('2026-01-02', digestRoot)?.date, 'the control day did not load').toBe('2026-01-02');
            expect(loadDay('2026-01-03', digestRoot), 'an unreadable payload still throws').toBeNull();
            // It is still a published date, because the file is there. That is what
            // makes the day reachable and the screen necessary.
            expect(publishedDates(digestRoot)).toContain('2026-01-03');
        }
        finally {
            rmSync(root, { recursive: true, force: true });
        }
    });
    test('a payload that parses into something that is not a day drops too', () => {
        const root = test.info().outputPath('invalid-day');
        try {
            const day = join(root, '2026', '01', '04');
            mkdirSync(day, { recursive: true });
            // Valid JSON, no day in it. A parser is not a contract, and this one
            // used to arrive at the page as an object with no items on it - which
            // is a white screen rather than a designed one.
            writeFileSync(join(day, 'digest.json'), 'null');
            expect(loadDay('2026-01-04', root), 'a payload with no day in it still loads').toBeNull();
        }
        finally {
            rmSync(root, { recursive: true, force: true });
        }
    });
});
