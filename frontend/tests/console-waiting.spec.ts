/** Do ledger waiting words preserve the distinction between no rows and a failed read? */
import { expect, test } from '@playwright/test';
import { emptyState, recordEmptyState } from '../src/lib/charts/d3/empty';
import { recordWindowSentence, routeStanding, STATE_WORDS } from '../src/lib/console/waiting';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { render } from 'svelte/server';
import { serverCompiler } from './support/server-render';

test('each settled ledger state has its own words and only failure takes warning tint', () => {
	expect(STATE_WORDS).toEqual({
		quiet: 'Nothing recorded.',
		missing: 'Not published yet.',
		unreachable: 'Did not arrive.'
	});
	for (const kind of ['quiet', 'missing', 'unreachable'] as const) {
		expect(emptyState(kind)).toEqual({
			kind, shimmer: false, tone: kind === 'unreachable' ? 'warn' : 'neutral',
			sentence: STATE_WORDS[kind]
		});
	}
	expect(emptyState('loading').sentence).toBeNull();
	expect(recordEmptyState('loading')).toMatchObject({ sentence: null, record: true });
	expect(() => emptyState('too-few', '')).toThrow(/sentence/);
});

test('the route standing waits without giving an answer and counts missing panels separately', () => {
	const reading = { days: 14, through: '2026-10-09', missing: 4, unreachable: 6, shimmer: false };
	expect(routeStanding({ ...reading, state: 'loading' })).toBe('');
	expect(routeStanding({ ...reading, state: 'loading', shimmer: true })).toBe('Fetching the record.');
	expect(routeStanding({ ...reading, state: 'quiet' })).toBe('Nothing was recorded in these 14 days.');
	expect(routeStanding({ ...reading, state: 'missing' })).toBe('4 panels read a record this site has not published yet, so they have nothing to draw.');
	expect(routeStanding({ ...reading, state: 'unreachable' })).toBe('Part of the record did not arrive, so 6 panels have nothing to draw.');
	expect(routeStanding({ ...reading, state: 'ok' })).toBe('The panels below reach 9 Oct 2026.');
	expect(() => routeStanding({ ...reading, state: 'ok', through: null })).toThrow(/day/);
});

test('record freshness names the data day and when a short window fills, in UTC', () => {
	expect(recordWindowSentence({ asked: 14, first: null, through: null })).toBe('');
	expect(recordWindowSentence({ asked: 14, first: '2026-10-01', through: '2026-10-09' })).toBe(
		'Showing 9 days, to 9 Oct 2026. The record starts on 1 Oct 2026; the 14-day window fills on 14 Oct 2026.'
	);
	expect(recordWindowSentence({ asked: 7, first: '2026-09-01', through: '2026-10-09' })).toBe('Showing 7 days, to 9 Oct 2026.');
	expect(() => recordWindowSentence({ asked: 0, first: '2026-10-01', through: '2026-10-09' })).toThrow(/preset/);
	expect(() => recordWindowSentence({ asked: 7, first: '2026-02-30', through: '2026-03-09' })).toThrow(/UTC days/);
});

test('the real server frame stays loading and empty even when settled answers are supplied', async ({}, testInfo) => {
	const compile = serverCompiler(resolve(testInfo.outputPath('components')));
	const rewrites = [
		['$lib/components/RouteStatus.svelte', './RouteStatus.server.mjs'],
		['$lib/components/Reserved.svelte', './Reserved.server.mjs']
	] as const;
	await compile('src/lib/components/RouteStatus.svelte', 'RouteStatus', rewrites);
	await compile('src/lib/components/Reserved.svelte', 'Reserved', rewrites);
	const module = await compile('tests/fixtures/panels/RouteWaiting.svelte', 'RouteWaiting', rewrites);
	const component = (await import(pathToFileURL(module).href)).default;
	const body = render(component, { props: {
		initialAnswers: [{ state: 'missing', rows: [], fault: 'not-packed' }],
		days: 14, through: '2026-10-09', shimmerAfterMs: 400, height: 220, width: 760
	} }).body;
	expect(body).toContain('data-route-state="loading"');
	expect(body).toContain('data-shimmer="off"');
	expect(body).toContain('data-reserved-frame="waiting-fixture"');
	expect(body).not.toContain('data-real-count');
	expect(body).not.toContain('Not published yet.');
	expect(body).not.toContain('9 Oct');
	expect(body).not.toContain('data-console-retry');
	expect(body).not.toContain('reserved-bar');
});

test('the real window status does not print a supplied record day before the browser is ready', async ({}, testInfo) => {
	const compile = serverCompiler(resolve(testInfo.outputPath('components')));
	const module = await compile('src/lib/components/WindowStatus.svelte', 'WindowStatus', []);
	const component = (await import(pathToFileURL(module).href)).default;
	const props = { days: 14, presets: [7, 14], monthsFor: () => 0, record: { asked: 14, first: '2026-10-01', through: '2026-10-09' } };
	const pending = render(component, { props }).body;
	expect(pending).not.toContain('9 Oct');
	expect(pending).not.toContain('Showing');
	const ready = render(component, { props: { ...props, ready: true } }).body;
	expect(ready).toContain('Showing 9 days, to 9 Oct 2026.');
});
