/** Which browser specs remain when a run declines review pictures? */
import { expect, test } from '@playwright/test';
import { ignoredBrowserSpecs } from '../playwright.config';

test('declining pictures retains panel sufficiency and console behavior', () => {
	const ignored = ignoredBrowserSpecs(false, false, true);
	expect(ignored).toContain('**/panel-captures.spec.ts');
	expect(ignored).not.toContain('**/panel-sufficiency.spec.ts');
	expect(ignored).not.toContain('**/console.spec.ts');
});

test('an explicit review run restores pictures without restoring the whole-day spec', () => {
	const ignored = ignoredBrowserSpecs(false, false, false);
	expect(ignored).not.toContain('**/panel-captures.spec.ts');
	expect(ignored).toHaveLength(1);
	expect(ignored[0]).toEqual(/whole-day\.spec\.ts$/);
});

test('panel selection can still skip both panel specs', () => {
	const ignored = ignoredBrowserSpecs(true, true, false);
	expect(ignored).toContain('**/panel-captures.spec.ts');
	expect(ignored).toContain('**/panel-sufficiency.spec.ts');
	expect(ignored).toContain('**/console.spec.ts');
});
