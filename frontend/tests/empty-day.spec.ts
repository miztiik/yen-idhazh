import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { render } from 'svelte/server';
import { serverCompiler } from './support/server-render';
const ROOT = resolve(process.cwd(), '..');
test('the root empty state offers a way out that no later run can move', () => {
    const page = readFileSync(resolve(ROOT, 'frontend', 'src', 'routes', '+page.svelte'), 'utf8');
    const copy = readFileSync(resolve(ROOT, 'frontend', 'src', 'lib', 'components', 'EmptyDay.svelte'), 'utf8');
    // It used to name the newest day and link straight to it. That name is read
    // off the newest day on disk and the root layout handed it to every page,
    // so publishing rewrote the bytes of every older page carrying this panel.
    // `/` is the same destination under a name no later run can change, and
    // `day-states.spec.ts` holds the panel to two ways on.
    expect(page).not.toContain('data.latest');
    expect(copy).not.toContain('run notice above');
    expect(copy).not.toContain('Latest day -');
    expect(copy).toContain("Today's digest");
    expect(copy).toContain('All days');
});
test('the root load does not read the build clock', () => {
    const source = readFileSync(resolve(ROOT, 'frontend', 'src', 'routes', '+page.server.ts'), 'utf8');
    expect(source).not.toContain('new Date');
    // The date the page shows comes off the newest committed day and nothing
    // else. This used to assert `day?.date ?? latest`, which was the same rule
    // written as a fallback; since 2026-09-10 the load carries a seed rather than
    // a whole day, so there is no day object to read a date off and `latest` is
    // the only source there is.
    expect(source).toContain('latestDate()');
    expect(source).toContain('today: latest');
});
test('reader source limits are sentences in the page text', () => {
    const item = readFileSync(resolve(ROOT, 'frontend', 'src', 'lib', 'components', 'DigestItem.svelte'), 'utf8');
    expect(item).toContain('item.reader_note');
    expect(item).not.toContain('Brief');
});

test('the edition identifies published stories without reporting pipeline progress', async ({}, testInfo) => {
    const compile = serverCompiler(testInfo.outputPath('components'));
    const module = await compile('src/lib/components/DayNotice.svelte', 'DayNotice', [
        ['$lib/format', pathToFileURL(resolve('src', 'lib', 'format.ts')).href]
    ]);
    const component = (await import(pathToFileURL(module).href)).default;
    const day = {
        date: '2026-11-10',
        generated_at: '2026-11-10T16:55:00Z',
        items: [],
        partial: true,
        items_failed: 80,
        runs: [{ n: 2, at: '2026-11-10T15:00:00Z', items_added: 265 }]
    };
    const published = render(component, { props: { day, count: 327 } }).body;
    expect(published).toContain('10 November 2026');
    expect(published).toContain('327 stories');
    expect(published).toContain('Updated 16:55 UTC');
    expect(published).not.toContain('15:00');
    expect(published).not.toContain('did not finish');
    expect(published).not.toContain('added after');
    const empty = render(component, { props: { day: { ...day, generated_at: null }, count: 0 } }).body;
    expect(empty).toContain('No stories today');
    expect(empty).not.toContain('Updated');
    expect(empty).not.toContain('class="separator');
    const single = render(component, { props: { day, count: 1 } }).body;
    expect(single).toContain('1 story');
    expect(single).not.toContain('1 stories');
});
