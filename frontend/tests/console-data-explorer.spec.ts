import { expect, test } from './support/browser';
import { CONSOLE_CHROMES, consoleChromeOf } from '../src/lib/console/chrome';
test('THE ORACLE: console chrome resolves to console unless the route asks for workbench', () => {
    expect(CONSOLE_CHROMES).toEqual(['console', 'workbench']);
    expect(consoleChromeOf(null)).toBe('console');
    expect(consoleChromeOf({})).toBe('console');
    expect(consoleChromeOf({ chrome: 'console' })).toBe('console');
    expect(consoleChromeOf({ chrome: 'workbench' })).toBe('workbench');
    expect(consoleChromeOf({ chrome: 'something-else' })).toBe('console');
});
