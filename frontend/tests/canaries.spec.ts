import { expect, test } from '@playwright/test';
import { existsSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { dayReady } from './support/day-ready';
/**
 * The injection canaries, asserted where a reader actually meets them.
 *
 * The backend suite proves the sanitizer strips an attack before it reaches a
 * payload. This suite assumes that failed. The day under test is built from the
 * RAW attack text, so every assertion here is about the published surface
 * itself: given markup in a title and a hostile URL in a summary, does the page
 * render words, or does it render a stranger's click target?
 *
 * That distinction is the whole reason this file exists. A suite that only
 * re-asserted the sanitizer would pass forever while the surface rotted.
 */
const CANARY_DIR = resolve(process.cwd(), '..', 'tests', 'fixtures', 'canaries');
interface Canary {
    name: string;
    attack: string;
    raw_title: string;
    raw_text: string;
    must_survive: string[];
    must_not_survive?: string[];
    must_not_render_as?: string[];
}
/** The canaries this day publishes, named rather than globbed.
 *
 * `backend/utilities/build_canary_day.py` names the same eight in
 * `DAY_CANARIES` and builds the day from that list, so this is the same
 * question asked on the other side. Reading the directory instead made this
 * suite's expectation depend on how many injection attacks the boundary suite
 * happens to hold, which is a different question: a sixth attack landed on
 * 2026-09-15 and turned four of these tests red without a line of the page
 * moving. An attack joins this list when somebody gives it a row on the day.
 *
 * The single browser case verifies its inputs and rendered content before
 * checking that hostile markup and addresses stayed inert. */
const REQUIRED = [
    'direct-instruction-override',
    'encoded-payload',
    'exfiltration-via-image-source',
    'exfiltration-via-url',
    'fake-system-delimiter',
    'instruction-to-the-browser-model',
    'markup-into-the-page',
    'tool-call-injection'
];
function load(): Canary[] {
    const found: Canary[] = [];
    for (const name of [...REQUIRED].sort((a, b) => a.localeCompare(b))) {
        for (const dir of [CANARY_DIR, join(CANARY_DIR, 'browser')]) {
            const path = join(dir, `${name}.json`);
            if (!existsSync(path))
                continue;
            found.push(JSON.parse(readFileSync(path, 'utf8')) as Canary);
            break;
        }
    }
    return found;
}
const CANARIES = load();
/** Why this file in particular cannot skip the wait.
 *
 * Until 2026-09-09 the document carried the head of its day, so a goto put the
 * stories on the page. One shell answers every dated address now and the day is
 * fetched - so every absence check in this file would pass on an empty page,
 * which is the one way a prompt-injection oracle can go quiet without anybody
 * noticing. The counter-oracles below are what catch that, and they need the
 * same wait.
 */
test.describe('the eight canaries, on the published surface', () => {
    test('planted markup rendered as words, not as elements', async ({ page }) => {
        expect(CANARIES.map((canary) => canary.name).sort()).toEqual([...REQUIRED].sort());
        // No exemption for a figure image, because from 2026-09-05 there is no
        // image on this page at all: a drawing is inlined whether the build put it
        // there or the browser fetched it. So any `img` under `main` is markup that
        // came from a stranger's page.
        //
        // The second query is the same rule at the carrier that replaced that
        // image. A drawing is markup in our own origin rather than a separate inert
        // document, so the parts of SVG that can run or fetch have to be absent
        // from the rendered page as well as refused before it is drawn (Guardrail #11).
        await page.goto('/2026-08-20/');
        await dayReady(page);
        await expect(page.locator('article.item')).toHaveCount(CANARIES.length);
        const planted = CANARIES.find((canary) => canary.name === 'markup-into-the-page');
        if (planted === undefined) throw new Error('The markup canary must be present');
        await expect(page.locator('main')).toContainText(planted.must_survive[0]);
        await expect(page.locator('main a[href="https://canary.example/markup-into-the-page"]')).toBeVisible();
        const smuggled = await page.evaluate(() => [
            ...document.querySelectorAll('main script, main iframe, main object, main embed, main img'),
            ...document.querySelectorAll('main svg script, main svg foreignObject, main svg image, main svg use, main svg a'),
            ...[...document.querySelectorAll('main svg *')].filter((node) => [...node.attributes].some((attribute) => attribute.name.startsWith('on')))
        ].map((node) => node.outerHTML));
        expect(smuggled).toEqual([]);
        const targets = await page.evaluate(() => {
            const hosts = ['collector.canary.example', 'collect.canary.example', 'collect-canary.example'];
            return [...document.querySelectorAll('*')].flatMap((node) =>
                ['href', 'src', 'srcset', 'action', 'formaction'].flatMap((attribute) => {
                    const value = node.getAttribute(attribute);
                    return value !== null && hosts.some((host) => value.includes(host))
                        ? [`${node.tagName}[${attribute}]=${value}`] : [];
                })
            );
        });
        expect(targets, 'attack text must never become a request or click target').toEqual([]);
    });
});
