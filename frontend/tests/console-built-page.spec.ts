/** Does the real scriptless document keep each declared door panel's first frame empty? */
import { expect, test } from './support/door-page';
import { parse, type AST } from 'svelte/compiler';
import { BAND_UNREAD } from '../src/lib/console/band';
import { BY_ROUTE, type RouteExpect } from './support/console-expect/console-built-page';

interface PanelSnapshot {
	readonly count: number;
	readonly bodies: number;
	readonly text: string;
	readonly drawnSVG: number;
	readonly reservedSVG: number;
	readonly facts: number;
}

interface BuiltSnapshot {
	readonly frames: number;
	readonly state: string | null;
	readonly shimmer: string | null;
	readonly standingCount: number;
	readonly standing: string;
	readonly panels: Readonly<Record<string, PanelSnapshot>>;
	readonly pendingCount: number;
	readonly pendingState: string | null;
	readonly pendingAttributes: readonly (string | null)[];
}

function collapsed(text: string): string {
	return text.replace(/\s+/g, ' ').trim();
}

function object(value: unknown): value is Record<string, unknown> {
	return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function pageDataKeys(payload: unknown): string[] | null {
	if (!object(payload) || payload.type !== 'data' || !Array.isArray(payload.nodes)) return null;
	const last: unknown = payload.nodes.at(-1);
	if (!object(last) || last.type !== 'data' || !Array.isArray(last.data) || !object(last.data[0])) return null;
	return Object.keys(last.data[0]).sort();
}

function builtPageErrors(actual: BuiltSnapshot, payload: unknown, expected: RouteExpect): string[] {
	const errors: string[] = [];
	if (expected.scope === 'route') {
		if (actual.frames !== 1) errors.push('Expected exactly one route frame');
		if (actual.state !== 'loading') errors.push('Route must be loading');
		if (actual.shimmer !== 'off') errors.push('Route shimmer must be off');
		if (actual.standingCount !== 1 || collapsed(actual.standing) !== '') errors.push('Route standing must exist and be empty');
	}
	for (const [id, text] of Object.entries(expected.doorPanels)) {
		const panel = actual.panels[id];
		if (!panel || panel.count !== 1 || panel.bodies !== 1) {
			errors.push(`${id}: expected exactly one panel and body`);
			continue;
		}
		if (collapsed(panel.text) !== text) errors.push(`${id}: first frame text differs`);
		if (panel.drawnSVG !== 0 || panel.facts !== 0) errors.push(`${id}: first frame contains drawn ledger facts`);
		if (expected.reservedPanels.includes(id) && panel.reservedSVG !== 1) errors.push(`${id}: reserved SVG frame is missing or duplicated`);
	}
	if (expected.pendingPanel !== null) {
		if (actual.pendingCount !== 1 || actual.pendingState !== 'loading') errors.push('Expected one loading panel wrapper');
		if (actual.pendingAttributes.length !== expected.pendingPanel.emptyAttributes.length ||
			actual.pendingAttributes.some((value) => value !== null && value !== '')) errors.push('Pending panel carries ledger reach');
	}
	const keys = pageDataKeys(payload);
	if (keys === null || JSON.stringify(keys) !== JSON.stringify([...expected.pageData].sort())) errors.push('Route pageData keys differ');
	return errors;
}

/** A bounded generated HTML fixture exercises the same observations as the real page. */
function fixtureSnapshot(html: string, expected: RouteExpect): BuiltSnapshot {
	const nodes: AST.ElementLike[] = [];
	function fragment(value: AST.Fragment | null | undefined): void {
		for (const node of value?.nodes ?? []) {
			if ('attributes' in node) nodes.push(node);
			if ('fragment' in node) fragment(node.fragment);
		}
	}
	fragment(parse(html, { modern: true }).fragment);
	function attribute(node: AST.ElementLike, name: string): string | null {
		const found = node.attributes.find((entry) => entry.type === 'Attribute' && entry.name === name);
		if (!found || found.type !== 'Attribute') return null;
		if (found.value === true) return '';
		const parts = Array.isArray(found.value) ? found.value : [found.value];
		return parts.map((part) => part.type === 'Text' ? part.data : '').join('');
	}
	function children(node: AST.ElementLike): AST.ElementLike[] {
		return nodes.filter((entry) => entry.start > node.start && entry.end < node.end);
	}
	function text(node: AST.ElementLike): string {
		function read(fragment: AST.Fragment): string {
			return fragment.nodes.map((child) => child.type === 'Text' ? child.data :
				'fragment' in child ? read(child.fragment) : '').join('');
		}
		return read(node.fragment);
	}
	const frame = nodes.filter((node) => attribute(node, 'data-console-panels') !== null);
	const standing = nodes.filter((node) => attribute(node, 'data-console-standing') !== null);
	const panels = Object.fromEntries(Object.keys(expected.doorPanels).map((id) => {
		const matching = nodes.filter((node) => attribute(node, 'data-console-panel-id') === id);
		const bodies = matching.flatMap(children).filter((node) => (attribute(node, 'class') ?? '').split(/\s+/).includes('panel-body'));
		const inside = bodies.flatMap(children);
		return [id, {
			count: matching.length, bodies: bodies.length,
			text: bodies.map(text).join(''),
			drawnSVG: inside.filter((node) => node.name === 'svg' && attribute(node, 'data-reserved-frame') === null).length,
			reservedSVG: inside.filter((node) => node.name === 'svg' && attribute(node, 'data-reserved-frame') !== null).length,
			facts: inside.filter((node) => ['data-chart-type', 'data-chart'].some((name) => attribute(node, name) !== null) ||
				(attribute(node, 'class') ?? '').split(/\s+/).includes('reserved-bar')).length
		}];
	}));
	return {
		frames: frame.length, state: frame[0] ? attribute(frame[0], 'data-route-state') : null,
		shimmer: frame[0] ? attribute(frame[0], 'data-shimmer') : null,
		standingCount: standing.length, standing: standing.map(text).join(''),
		panels, pendingCount: 0, pendingState: null, pendingAttributes: []
	};
}

test('built-page oracle refuses a figure, wrong pageData and every incorrect first-frame shape', () => {
	const expected: RouteExpect = {
		scope: 'route', doorPanels: { chart: '', card: 'Count' }, reservedPanels: ['chart'],
		pageData: ['chart', 'knobs'], pendingPanel: null
	};
	const html = '<main data-console-panels="fixture" data-route-state="loading" data-shimmer="off">' +
		'<p data-console-standing></p><section data-console-panel-id="chart"><div class="panel-body">' +
		'<svg data-reserved-frame="chart"><line></line></svg></div></section>' +
		'<section data-console-panel-id="card"><div class="panel-body"> Count </div></section></main>';
	const payload = { type: 'data', nodes: [null, { type: 'data', data: [{ chart: 1, knobs: 2 }, {}, {}] }] };
	const actual = fixtureSnapshot(html, expected);
	expect(builtPageErrors(actual, payload, expected)).toEqual([]);
	for (const changed of [
		html.replace('<line></line>', '<path data-chart-type="dateSeries"></path>'),
		html.replace('</svg>', '</svg><svg><path></path></svg>'),
		html.replace('</svg>', '</svg><span class="loading reserved-bar"></span>'),
		html.replace(' Count ', ' Count 451 '),
		html.replace('<p data-console-standing></p>', '<p data-console-standing>Record to 1 Sep</p>'),
		html.replace('data-route-state="loading"', 'data-route-state="ok"'),
		html.replace('data-shimmer="off"', 'data-shimmer="on"'),
		html.replace('data-console-panel-id="chart"', 'data-console-panel-id="wrong"'),
		html.replace('class="panel-body"', 'class="missing-body"'),
		html.replace('data-reserved-frame="chart"', 'data-reserved-typo="chart"'),
		html.replace('<p data-console-standing></p>', ''),
		html.replace('</main>', '<section data-console-panel-id="chart"><div class="panel-body"></div></section></main>')
	]) expect(builtPageErrors(fixtureSnapshot(changed, expected), payload, expected), changed).not.toEqual([]);
	for (const changed of [
		{ type: 'data', nodes: [{ type: 'data', data: [{ chart: 1, knobs: 2, rows: 3 }] }] },
		{ type: 'data', nodes: [{ type: 'data', data: [{ chart: 1 }] }] },
		{ type: 'error', nodes: [] }, {}, null
	]) expect(builtPageErrors(actual, changed, expected)).toContain('Route pageData keys differ');
});

test('limited Platform Mix contract still fails on missing panels, leaked reach and a settled first frame', () => {
	const expected = BY_ROUTE.machine;
	expect(expected).not.toBeNull();
	if (expected === null) throw new Error('Hardware must retain its shipped door-panel contract');
	expect(expected.scope).toBe('platform-mix-only');
	const payload = { type: 'data', nodes: [{ type: 'data', data: [Object.fromEntries(expected.pageData.map((key) => [key, 1]))] }] };
	const actual: BuiltSnapshot = {
		frames: 0, state: null, shimmer: null, standingCount: 0, standing: '',
		panels: { 'platform-mix': { count: 1, bodies: 1, text: '', drawnSVG: 0, reservedSVG: 1, facts: 0 } },
		pendingCount: 1, pendingState: 'loading', pendingAttributes: [null, null]
	};
	expect(builtPageErrors(actual, payload, expected)).toEqual([]);
	expect(builtPageErrors({ ...actual, panels: {} }, payload, expected)).not.toEqual([]);
	expect(builtPageErrors({ ...actual, pendingState: 'ready' }, payload, expected)).not.toEqual([]);
	expect(builtPageErrors({ ...actual, pendingAttributes: ['2026-09-01', null] }, payload, expected)).not.toEqual([]);
});

test.describe('the genuine scriptless built page', () => {
	test.use({ javaScriptEnabled: false });
	for (const route of BAND_UNREAD.routes) {
		const expected = BY_ROUTE[route.id];
		if (expected === null) continue; // Applicability is only the independent static table.
		test(`${route.id}: ${expected.scope}`, async ({ page }) => {
			await page.goto(route.href);
			const frame = page.locator(`[data-console-panels="${route.id}"]`);
			const standing = frame.locator('[data-console-standing]');
			const panels: Record<string, PanelSnapshot> = {};
			for (const id of Object.keys(expected.doorPanels)) {
				const panel = page.locator(`[data-console-panel-id="${id}"]`);
				const body = panel.locator('.panel-body');
				panels[id] = {
					count: await panel.count(), bodies: await body.count(),
					text: (await body.allTextContents()).join(''),
					drawnSVG: await body.locator('svg:not([data-reserved-frame])').count(),
					reservedSVG: await body.locator('svg[data-reserved-frame]').count(),
					facts: await body.locator('[data-chart-type], [data-chart], .reserved-bar').count()
				};
			}
			const pending = expected.pendingPanel ? page.locator(expected.pendingPanel.selector) : null;
			const pendingCount = pending ? await pending.count() : 0;
			const actual: BuiltSnapshot = {
				frames: await frame.count(),
				state: await frame.count() === 1 ? await frame.getAttribute('data-route-state') : null,
				shimmer: await frame.count() === 1 ? await frame.getAttribute('data-shimmer') : null,
				standingCount: await standing.count(), standing: (await standing.allTextContents()).join(''),
				panels, pendingCount,
				pendingState: pending && pendingCount === 1 && expected.pendingPanel ? await pending.getAttribute(expected.pendingPanel.stateAttribute) : null,
				pendingAttributes: pending && pendingCount === 1 && expected.pendingPanel ?
					await Promise.all(expected.pendingPanel.emptyAttributes.map((name) => pending.getAttribute(name))) : []
			};
			const response = await page.request.get(new URL('__data.json', page.url()).href);
			expect(response.ok(), 'The real built route must publish its page data').toBe(true);
			const payload: unknown = await response.json();
			expect(builtPageErrors(actual, payload, expected)).toEqual([]);
		});
	}
});
