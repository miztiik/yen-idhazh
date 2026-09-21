import { expect, test } from '@playwright/test';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { compile, preprocess } from 'svelte/compiler';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';
import { render } from 'svelte/server';
import { promptReuse, requestNames } from '../src/lib/console/machine/prompt-reuse';

/**
 * THE ORACLE for the reuse panel: the tracks come from the data, never from a
 * number somebody typed.
 *
 * How many requests one article makes is a config value. `_ask_the_model` runs
 * two requests per logical call when the model declares a thinking marker and
 * one when it does not, so clearing one marker turns four requests into two
 * with no code changed. A panel drawn for a fixed number is therefore a panel
 * that goes quietly wrong on a config edit, and nothing would fail to warn the
 * person who made it.
 *
 * So the ledger's own column names decide, and this file renders the panel
 * three times with a DIFFERENT number of them. A constant cannot satisfy all
 * three, and neither can arithmetic over a count: the fixtures name one, two
 * and three requests and the drawn track pairs follow each of them.
 *
 * The second half is the spread. A fixture whose reuse runs from nothing to
 * nearly everything must draw both ends, because the mean of those two ends is
 * the figure this panel exists to stop publishing.
 *
 * `render` and not a browser: nothing here depends on layout, and the count of
 * drawn tracks is in the markup.
 */

const here = path.dirname(fileURLToPath(import.meta.url));
const frontend = path.resolve(here, '..');
/** Any other child renders as nothing. `Panel` is compiled for real below,
 * because everything this file reads sits inside its children snippet. */
const CHILD_STUB = 'data:text/javascript,export default function(){}';

type Rendered = string;

/** Compile one component to a server module beside its siblings, and return the
 * file it was written to. `Panel.svelte` imports nothing but a Svelte type, so
 * it compiles and renders with no stubbing at all. */
async function compiled(source: string, name: string, rewrite: [string, string][]): Promise<string> {
	const filename = path.join(frontend, source);
	const pre = await preprocess(readFileSync(filename, 'utf8'), vitePreprocess(), { filename });
	const result = compile(pre.code, { generate: 'server', filename, name });
	const built = path.join(frontend, 'test-results', 'rendered');
	mkdirSync(built, { recursive: true });
	const module = path.join(built, `${name}.server.mjs`);
	let code = result.js.code;
	for (const [from, to] of rewrite) code = code.split(`'${from}'`).join(`'${to}'`);
	writeFileSync(module, code.replace(/'[^']*\.svelte'/g, `'${CHILD_STUB}'`), 'utf8');
	return module;
}

async function renderer(): Promise<(props: Record<string, unknown>) => Rendered> {
	await compiled('src/lib/components/Panel.svelte', 'Panel', []);
	const module = await compiled(
		'src/lib/console/machine/PromptReusePanel.svelte',
		'PromptReusePanel',
		[['$lib/components/Panel.svelte', './Panel.server.mjs']]
	);
	const loaded = await import(pathToFileURL(module).href);
	return (props) => render(loaded.default, { props }).body;
}

/** The chart width the page passes, read from the config the page reads it from
 * rather than typed here (Guardrail #6). It decides only whether a band is wide
 * enough to draw, so a test that typed its own would be testing a different
 * page. */
const CHART = JSON.parse(
	readFileSync(path.join(frontend, '..', 'config', 'appearance.json'), 'utf8')
).chart as { width_px: number; height_px: number };

/** An item row carrying one reuse reading and one reading speed per request. */
function itemRow(readings: Record<string, [number, number]>): Record<string, string> {
	const row: Record<string, string> = { date: '2026-09-20' };
	for (const [request, [reusePct, readRate]] of Object.entries(readings)) {
		row[`${request}_cache_pct`] = String(reusePct);
		row[`${request}_prefill_tokens_per_s`] = String(readRate);
	}
	return row;
}

function columnsFor(requests: readonly string[]): string[] {
	return [
		'date',
		...requests.flatMap((name) => [`${name}_cache_pct`, `${name}_prefill_tokens_per_s`])
	];
}

/** How many request entries the rendered panel drew, off the markup. */
function drawnRequests(body: string): number {
	return [...body.matchAll(/data-prompt-reuse-request="(\d+)"/g)].length;
}

/** The three shapes the ledger could take. One request is the pipeline with the
 * thinking marker cleared and the calls folded; two is what it writes today;
 * three is a plan pass added in front. Not one of them is privileged here. */
const SHAPES: { requests: string[]; why: string }[] = [
	{ requests: ['summary'], why: 'one request' },
	{ requests: ['label', 'summary'], why: 'two requests' },
	{ requests: ['plan', 'label', 'summary'], why: 'three requests' }
];

test('THE ORACLE: the drawn track pairs follow the ledger, not a constant', async () => {
	const draw = await renderer();
	const drawn: number[] = [];

	for (const shape of SHAPES) {
		const rows = [0, 1, 2].map((step) =>
			itemRow(
				Object.fromEntries(
					shape.requests.map((name, index) => [
						name,
						[10 * index + step, 12 + index + step] as [number, number]
					])
				)
			)
		);
		const reuse = promptReuse(rows, columnsFor(shape.requests));
		expect(reuse.requests.length, `${shape.why}: the derivation counted a different number`).toBe(
			shape.requests.length
		);

		const body = draw({ reuse, days: 30, windowDays: 30, chart: CHART });
		expect(drawnRequests(body), `${shape.why}: the panel drew a different number`).toBe(
			shape.requests.length
		);
		drawn.push(drawnRequests(body));
	}

	// The point of all three together: no constant and no fixed arithmetic
	// satisfies them, because the three answers are different.
	expect(new Set(drawn).size, 'three fixtures drew the same number of tracks').toBe(SHAPES.length);
});

test('THE ORACLE: a spread from nothing to nearly everything draws both ends', async () => {
	const draw = await renderer();
	// One request that reads its whole prompt again and one that reuses almost
	// all of its own. Their mean is 49.8 percent, which is the figure a day
	// grain would print and which neither request ever recorded.
	const rows = [
		itemRow({ label: [0, 9.13], summary: [98.73, 31.38] }),
		itemRow({ label: [0.2, 9.72], summary: [99.6, 30.1] })
	];
	const reuse = promptReuse(rows, columnsFor(['label', 'summary']));

	expect(reuse.floor, 'the floor was not found').toEqual({ place: 1, pct: 0 });
	expect(reuse.ceiling, 'the ceiling was not found').toEqual({ place: 2, pct: 99.6 });

	const body = draw({ reuse, days: 30, windowDays: 30, chart: CHART });
	expect(body, 'the panel did not print the floor it measured').toContain('0.00%');
	expect(body, 'the panel did not print the ceiling it measured').toContain('99.60%');
	const mean = ((0 + 99.6) / 2).toFixed(2);
	expect(body, 'the panel printed the mean of the two ends').not.toContain(`${mean}%`);
});

test('a request the ledger names but never filled is drawn as absent, not as zero', async () => {
	const draw = await renderer();
	const rows = [{ date: '2026-09-20', summary_cache_pct: '98.74' }];
	const reuse = promptReuse(rows, columnsFor(['label', 'summary']));

	// Both requests are named by the columns; only one was ever measured.
	expect(requestNames(columnsFor(['label', 'summary']))).toEqual(['label', 'summary']);
	expect(reuse.requests[0].reuse, 'an unfilled request was given a reading').toBeNull();
	expect(reuse.items, 'the item count counted a row that recorded nothing').toBe(1);

	const body = draw({ reuse, days: 30, windowDays: 30, chart: CHART });
	expect(drawnRequests(body), 'a request nothing measured was drawn anyway').toBe(1);
	expect(body, 'a missing reading was drawn as a zero').not.toContain('data-reuse-low="0"');
});

test('a window nothing measured says so rather than drawing an empty track', async () => {
	const draw = await renderer();
	const reuse = promptReuse([{ date: '2026-09-20' }], columnsFor(['label', 'summary']));
	const body = draw({ reuse, days: 7, windowDays: 7, chart: CHART });

	expect(drawnRequests(body), 'a window with no readings drew a track').toBe(0);
	expect(body, 'a window with no readings drew no sentence either').toContain(
		'data-prompt-reuse-empty="none"'
	);
});

test('the contract names its requests in the spelling the panel discovers them by', () => {
	// The generated schema and not a committed day file: the schema is the
	// contract the producer writes those columns under, it is one file of fixed
	// size, and no run can edit it (`CLAUDE.md` section 13).
	//
	// Read off it rather than asserted as a list. How many requests the pipeline
	// makes is a config value, so a test that named two would be the very
	// constant this row exists to remove. What is asserted is the property: the
	// contract names at least one request, and each one carries the
	// reading-speed column this panel pairs with it.
	const schema = JSON.parse(
		readFileSync(path.join(frontend, '..', 'schemas', 'item-health-row.schema.json'), 'utf8')
	) as { properties: Record<string, unknown> };
	const columns = Object.keys(schema.properties);
	const names = requestNames(columns);

	expect(names.length, 'the contract names no request at all').toBeGreaterThan(0);
	for (const name of names) {
		expect(columns, `${name} carries no reading-speed column to pair with`).toContain(
			`${name}_prefill_tokens_per_s`
		);
	}
});
