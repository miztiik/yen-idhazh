import { expect, test } from '@playwright/test';
import { existsSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
/**
 * Installable, and nothing more than that.
 *
 * A manifest is a static JSON file. It adds no request, no account, and no code
 * running off the reader's device.
 *
 * The way this actually breaks is the base path. The site is served from a
 * GitHub Pages project path, a manifest that validates at the root 404s every
 * icon one directory up, and nothing on the page reports it. Every path here is
 * relative for that reason, and the test resolves them the way a browser would.
 */
const STATIC = resolve(process.cwd(), 'static');
interface Manifest {
    name: string;
    start_url: string;
    scope: string;
    theme_color: string;
    background_color: string;
    icons: {
        src: string;
        sizes: string;
        type: string;
        purpose: string;
    }[];
}
function manifest(): Manifest {
    return JSON.parse(readFileSync(join(STATIC, 'manifest.webmanifest'), 'utf8'));
}
test.describe('the web app manifest', () => {
    test('the committed manifest parses and names the app and its icons', () => {
        const m = manifest();
        expect(m.name).toBeTruthy();
        expect(m.icons.length).toBeGreaterThanOrEqual(2);
    });
    test('every relative icon resolves to a committed static asset', () => {
        // Resolved the way a browser resolves a relative src against the
        // manifest's own URL, which is what makes the project path a non-issue.
        for (const icon of manifest().icons) {
            expect(icon.src.startsWith('./'), `${icon.src} is not relative`).toBe(true);
            const path = join(STATIC, icon.src.replace(/^\.\//, ''));
            expect(existsSync(path), `${icon.src} is declared and missing`).toBe(true);
        }
    });
    test('it carries a maskable icon as well as a plain one', () => {
        const purposes = manifest().icons.map((i) => i.purpose);
        expect(purposes).toContain('any');
        // Without one, a platform crops the square icon and takes the ends off the
        // mark. A maskable icon is a different drawing, not a crop.
        expect(purposes).toContain('maskable');
    });
    test('start_url and scope survive a project path', () => {
        const m = manifest();
        for (const field of [m.start_url, m.scope]) {
            expect(field.startsWith('/'), 'an absolute path breaks under a project path').toBe(false);
        }
    });
    test('the apple-touch icon is a static asset, because Safari ignores the manifest for it', () => {
        expect(existsSync(join(STATIC, 'icons', 'apple-touch-icon.png'))).toBe(true);
    });
});
test.describe('what installability may not become', () => {
    test('the worker fetches nothing that is not our own origin', () => {
        const source = readFileSync(resolve(process.cwd(), 'src', 'service-worker.ts'), 'utf8');
        // Guardrail #1: a worker runs on the reader's device over files we already
        // serve. An absolute URL in it would be the one way that stops being true,
        // and the guard that keeps it true is read back here rather than trusted.
        expect(source.match(/https?:\/\/[^\s'"`]+/g) ?? [], 'the worker names an origin').toEqual([]);
        expect(source, 'the worker does not check the origin it is answering for').toContain('url.origin !== sw.location.origin');
    });
    test('the manifest asks for no messaging identity', () => {
        const raw = readFileSync(join(STATIC, 'manifest.webmanifest'), 'utf8');
        expect(raw).not.toContain('gcm_sender_id');
    });
});
