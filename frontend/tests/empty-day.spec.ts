import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
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
    // The sentence moved to the day notice, which is where the day is. The
    // footer stated it on every route, including the ones that show no day.
    const notice = readFileSync(resolve(ROOT, 'frontend', 'src', 'lib', 'components', 'DayNotice.svelte'), 'utf8');
    expect(item).toContain('item.reader_note');
    expect(item).not.toContain('Brief');
    expect(notice).toContain('day.items_failed');
    expect(notice).toContain('did not finish.');
    expect(notice).not.toContain('could not read enough of the page');
});
