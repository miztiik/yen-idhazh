import { expect, test } from '@playwright/test';
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { render } from 'svelte/server';
import ts from 'typescript';

import { AXIS_LABEL_GAP_PX, AXIS_LABEL_PX, frame } from '../src/lib/charts/frame';
import { UNRECORDED_STOP } from '../src/lib/charts/machine-colour';
import { readoutOf } from '../src/lib/charts/readout';
import { valueAxis } from '../src/lib/charts/d3/axis';
import { dateSeries, type SeriesInput } from '../src/lib/charts/d3/dateSeries';
import { distribution, distributionShortfall } from '../src/lib/charts/d3/distribution';
import { emptyState, tooFewSentence } from '../src/lib/charts/d3/empty';
import { flow, type FlowStageInput } from '../src/lib/charts/d3/flow';
import { prefersReducedMotion, REDUCED_MOTION_QUERY, transition } from '../src/lib/charts/d3/motion';
import { absentHatch, orderedRamp, RESERVED_GREY } from '../src/lib/charts/d3/ordered-colour';
import { overlapTimeline } from '../src/lib/charts/d3/overlapTimeline';
import { paired, pairedShortfall, type PairedInput } from '../src/lib/charts/d3/paired';
import { pairedScatter, pairedScatterShortfall, type ScatterInput } from '../src/lib/charts/d3/pairedScatter';
import { partsOfOne } from '../src/lib/charts/d3/partsOfOne';
import { rankedList } from '../src/lib/charts/d3/rankedList';
import { bandScale, linearScale, timeScale } from '../src/lib/charts/d3/scale';
import { tileStrip } from '../src/lib/charts/d3/tileStrip';
import { CHART_VOCABULARY_PAGE } from '../scripts/doc-test-inputs';
import { serverCompiler } from './support/server-render';

/**
 * THE ORACLE for the chart vocabulary: every chart type is written down, and
 * nothing has left the house style.
 *
 * The vocabulary page is the one list of the types a console panel is built
 * from, so a new type arrives on purpose - with its page entry and Susan's
 * ruling - and never by accident. This file reads that list off the page and
 * holds `frontend/src/lib/charts/d3/` to it both ways: every listed type has
 * its module, and every module there is a listed type or a listed piece of the
 * house style. It then walks every import under `frontend/src/` for the four
 * d3 packages this console refuses by name, and the query door's call sites for
 * a panel that asks for every column or an open date range.
 *
 * Below the oracle, each house-style module and each type is driven through
 * its own rules, and each drawing component is rendered on the server, where
 * the count of drawn marks is in the markup and no layout is needed.
 */

const here = path.dirname(fileURLToPath(import.meta.url));
const frontend = path.resolve(here, '..');
const repo = path.resolve(frontend, '..');
const source = path.join(frontend, 'src');
const vocabulary = path.join(source, 'lib', 'charts', 'd3');

/** A package this console refuses, by its own name or any path inside it.
 * The umbrella `d3` re-exports all four, so it is refused with them. */
const REFUSED = ['d3-axis', 'd3-selection', 'd3-transition', 'd3-scale-chromatic', 'd3'];
/** The query engine, and the one module allowed to import it. */
const ENGINE_PACKAGE = '@duckdb/duckdb-wasm';
const ENGINE_MODULE = 'frontend/src/lib/data/engine.ts';
/** The two entry points of the query door, and where they are exported from. */
const DOOR_CALLS = ['slice', 'sliceFromDisk'];
const DOOR_MODULE = /(^|\/)(data\/ledger|server\/ledger-disk)(\.ts)?$/;
/** The door's modules, the one a panel may import, and the one a build-time reader may. */
const DOOR_DIRECTORY = 'frontend/src/lib/data/';
const PANEL_DOOR = 'frontend/src/lib/data/ledger';
const DISK_DOOR = 'frontend/src/lib/server/ledger-disk';
const SERVER_DIRECTORY = 'frontend/src/lib/server/';

interface Listed {
	name: string;
	drawnBy: string | null;
}

/** One table off the page, under the heading that names it: the first
 * backticked word of the second column, and the backticked file of the last.
 * Read inside the test that needs it, so a page that lost its table fails the
 * test that says so and no other. */
function listedUnder(heading: string): Listed[] {
	const page = readFileSync(path.join(repo, CHART_VOCABULARY_PAGE), 'utf8').replaceAll('\r\n', '\n');
	const start = page.indexOf(`\n## ${heading}\n`);
	expect(start, `${CHART_VOCABULARY_PAGE} has no section "${heading}"`).toBeGreaterThan(-1);
	const next = page.indexOf('\n## ', start + heading.length + 4);
	const body = page.slice(start, next === -1 ? undefined : next);
	const rows = body.split('\n').filter((line) => /^\|\s*\d+\s*\|/.test(line));
	return rows.map((line) => {
		const cells = line.split('|').map((cell) => cell.trim());
		const name = /`([^`]+)`/.exec(cells[2] ?? '')?.[1];
		expect(name, `a row under "${heading}" names nothing: ${line}`).toBeTruthy();
		const drawn = /`([^`]+\.svelte)`/.exec(cells[cells.length - 2] ?? '')?.[1] ?? null;
		return { name: name as string, drawnBy: drawn };
	});
}

function typesOnThePage(): Listed[] {
	return listedUnder('The chart types a panel is built from');
}

function houseStyleOnThePage(): Listed[] {
	return listedUnder('The house style every chart type draws with');
}

/** Every file under `frontend/src/` that can import anything. */
function sourcesUnder(dir: string): string[] {
	return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
		const full = path.join(dir, entry.name);
		if (entry.isDirectory()) return sourcesUnder(full);
		return /\.(ts|js|mjs|svelte)$/.test(entry.name) ? [full] : [];
	});
}

/** The script a file runs: the whole of a module, or every script block of a
 * component. */
function scriptsOf(file: string): string[] {
	const text = readFileSync(file, 'utf8');
	if (!file.endsWith('.svelte')) return [text];
	return [...text.matchAll(/<script[^>]*>([\s\S]*?)<\/script>/g)].map((match) => match[1]);
}

interface Source {
	file: string;
	scripts: string[];
}

let scanned: Source[] | null = null;

/** Every source file and its scripts, read once by the first walk that asks
 * and shared by the three walks below. The tree is the application's own
 * code, so the cost follows the code and not anything a run writes. */
function sources(): Source[] {
	scanned ??= sourcesUnder(source).map((file) => ({ file, scripts: scriptsOf(file) }));
	return scanned;
}

/** Every module a file imports, statically or by `import()`, as the compiler
 * reads it rather than as a pattern guesses it. */
function importsOf(entry: Source): string[] {
	return entry.scripts.flatMap((script) =>
		ts.preProcessFile(script, true, true).importedFiles.map((imported) => imported.fileName)
	);
}

function relative(file: string): string {
	return path.relative(repo, file).replaceAll('\\', '/');
}

function names(pkg: string, specifier: string): boolean {
	return specifier === pkg || specifier.startsWith(`${pkg}/`);
}

/** The repository path a specifier names, without its extension, or null for a
 * package. `$lib` is the only alias this tree uses. */
function landsOn(entry: Source, specifier: string): string | null {
	const target = specifier.startsWith('$lib/')
		? path.join(source, 'lib', specifier.slice('$lib/'.length))
		: specifier.startsWith('.')
			? path.resolve(path.dirname(entry.file), specifier)
			: null;
	return target === null ? null : relative(target).replace(/\.(ts|js)$/, '');
}

function declaredColumns(expression: ts.Expression | undefined, tree: ts.SourceFile, seen = new Set<string>()): string[] | null {
	if (expression === undefined) return null;
	if (ts.isAsExpression(expression) || ts.isSatisfiesExpression(expression) || ts.isParenthesizedExpression(expression)) {
		return declaredColumns(expression.expression, tree, seen);
	}
	if (ts.isArrayLiteralExpression(expression)) {
		const columns: string[] = [];
		for (const element of expression.elements) {
			if (ts.isStringLiteral(element)) columns.push(element.text);
			else if (ts.isSpreadElement(element)) {
				const spread = declaredColumns(element.expression, tree, new Set(seen));
				if (spread === null) return null;
				columns.push(...spread);
			} else return null;
		}
		return columns;
	}
	if (!ts.isIdentifier(expression)) return null;
	const key = `${tree.fileName}:${expression.text}`;
	if (seen.has(key)) return null;
	seen.add(key);
	for (const statement of tree.statements) {
		if (ts.isVariableStatement(statement)) {
			const declaration = statement.declarationList.declarations.find((entry) => ts.isIdentifier(entry.name) && entry.name.text === expression.text);
			if (declaration) return declaredColumns(declaration.initializer, tree, seen);
		}
		if (!ts.isImportDeclaration(statement) || !ts.isStringLiteral(statement.moduleSpecifier)) continue;
		const bindings = statement.importClause?.namedBindings;
		if (!bindings || !ts.isNamedImports(bindings)) continue;
		const imported = bindings.elements.find((entry) => entry.name.text === expression.text);
		if (!imported) continue;
		const resolved = ts.resolveModuleName(statement.moduleSpecifier.text, tree.fileName, {
			moduleResolution: ts.ModuleResolutionKind.Bundler,
			baseUrl: frontend,
			paths: { '$lib/*': ['src/lib/*'] }
		}, ts.sys).resolvedModule;
		if (!resolved) return null;
		const module = ts.createSourceFile(resolved.resolvedFileName, readFileSync(resolved.resolvedFileName, 'utf8'), ts.ScriptTarget.Latest, true);
		return declaredColumns(ts.factory.createIdentifier((imported.propertyName ?? imported.name).text), module, seen);
	}
	return null;
}

test('the query-column guard resolves static arrays and keeps wildcard and unknown expressions visible', () => {
	const tree = ts.createSourceFile(path.join(frontend, 'guard.ts'), `
		import { FLEET_COLUMNS as imported } from '$lib/charts/fleet';
		const literal = ['date', 'job'] as const;
		const wildcard = [...literal, '*'];
		const dynamic = chooseColumns();
		const cycle = cycle;
	`, ts.ScriptTarget.Latest, true);
	const columns = (name: string) => declaredColumns(ts.factory.createIdentifier(name), tree);
	expect(columns('literal')).toEqual(['date', 'job']);
	expect(columns('wildcard')).toEqual(['date', 'job', '*']);
	expect(columns('dynamic')).toBeNull();
	expect(columns('cycle')).toBeNull();
	expect(columns('imported')).toContain('date');
	expect(columns('imported')).not.toContain('*');
});

test.describe('THE ORACLE: every chart type is written down, and nothing has left the house style', () => {
	test('every listed type has its module, and every module is listed', () => {
		const types = typesOnThePage();
		const house = houseStyleOnThePage();
		expect(types.length, 'the page lists no chart types').toBeGreaterThan(0);
		expect(house.length, 'the page lists no house style').toBeGreaterThan(0);
		const listed = new Set([...types.map((type) => type.name), ...house.map((module) => module.name.replace(/\.ts$/, ''))]);
		expect(listed.size, 'the page lists one name twice').toBe(types.length + house.length);

		// Every miss at once, so one run names every module to list or to write.
		const unwritten = [
			...types.filter((type) => !existsSync(path.join(vocabulary, `${type.name}.ts`))).map((type) => type.name),
			...house.filter((module) => !existsSync(path.join(vocabulary, module.name))).map((module) => module.name)
		];
		expect(unwritten, 'listed on the vocabulary page with no module under charts/d3/').toEqual([]);
		const unlisted = readdirSync(vocabulary)
			.filter((file) => file.endsWith('.ts'))
			.filter((module) => !listed.has(module.replace(/\.ts$/, '')));
		expect(
			unlisted,
			"under charts/d3/ and on no list; a type is added on the vocabulary page, with Susan's ruling, before it is built"
		).toEqual([]);
	});

	test('every drawing component is named on the page, and every named one exists', () => {
		const rows = [...typesOnThePage(), ...houseStyleOnThePage()];
		const named = new Set(rows.flatMap((row) => (row.drawnBy === null ? [] : [row.drawnBy])));
		const missing = [...named].filter(
			(drawn) => !existsSync(drawn.includes('/') ? path.join(repo, drawn) : path.join(vocabulary, drawn))
		);
		expect(missing, 'named on the vocabulary page as what draws a type, and not there').toEqual([]);
		const unnamed = readdirSync(vocabulary)
			.filter((file) => file.endsWith('.svelte'))
			.filter((component) => !named.has(component));
		expect(unnamed, 'under charts/d3/ and the page names no type it draws').toEqual([]);
	});

	test('no file under frontend/src imports a refused package', () => {
		const found = sources().flatMap((entry) =>
			importsOf(entry)
				.filter((specifier) => REFUSED.some((pkg) => names(pkg, specifier)))
				.map((specifier) => `${relative(entry.file)} imports ${specifier}`)
		);
		expect(found, 'd3 is a maths library here: Svelte owns the DOM, dayTicks owns the dates and tokens.css owns the colour').toEqual([]);
	});

	test('the query engine has one importer, and it is the engine module', () => {
		const importers = sources()
			.filter((entry) => importsOf(entry).some((specifier) => names(ENGINE_PACKAGE, specifier)))
			.map((entry) => relative(entry.file));
		expect(importers, 'a second importer is a second place to change when the engine moves').toEqual([ENGINE_MODULE]);
	});

	test('a panel reaches the door through ledger.ts and nothing deeper', () => {
		const deeper = sources()
			.filter(({ file }) => !relative(file).startsWith(DOOR_DIRECTORY) && !relative(file).startsWith(SERVER_DIRECTORY))
			.flatMap((entry) =>
				importsOf(entry)
					.map((specifier) => landsOn(entry, specifier))
					.filter((target): target is string =>
						target !== null &&
						target.startsWith(DOOR_DIRECTORY) &&
						target !== PANEL_DOOR &&
						!(relative(entry.file) === 'frontend/src/lib/console/waiting.ts' && target === 'frontend/src/lib/data/slice-shapes')
					)
					.map((target) => `${relative(entry.file)} imports ${target}`)
			);
		expect(deeper, 'only ledger.ts binds the door to the published site; a deeper module lets a panel name a path').toEqual([]);
	});

	test('sliceFromDisk has one home, and only a build-time reader imports it', () => {
		const homes = sources()
			.filter(({ scripts }) => scripts.some((script) => /export (async )?function sliceFromDisk\b/.test(script)))
			.map(({ file }) => relative(file));
		expect(homes).toEqual([`${DISK_DOOR}.ts`]);
		const importers = sources()
			.filter((entry) => importsOf(entry).some((specifier) => landsOn(entry, specifier) === DISK_DOOR))
			.map(({ file }) => relative(file));
		const outside = importers.filter((file) => !file.startsWith(SERVER_DIRECTORY));
		expect(outside, 'a panel never reads the disk: it calls slice()').toEqual([]);
		if (importers.length === 0) {
			test.info().annotations.push({
				type: 'vacuous',
				description: 'No build-time reader calls sliceFromDisk yet; this walk bites from the first one that does.'
			});
		}
	});

	test('every call to the query door names its columns and closes its date range', () => {
		const problems: string[] = [];
		let calls = 0;
		for (const { file, scripts } of sources()) {
			if (/\/lib\/data\//.test(relative(file))) continue;
			for (const script of scripts) {
				const tree = ts.createSourceFile(file, script, ts.ScriptTarget.Latest, true);
				const local = new Set<string>();
				tree.forEachChild((node) => {
					if (!ts.isImportDeclaration(node) || !ts.isStringLiteral(node.moduleSpecifier)) return;
					if (!DOOR_MODULE.test(node.moduleSpecifier.text)) return;
					const bound = node.importClause?.namedBindings;
					if (bound === undefined || !ts.isNamedImports(bound)) return;
					for (const element of bound.elements) {
						if (DOOR_CALLS.includes((element.propertyName ?? element.name).text)) local.add(element.name.text);
					}
				});
				const visit = (node: ts.Node): void => {
					if (ts.isCallExpression(node) && ts.isIdentifier(node.expression) && local.has(node.expression.text)) {
						calls += 1;
						const options = node.arguments[node.arguments.length - 1];
						const where = `${relative(file)}: ${node.getText().slice(0, 80)}`;
						if (options === undefined || !ts.isObjectLiteralExpression(options)) {
							problems.push(`${where} - pass the options inline, so this walk can read them`);
						} else {
							const field = (key: string) =>
								options.properties.find(
									(property): property is ts.PropertyAssignment | ts.ShorthandPropertyAssignment =>
										(ts.isPropertyAssignment(property) || ts.isShorthandPropertyAssignment(property)) && property.name.getText() === key
								);
							const columnField = field('columns');
							const columns = declaredColumns(columnField === undefined ? undefined
								: ts.isShorthandPropertyAssignment(columnField) ? columnField.name : columnField.initializer, tree);
							if (columns === null || columns.length === 0) {
								problems.push(`${where} - names no columns`);
							} else if (columns.includes('*')) {
								problems.push(`${where} - asks for every column`);
							}
							for (const end of ['from', 'to']) {
								if (field(end) === undefined) problems.push(`${where} - leaves the date range open at "${end}"`);
							}
						}
					}
					ts.forEachChild(node, visit);
				};
				visit(tree);
			}
		}
		if (calls === 0) {
			test.info().annotations.push({
				type: 'vacuous',
				description: 'No panel calls the query door yet; this walk bites from the first panel that does.'
			});
		}
		expect(problems).toEqual([]);
	});
});

test.describe('the house style', () => {
	const box = frame(400, 200);

	test('a scale reads its range from the frame, and up the page for a value', () => {
		expect(linearScale([0, 10], box, 'y').range()).toEqual([box.bottom, box.top]);
		expect(linearScale([0, 10], box, 'x').range()).toEqual([box.left, box.right]);
		const band = bandScale(['a', 'b'], box, 'x', 0.2);
		expect(band('a')).toBeGreaterThanOrEqual(box.left);
		expect((band('b') ?? 0) + band.bandwidth()).toBeLessThanOrEqual(box.right);
	});

	test('the time scale rounds and ticks on UTC midnights wherever it runs', () => {
		const zone = process.env.TZ;
		// Half an hour off a whole hour, so a local midnight can never pass for a UTC one.
		process.env.TZ = 'Asia/Kolkata';
		try {
			const scale = timeScale([Date.UTC(2026, 8, 1, 5, 30), Date.UTC(2026, 8, 3, 17, 0)], box).nice();
			expect(scale.domain()[0].toISOString()).toBe('2026-09-01T00:00:00.000Z');
			for (const tick of scale.ticks(3)) expect(tick.getUTCHours(), tick.toISOString()).toBe(0);
		} finally {
			if (zone === undefined) delete process.env.TZ;
			else process.env.TZ = zone;
		}
	});

	test('a value axis starts at zero, prints one precision, and never a non-ASCII minus', () => {
		const axis = valueAxis([-0.4, 1.2], box, { along: 'y', ticks: 4 });
		expect(axis.domain[0]).toBeLessThanOrEqual(-0.4);
		const texts = axis.ticks.map((tick) => tick.text).filter((text) => text !== '');
		expect(texts.every((text) => /^-?[\d,]+\.\d$/.test(text)), texts.join(' ')).toBe(true);
		expect(texts.join('')).not.toMatch(/[^\x20-\x7e]/);
		const positive = valueAxis([3, 9], box, { along: 'x', ticks: 4 });
		expect(positive.domain[0]).toBe(0);
		expect(valueAxis([3, 9], box, { along: 'x', ticks: 4, zero: false }).domain[0]).toBeGreaterThan(0);
	});

	test('an upright axis keeps a line of air between two labels', () => {
		const short = frame(400, 120);
		const axis = valueAxis([0, 100], short, { along: 'y', ticks: 10 });
		const drawn = axis.ticks.filter((tick) => tick.text !== '');
		expect(drawn.length).toBeGreaterThan(1);
		expect(drawn.length).toBeLessThan(axis.ticks.length);
		for (let at = 1; at < drawn.length; at += 1) {
			expect(Math.abs(drawn[at].at - drawn[at - 1].at)).toBeGreaterThanOrEqual(AXIS_LABEL_PX + AXIS_LABEL_GAP_PX);
		}
	});

	test('the machine colours keep the one reserved grey, not a second', () => {
		expect(RESERVED_GREY).toBe(UNRECORDED_STOP);
	});

	test('an ordered ramp is one token in steps, cut over the whole record', () => {
		const record = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];
		const ramp = orderedRamp(record, 5, '--chart-1', 0.4);
		expect(ramp).not.toBeNull();
		if (ramp === null) return;
		expect(ramp.colours).toHaveLength(5);
		expect(ramp.colours[4]).toBe('var(--chart-1)');
		expect(ramp.colours.every((colour) => colour.includes('var(--chart-1)'))).toBe(true);
		expect(ramp.colours.join(' ')).not.toMatch(/#[0-9a-f]{3,8}\b/i);
		// The weakest step carries the floor of the hue, and the rest rise evenly.
		expect(ramp.colours.slice(0, 4).map((colour) => Number(/ (\d+)%/.exec(colour)?.[1]))).toEqual([40, 55, 70, 85]);
		expect(ramp.cuts).toHaveLength(4);
		expect(ramp.stepOf(1)).toBe(1);
		expect(ramp.stepOf(10)).toBe(5);
		expect(orderedRamp([], 5, '--chart-1', 0.4)).toBeNull();
		expect(() => orderedRamp(record, 0, '--chart-1', 0.4)).toThrow(/whole number of steps/);
		expect(() => orderedRamp(record, 5, '--chart-1', 1)).toThrow(/not all of it/);
	});

	test('the absent hatch takes its angle from the caller and shows the page between its stripes', () => {
		const hatch = absentHatch({ degrees: 30, gapPx: 3, linePx: 1 });
		expect(hatch.background).toContain('30deg');
		expect(hatch.background).toContain('transparent');
		expect(hatch.ink).toBe(`var(--chart-${UNRECORDED_STOP})`);
		expect(hatch.tile).toEqual({ size: 4, transform: 'rotate(30)' });
		expect(() => absentHatch({ degrees: 45, gapPx: 0, linePx: 1 })).toThrow(/wider than nothing/);
	});

	test('motion is one duration and one easing from the tokens, and none at all when reduced', () => {
		expect(transition(['opacity', 'transform'], false)).toBe(
			'opacity var(--dur-base) var(--ease-standard), transform var(--dur-base) var(--ease-standard)'
		);
		expect(transition(['opacity'], true)).toBe('none');
		expect(() => transition(['width'], false)).toThrow(/does not animate "width"/);
		expect(prefersReducedMotion((query) => ({ matches: query === REDUCED_MOTION_QUERY }))).toBe(true);
		expect(prefersReducedMotion(() => ({ matches: false }))).toBe(false);
		expect(prefersReducedMotion(undefined)).toBe(true);
	});

	test('every nothing but a wait says what it is, and only a failure takes a hue', () => {
		expect(emptyState('loading')).toEqual({ kind: 'loading', shimmer: true, tone: 'neutral', sentence: null });
		expect(emptyState('unreachable', 'September 2026 did not arrive.').tone).toBe('warn');
		for (const kind of ['quiet', 'missing', 'too-few'] as const) {
			expect(emptyState(kind, 'Said.').tone).toBe('neutral');
		}
		expect(() => emptyState('quiet', ' ')).toThrow(/says so in words/);
		expect(tooFewSentence(42, 160, 'readings')).toBe(
			'Only 42 of the 160 readings this chart needs are in this window, so it is not drawn.'
		);
		expect(tooFewSentence(1, 3, 'subjects')).toContain('is in this window');
	});
});

test.describe('the nine types', () => {
	const box = frame(400, 200);

	test('rankedList ranks by magnitude, caps, and measures every part against one divisor', () => {
		const ranked = rankedList(
			[
				{ label: 'b', value: 4, segments: [{ label: 'x', value: 1 }, { label: 'y', value: 3 }] },
				{ label: 'a', value: 8 },
				{ label: 'c', value: 2 }
			],
			{ max: 2 }
		);
		expect(ranked?.rows.map((row) => row.label)).toEqual(['a', 'b']);
		expect(ranked?.max).toBe(8);
		expect(ranked?.hidden).toBe(1);
		expect(ranked?.rows[1].segments.map((part) => [part.start, part.size])).toEqual([
			['0.0000%', '12.5000%'],
			['12.5000%', '37.5000%']
		]);
		expect(rankedList([{ label: 'a', value: 0 }], {})).toBeNull();
		expect(() => rankedList([{ label: 'a', value: 1, segments: [{ label: 'x', value: 2 }] }], {})).toThrow(/more than its/);
		expect(() => rankedList([{ label: 'a', value: 1 }, { label: 'a', value: 2 }], {})).toThrow(/names each thing once/);
	});

	const lines: SeriesInput[] = [
		{
			label: 'first',
			token: '--chart-1',
			points: [
				{ date: '2026-09-01', value: 2 },
				{ date: '2026-09-02', value: null },
				{ date: '2026-09-03', value: 4 },
				{ date: '2026-09-04', value: 5 }
			]
		},
		{ label: 'second', token: '--chart-2', points: [{ date: '2026-09-02', value: 3 }] }
	];

	test('dateSeries breaks a line at a missing day and gives a lone reading a dot', () => {
		const series = dateSeries(lines, { frame: box, density: 6, valueTicks: 4, padding: 0.2 });
		expect(series?.dates).toEqual(['2026-09-01', '2026-09-02', '2026-09-03', '2026-09-04']);
		expect(series?.ticks.length).toBeGreaterThan(0);
		const first = series?.lines[0];
		expect(first?.path.match(/M/g)?.length, 'a gap is a break in the line, never a zero').toBe(2);
		expect(first?.points.find((point) => point.date === '2026-09-01')?.alone).toBe(true);
		expect(first?.points.find((point) => point.date === '2026-09-03')?.alone).toBe(false);
		expect(series?.lines[1].points[0].alone).toBe(true);
		expect(dateSeries([{ label: 'none', token: '--chart-1', points: [{ date: '2026-09-01', value: null }] }], {
			frame: box,
			density: 6,
			valueTicks: 4,
			padding: 0.2
		})).toBeNull();
	});

	test('dateSeries stacks a day into one bar and draws no segment for a missing reading', () => {
		const series = dateSeries(lines, { frame: box, stacked: true, density: 6, valueTicks: 4, padding: 0.2 });
		expect(series?.lines).toEqual([]);
		expect(series?.bars.map((bar) => `${bar.label} ${bar.date}`)).toEqual([
			'first 2026-09-01',
			'first 2026-09-03',
			'first 2026-09-04',
			'second 2026-09-02'
		]);
		expect(series?.axis.domain[1]).toBeGreaterThanOrEqual(5);
		const negative: SeriesInput[] = [{ label: 'n', token: '--chart-1', points: [{ date: '2026-09-01', value: -1 }] }];
		expect(() => dateSeries(negative, { frame: box, stacked: true, density: 6, valueTicks: 4, padding: 0 })).toThrow(/negative/);
	});

	test('distribution draws nothing under its floor and names the floor it missed', () => {
		const few = [1, 2, 3];
		expect(distribution(few, { frame: box, minValues: 160, valueTicks: 5 })).toBeNull();
		expect(distributionShortfall(few, { minValues: 160 })).toContain('Only 3 of the 160 readings');
		const many = Array.from({ length: 40 }, (_, index) => index % 10);
		const shape = distribution(many, { frame: box, minValues: 20, valueTicks: 5, rules: [{ at: 12, label: 'limit' }] });
		expect(shape?.bins.reduce((sum, bin) => sum + bin.count, 0)).toBe(40);
		expect(shape?.bins.at(-1)?.share).toBe(100);
		expect(shape?.x.domain[1]).toBeGreaterThanOrEqual(12);
		expect(shape?.rules[0].x).toBeLessThanOrEqual(box.right);
		expect(distributionShortfall(many, { minValues: 20 })).toBeNull();
	});

	test('partsOfOne stacks parts in one order, and overlapping parts are brackets with no total', () => {
		const rows = [
			{ label: 'r1', parts: [{ label: 'late', value: 1 }, { label: 'early', value: 3 }] },
			{ label: 'r2', parts: [{ label: 'early', value: 2 }] }
		];
		const stacked = partsOfOne(rows, { order: ['early', 'late'] });
		expect(stacked?.max).toBe(4);
		expect(stacked?.rows[0].segments.map((part) => [part.label, part.start])).toEqual([
			['early', '0.0000%'],
			['late', '75.0000%']
		]);
		expect(stacked?.rows[0].total).toBe(4);
		const overlapping = partsOfOne(rows, { order: ['early', 'late'], overlapping: true });
		expect(overlapping?.rows[0].total).toBeNull();
		expect(overlapping?.rows[0].segments.every((part) => part.start === '0.0000%')).toBe(true);
		expect(stacked?.key.map((part) => part.token)).not.toContain(`--chart-${UNRECORDED_STOP}`);
		expect(() => partsOfOne([{ label: 'r', parts: [{ label: 'other', value: 1 }] }], { order: ['early'] })).toThrow(/does not name/);
		expect(partsOfOne([{ label: 'r', parts: [{ label: 'early', value: 0 }] }], { order: ['early'] })).toBeNull();
	});

	test('tileStrip keeps three states and never passes an absence off as a quiet day', () => {
		const strip = tileStrip(
			[
				{ date: '2026-09-03', state: 'fired', reading: 9 },
				{ date: '2026-09-01', state: 'absent' },
				{ date: '2026-09-02', state: 'quiet', reading: 1 },
				{ date: '2026-09-04', state: 'fired', reading: 12 }
			],
			{ thresholds: [5, 10] }
		);
		expect(strip?.tiles.map((tile) => tile.state)).toEqual(['absent', 'quiet', 'fired', 'fired']);
		expect(strip?.counts).toEqual({ quiet: 1, fired: 2, absent: 1 });
		expect(strip?.worst?.date).toBe('2026-09-04');
		expect(tileStrip([{ date: '2026-09-01', state: 'absent' }], { thresholds: [5, 10] })).toBeNull();
		expect(() => tileStrip([{ date: '2026-09-01', state: 'quiet', reading: 7 }], { thresholds: [5, 10] })).toThrow(/marked quiet/);
		expect(() => tileStrip([], { thresholds: [10, 5] })).toThrow(/sits above/);
	});

	test('paired blanks the one row under the attempts floor and draws the rest', () => {
		const rows: PairedInput[] = [
			{ label: 'speed', before: 10, after: 12, attempts: { before: 20, after: 20 } },
			{ label: 'thin', before: 10, after: 30, attempts: { before: 2, after: 20 } }
		];
		const shape = paired(rows, { minAttempts: 5 });
		expect(shape?.rows[0].percent).toBeCloseTo(120, 9);
		expect(shape?.rows[0].at).toBeGreaterThan(0.5);
		expect(shape?.rows[1].at).toBeNull();
		expect(shape?.rows[1].reason).toContain('Fewer than 5 attempts before the change');
		expect(shape?.half, 'the thin row does not widen the axis it is not drawn on').toBe(25);
		const short = rows.map((row) => ({ ...row, attempts: { before: 1, after: 1 } }));
		expect(paired(short, { minAttempts: 5 })).toBeNull();
		expect(pairedShortfall(short, { minAttempts: 5 })).toContain('fewer than 5 attempts');
		expect(pairedShortfall(rows, { minAttempts: 5 })).toBeNull();
	});

	test('overlapTimeline puts every lane on one clock and counts the most in flight at once', () => {
		const shape = overlapTimeline([
			{ id: 'b', source: 's', shard: 1, startMs: 1000, steps: [{ label: 'read', ms: 500 }] },
			{ id: 'a', source: 's', shard: 0, startMs: 0, steps: [{ label: 'fetch', ms: 1000 }, { label: 'write', ms: 1000 }] }
		]);
		expect(shape?.startMs).toBe(0);
		expect(shape?.endMs).toBe(2000);
		expect(shape?.lanes.map((lane) => lane.id)).toEqual(['a', 'b']);
		expect(shape?.lanes[0].steps.map((step) => [step.left, step.width])).toEqual([
			['0.0000%', '50.0000%'],
			['50.0000%', '50.0000%']
		]);
		expect(shape?.peak).toBe(2);
		expect(overlapTimeline([])).toBeNull();
	});

	const funnel: FlowStageInput[] = [
		{ label: 'Reached', arrived: 100, left: 60, drops: [{ label: 'Answered in words', count: 40 }] },
		{ label: 'Asked', arrived: 60, left: 50, drops: [{ label: 'Drew nothing', count: 10 }, { label: 'Zero', count: 0 }] },
		{ label: 'Published', arrived: 50, left: 50, drops: [] }
	];

	test('flow shares one top edge, and a drop lands in the column after its own stage', () => {
		const shape = flow(funnel, { narrow: false, frame: box, nodeWidth: 10, nodeGap: 8 });
		expect(shape?.kind).toBe('diagram');
		if (shape?.kind !== 'diagram') return;
		const stages = shape.nodes.filter((node) => !node.drop);
		expect(stages.every((node) => node.y === box.top)).toBe(true);
		const first = shape.nodes.find((node) => node.label === 'Answered in words');
		expect(first?.column, 'a first-stage drop sits beside the stage that lost it').toBe(1);
		expect(shape.nodes.some((node) => node.label === 'Zero'), 'a branch of zero is not a branch').toBe(false);
		const leaving = shape.ribbons.filter((ribbon) => ribbon.from === 'Reached').reduce((sum, ribbon) => sum + ribbon.value, 0);
		expect(leaving).toBe(100);
		expect(stages[0].height).toBeCloseTo((stages[1].height ?? 0) + (first?.height ?? 0), 6);
	});

	test('flow returns the stepped list from the same call, and lists counts that are not one flow', () => {
		const narrow = flow(funnel, { narrow: true, frame: box, nodeWidth: 10, nodeGap: 8 });
		expect(narrow?.kind).toBe('stepped');
		if (narrow?.kind === 'stepped') {
			expect(narrow.note).toBeNull();
			expect(narrow.stages.map((stage) => stage.share)).toEqual([100, 60, 50]);
		}
		const gained = funnel.map((stage, index) => (index === 1 ? { ...stage, arrived: 70, left: 60 } : stage));
		const listed = flow(gained, { narrow: false, frame: box, nodeWidth: 10, nodeGap: 8 });
		expect(listed?.kind).toBe('stepped');
		if (listed?.kind === 'stepped') expect(listed.note).toContain('not one flow');
		expect(flow([{ label: 'none', arrived: 0, left: 0, drops: [] }], { narrow: false, frame: box, nodeWidth: 10, nodeGap: 8 })).toBeNull();
	});

	test('pairedScatter needs both floors, and has nowhere to put a trend line', () => {
		const points: ScatterInput[] = Array.from({ length: 12 }, (_, index) => ({
			label: `kind-${index % 3}`,
			x: index,
			y: index * 2
		}));
		expect(pairedScatter(points.slice(0, 4), { frame: box, minRows: 10, minSubjects: 3, valueTicks: 4 })).toBeNull();
		expect(pairedScatterShortfall(points.slice(0, 4), { minRows: 10, minSubjects: 3 })).toContain('Only 4 of the 10 readings');
		const oneKind = points.map((point) => ({ ...point, label: 'kind-0' }));
		expect(pairedScatter(oneKind, { frame: box, minRows: 10, minSubjects: 3, valueTicks: 4 })).toBeNull();
		expect(pairedScatterShortfall(oneKind, { minRows: 10, minSubjects: 3 })).toContain('Only 1 of the 3 subjects');
		const shape = pairedScatter(points, { frame: box, minRows: 10, minSubjects: 3, valueTicks: 4 });
		expect(Object.keys(shape ?? {}).sort()).toEqual(['frame', 'marks', 'subjects', 'x', 'y']);
		expect(shape?.marks).toHaveLength(12);
		expect(shape?.subjects).toEqual(['kind-0', 'kind-1', 'kind-2']);
	});
});

test.describe('drawn by Svelte, rendered on the server', () => {
	const built = path.join(frontend, 'test-results', 'chart-vocabulary');
	const box = frame(400, 200);
	type Draw = (props: Record<string, unknown>) => string;
	const draw: Record<string, Draw> = {};

	/** One component compiled to a server module beside its siblings. A child
	 * component is compiled for real and its import pointed at the copy. */
	const compiled = serverCompiler(built);

	test.beforeAll(async () => {
		await compiled('src/lib/components/Reserved.svelte', 'Reserved', []);
		await compiled('src/lib/charts/d3/EmptyState.svelte', 'EmptyState', [
			['$lib/components/Reserved.svelte', './Reserved.server.mjs']
		]);
		await compiled('src/lib/components/ChartReadout.svelte', 'ChartReadout', []);
		for (const name of ['EmptyState', 'DateSeries', 'Distribution', 'PartsOfOne', 'TileStrip', 'Flow', 'PairedScatter']) {
			const module =
				name === 'EmptyState'
					? path.join(built, 'EmptyState.server.mjs')
					: await compiled(`src/lib/charts/d3/${name}.svelte`, name, [
							['./EmptyState.svelte', './EmptyState.server.mjs'],
							['$lib/components/ChartReadout.svelte', './ChartReadout.server.mjs']
						]);
			const loaded = await import(pathToFileURL(module).href);
			draw[name] = (props) => render(loaded.default, { props }).body;
		}
	});

	const sized = { name: 'test-chart', label: 'A chart under test', width: 400, height: 220 };

	test('the empty state keeps the chart height, and a wait is the only one with no words', () => {
		const waiting = draw.EmptyState({ ...sized, drawing: emptyState('loading') });
		expect(waiting).toContain('data-reserved="test-chart"');
		expect(waiting).not.toContain('empty-sentence');
		const failed = draw.EmptyState({ ...sized, drawing: emptyState('unreachable', 'September 2026 did not arrive.') });
		expect(failed).toContain('data-tone="warn"');
		expect(failed).toContain('September 2026 did not arrive.');
		const few = draw.EmptyState({ ...sized, drawing: emptyState('too-few', tooFewSentence(3, 160, 'readings')) });
		expect(few).toContain('block-size: 220px');
		expect(few).toContain('data-empty-state="too-few"');
		expect(few).toContain('data-tone="neutral"');
	});

	test('every type with no geometry draws the empty state it was handed', () => {
		const empty = emptyState('quiet', 'Nothing was recorded in these 30 days.');
		for (const name of ['DateSeries', 'Distribution', 'PartsOfOne', 'TileStrip', 'Flow', 'PairedScatter']) {
			const body = draw[name]({ ...sized, geometry: null, empty });
			expect(body, name).toContain('data-empty-state="quiet"');
			expect(body, name).toContain('Nothing was recorded in these 30 days.');
		}
	});

	test('the drawn marks are the geometry, one for one', () => {
		const empty = emptyState('quiet', 'Nothing.');
		const series = dateSeries(
			[{ label: 'one', token: '--chart-1', points: [{ date: '2026-09-01', value: 1 }, { date: '2026-09-02', value: 2 }] }],
			{ frame: box, density: 6, valueTicks: 4, padding: 0.2 }
		);
		expect(draw.DateSeries({ ...sized, geometry: series, empty }).match(/<path/g)).toHaveLength(1);
		const stacked = dateSeries(
			[
				{ label: 'one', token: '--chart-1', points: [{ date: '2026-09-01', value: 1 }] },
				{ label: 'two', token: '--chart-2', points: [{ date: '2026-09-01', value: 2 }] }
			],
			{ frame: box, stacked: true, density: 6, valueTicks: 4, padding: 0.2 }
		);
		expect(draw.DateSeries({ ...sized, geometry: stacked, empty }).match(/<rect/g)).toHaveLength(2);

		// No tooltip on a mark: the strip it is handed is the hover, under the plot.
		const hover = readoutOf({
			type: 'dateSeries',
			columns: ['1 Sep 2026'],
			series: [
				{ label: 'one', swatch: 'var(--chart-1)', values: [1], format: (value) => `${value}` },
				{ label: 'two', swatch: 'var(--chart-2)', values: [2], format: (value) => `${value}` }
			],
			notMeasured: 'Nothing was measured on this day',
			resting: 'last'
		});
		const held = draw.DateSeries({ ...sized, geometry: stacked, empty, readout: hover, readoutMaxShare: 1 });
		expect(held, 'a native tooltip on a mark').not.toContain('<title');
		expect(held).toContain('data-readout-columns="1"');
		expect(held).toContain('data-readout="test-chart"');
		// Two segments on one day meet once, and a line of the ground is drawn there.
		expect(held.match(/stroke="var\(--color-surface\)"/g)).toHaveLength(stacked?.joins.length ?? -1);
		expect(stacked?.joins).toHaveLength(1);

		const bins = distribution(Array.from({ length: 30 }, (_, index) => index % 6), { frame: box, minValues: 10, valueTicks: 5 });
		const binned = draw.Distribution({ ...sized, geometry: bins, empty });
		expect(binned.match(/<rect/g)).toHaveLength(bins?.bins.length ?? -1);
		expect(binned.match(/<path/g), 'one running-share curve').toHaveLength(1);

		const strip = tileStrip(
			[
				{ date: '2026-09-01', state: 'absent' },
				{ date: '2026-09-02', state: 'quiet' },
				{ date: '2026-09-03', state: 'fired' }
			],
			{ thresholds: [5, 10] }
		);
		const tiles = draw.TileStrip({ ...sized, geometry: strip, empty });
		for (const state of ['absent', 'quiet', 'fired']) expect(tiles).toContain(`data-tile-state="${state}"`);

		const parts = partsOfOne([{ label: 'r', parts: [{ label: 'a', value: 1 }, { label: 'b', value: 2 }] }], { order: ['a', 'b'] });
		expect(draw.PartsOfOne({ ...sized, geometry: parts, empty }).match(/class="parts-segment/g)).toHaveLength(2);
	});

	test('a scatter draws dots and no line through them', () => {
		const points = Array.from({ length: 9 }, (_, index) => ({ label: `k${index % 3}`, x: index, y: 9 - index }));
		const shape = pairedScatter(points, { frame: box, minRows: 9, minSubjects: 3, valueTicks: 4 });
		const body = draw.PairedScatter({ ...sized, geometry: shape, empty: emptyState('quiet', 'Nothing.') });
		expect(body.match(/<circle/g)).toHaveLength(9);
		expect(body).not.toContain('<path');
		expect(body).not.toContain('<polyline');
	});

	test('a flow is a diagram of filled ribbons where it is wide and a list where it is narrow', () => {
		const stages: FlowStageInput[] = [
			{ label: 'In', arrived: 10, left: 6, drops: [{ label: 'Out early', count: 4 }] },
			{ label: 'Done', arrived: 6, left: 6, drops: [] }
		];
		const empty = emptyState('quiet', 'Nothing.');
		const wide = draw.Flow({ ...sized, geometry: flow(stages, { narrow: false, frame: box, nodeWidth: 10, nodeGap: 8 }), empty });
		expect(wide).toContain('data-flow-shape="diagram"');
		expect(wide.match(/<path[^>]*fill="var\(--chart-1\)"/g)).toHaveLength(2);
		expect(wide).not.toMatch(/<path[^>]*stroke=/);
		const narrow = draw.Flow({ ...sized, geometry: flow(stages, { narrow: true, frame: box, nodeWidth: 10, nodeGap: 8 }), empty });
		expect(narrow).toContain('data-flow-shape="stepped"');
		expect(narrow).toContain('Out early: 4 (40%)');
	});
});
