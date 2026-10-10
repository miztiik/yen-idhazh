/** Which named console files cross a route's ownership boundary? */
import { expect, test } from '@playwright/test';
import { join } from 'node:path';
import ts from 'typescript';
import { groupedSpecs } from '../scripts/test-groups';
import { BAND_UNREAD, type RouteId } from '../src/lib/console/band';
import { FRONTEND, drawnSourceFiles, readSource, scriptTree, sourceFiles } from './support/console-sources';

const CROSS_ROUTE_SPECS = [
	'console-axis', 'console-band', 'console-chart-lifetime', 'console-chart-pending',
	'console-chrome', 'console-frame', 'console-mark-parity', 'console-model-panels',
	'console-model-rule', 'console-nav', 'console-polarity', 'console-readout',
	'console-shell', 'console-title', 'console-voices', 'console-window', 'console', 'console-built-page'
] as const;

const WINDOW_SHARED_IMPORTS = new Set([
	'./support/browser', './support/door-page', '../src/lib/console/band',
	'./support/console-expect/console-window', './support/span-said',
	'../src/lib/charts/viewport', './support/console-window/controls',
	'./support/console-window/readout', './support/console-window/machine-spans'
]);

function windowOwnershipErrors(file: string, source: string): string[] {
	const path = file.replaceAll('\\', '/');
	const tree = ts.createSourceFile(path, source, ts.ScriptTarget.Latest, true);
	const errors: string[] = [];
	function visit(node: ts.Node): void {
		if (path === 'tests/console-window.spec.ts' && ts.isStringLiteralLike(node) &&
			/(?:routes\/console\/|console\/machine\/|judgement-fixtures|server-panels|client-render)/.test(node.text)) {
			errors.push(`${path} owns route execution: ${node.text}`);
		}
		if (path === 'tests/console-window.spec.ts' && ts.isImportDeclaration(node) &&
			ts.isStringLiteral(node.moduleSpecifier) && !WINDOW_SHARED_IMPORTS.has(node.moduleSpecifier.text)) {
			errors.push(`${path} imports detailed execution: ${node.moduleSpecifier.text}`);
		}
		if (/^tests\/support\/console-expect\/console-window\//.test(path) &&
			(ts.isFunctionLike(node) || ts.isCallExpression(node))) {
			errors.push(`${path} contains executable expectations`);
		}
		ts.forEachChild(node, visit);
	}
	visit(tree);
	return errors;
}

const DEFINE_OWNERS = new Set(['vite.config.ts', 'src/app.d.ts', 'src/lib/console/route-console.ts']);

function namedRoutes(source: string): RouteId[] {
	return BAND_UNREAD.routes.filter(({ href }) => {
		const escaped = href.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
		return new RegExp('([\'"`])' + escaped + '\\1').test(source);
	}).map(({ id }) => id);
}

function routeScopeErrors(file: string, source: string): string[] {
	const path = file.replaceAll('\\', '/');
	const routes = namedRoutes(source);
	const errors: string[] = [];
	const owned = /^tests\/support\/(?:console-expect\/[^/]+|panel-drivers)\/([^/]+)\.ts$/.exec(path);
	if (owned) {
		const owner = owned[1];
		const foreign = routes.filter((route) => owner === 'index' || route !== owner);
		if (foreign.length) errors.push(`${path} names routes it does not own: ${foreign.join(', ')}`);
	} else if (/^tests\/[^/]+\.spec\.ts$/.test(path)) {
		const name = path.slice('tests/'.length, -'.spec.ts'.length);
		if ((CROSS_ROUTE_SPECS as readonly string[]).includes(name) && routes.length) {
			errors.push(`${path} is cross-route and names: ${routes.join(', ')}`);
		} else if (name !== 'console-machine-page' && routes.length >= 2) {
			errors.push(`${path} names more than one route: ${routes.join(', ')}`);
		}
	}
	return errors;
}

function defineScopeErrors(file: string, source: string): string[] {
	const path = file.replaceAll('\\', '/');
	const scripts = path.endsWith('.svelte')
		? [...source.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/g)].map((match) => match[1]).join('\n')
		: source;
	const tree = ts.createSourceFile(path, scripts, ts.ScriptTarget.Latest, true);
	const errors = new Set<string>();
	if (path.endsWith('.svelte') && !DEFINE_OWNERS.has(path)) {
		const scanner = ts.createScanner(ts.ScriptTarget.Latest, true, ts.LanguageVariant.Standard, source);
		for (let token = scanner.scan(); token !== ts.SyntaxKind.EndOfFileToken; token = scanner.scan()) {
			if (token === ts.SyntaxKind.Identifier && scanner.getTokenText() === '__CONSOLE__') {
				errors.add(`${path} names __CONSOLE__ outside its three owners`);
			}
		}
	}
	function imported(module: ts.Expression | undefined): void {
		if (!module || !ts.isStringLiteralLike(module)) return;
		if (!/(?:^|\/)route-console(?:\.[jt]s)?$/.test(module.text.split(/[?#]/)[0])) return;
		if (path !== 'src/lib/server/config.ts' && !path.startsWith('src/routes/console/')) {
			errors.add(`${path} imports route-console outside the config loader or console routes`);
		}
	}
	function visit(node: ts.Node): void {
		if (ts.isIdentifier(node) && node.text === '__CONSOLE__' && !DEFINE_OWNERS.has(path)) {
			errors.add(`${path} names __CONSOLE__ outside its three owners`);
		}
		if (ts.isImportDeclaration(node) || ts.isExportDeclaration(node)) imported(node.moduleSpecifier);
		if (ts.isImportEqualsDeclaration(node) && ts.isExternalModuleReference(node.moduleReference)) {
			imported(node.moduleReference.expression);
		}
		if (ts.isImportTypeNode(node) && ts.isLiteralTypeNode(node.argument)) imported(node.argument.literal);
		if (ts.isCallExpression(node) && (
			node.expression.kind === ts.SyntaxKind.ImportKeyword ||
			(ts.isIdentifier(node.expression) && node.expression.text === 'require')
		)) imported(node.arguments[0]);
		ts.forEachChild(node, visit);
	}
	visit(tree);
	return [...errors];
}

function imports(tree: ts.SourceFile): ts.ImportDeclaration[] {
	return tree.statements.filter(ts.isImportDeclaration);
}

function movedRoutes(sources: Readonly<Record<string, string>>): RouteId[] {
	return BAND_UNREAD.routes.filter(({ id }) => Object.entries(sources).some(([file, source]) => {
		const path = file.replaceAll('\\', '/');
		const route = id === 'pipelines' ? 'src/routes/console/' : `src/routes/console/${id}/`;
		const owns = path.startsWith(`src/lib/console/${id}/`) ||
			(path.startsWith(route) && !path.slice(route.length).includes('/'));
		if (!owns) return false;
		return imports(scriptTree(path, source)).some((node) => ts.isStringLiteral(node.moduleSpecifier) &&
			/^(?:\$lib\/console\/queries\/|(?:\.\.\/)+queries\/)/.test(node.moduleSpecifier.text));
	})).map(({ id }) => id);
}

function doorFixtureErrors(file: string, source: string, moved: readonly RouteId[]): string[] {
	const path = file.replaceAll('\\', '/');
	if (!/^tests\/[^/]+\.spec\.ts$/.test(path)) return [];
	const tree = scriptTree(path, source);
	const imported = imports(tree);
	const shared = imported.some((node) => ts.isStringLiteral(node.moduleSpecifier) &&
		/^\.\/support\/(?:console-expect(?:\/|$)|console-panels$|panel-drivers(?:\/|$))/.test(node.moduleSpecifier.text));
	// Quoted address samples in a pure oracle do not open a page.
	function usesBrowser(input: ts.Node): boolean {
		let browserCall = false;
		function visit(node: ts.Node): void {
			if (ts.isCallExpression(node) && ts.isPropertyAccessExpression(node.expression) &&
				['goto', 'newPage', 'newContext'].includes(node.expression.name.text)) browserCall = true;
			if (ts.isParameter(node) && ts.isObjectBindingPattern(node.name) &&
				node.name.elements.some((entry) => ts.isIdentifier(entry.name) &&
					['page', 'browser', 'context'].includes((entry.propertyName ?? entry.name).getText(tree)))) browserCall = true;
			ts.forEachChild(node, visit);
		}
		visit(input);
		return browserCall;
	}
	if (!usesBrowser(tree) || !moved.some((route) => shared || namedRoutes(source).includes(route))) return [];
	const fixtures = new Map<string, boolean>();
	for (const node of imported) {
		const bindings = node.importClause?.namedBindings;
		if (!bindings || !ts.isNamedImports(bindings) || node.importClause?.isTypeOnly) continue;
		for (const entry of bindings.elements) {
			if (!entry.isTypeOnly && (entry.propertyName ?? entry.name).text === 'test') {
				fixtures.set(entry.name.text, ts.isStringLiteral(node.moduleSpecifier) && node.moduleSpecifier.text === './support/door-page');
			}
		}
	}
	function fixture(expression: ts.Expression, seen = new Set<string>()): boolean | undefined {
		if (ts.isPropertyAccessExpression(expression)) return fixture(expression.expression, seen);
		if (ts.isCallExpression(expression) && ts.isPropertyAccessExpression(expression.expression) &&
			expression.expression.name.text === 'extend') return fixture(expression.expression.expression, seen);
		if (!ts.isIdentifier(expression) || seen.has(expression.text)) return undefined;
		if (fixtures.has(expression.text)) return fixtures.get(expression.text);
		seen.add(expression.text);
		for (const statement of tree.statements) {
			if (!ts.isVariableStatement(statement)) continue;
			const declaration = statement.declarationList.declarations.find((entry) =>
				ts.isIdentifier(entry.name) && entry.name.text === expression.text);
			if (declaration?.initializer) return fixture(declaration.initializer, seen);
		}
		return undefined;
	}
	let wrongFixture = false;
	function registration(node: ts.Node): void {
		if (ts.isCallExpression(node) && fixture(node.expression) === false &&
			!(ts.isPropertyAccessExpression(node.expression) && node.expression.name.text === 'describe') &&
			node.arguments.some((argument) => (ts.isArrowFunction(argument) || ts.isFunctionExpression(argument)) && usesBrowser(argument))) wrongFixture = true;
		ts.forEachChild(node, registration);
	}
	registration(tree);
	return [...fixtures.values()].includes(true) && !wrongFixture ? [] :
		[`${path} opens a moved route without test from ./support/door-page`];
}

function supportFiles(): string[] {
	const routes = BAND_UNREAD.routes.map(({ id }) => id);
	return [
		...CROSS_ROUTE_SPECS.flatMap((name) => ['index', ...routes].map(
			(route) => `tests/support/console-expect/${name}/${route}.ts`
		)),
		...['index', ...routes].map((route) => `tests/support/panel-drivers/${route}.ts`)
	];
}

function specFiles(): string[] {
	return [...new Set([...Object.values(groupedSpecs(join(FRONTEND, 'tests'))).flat(),
		'console-built-page.spec.ts', 'console-drawn-cells.spec.ts', 'whole-day.spec.ts'])]
		.map((name) => `tests/${name}`);
}

test('quoted href matching covers all six routes and counts distinct routes only', () => {
	expect(BAND_UNREAD.routes).toHaveLength(6);
	for (const { id, href } of BAND_UNREAD.routes) {
		for (const quote of ["'", '"', '`']) {
			expect(namedRoutes(`${quote}${href}${quote}`)).toEqual([id]);
			expect(namedRoutes(`${quote}${href}${quote}; ${quote}${href}${quote}`)).toEqual([id]);
		}
		expect(namedRoutes(`'${href}"`)).toEqual([]);
		expect(namedRoutes(`'${href}child/'`)).toEqual([]);
		expect(namedRoutes(href)).toEqual([]);
	}
});

test('each route owns only its expectations and drivers, and indexes own no address', () => {
	for (const { id, href } of BAND_UNREAD.routes) {
		for (const directory of ['tests/support/console-expect/console-nav', 'tests/support/panel-drivers']) {
			expect(routeScopeErrors(`${directory}/${id}.ts`, `const href = '${href}';`)).toEqual([]);
			expect(routeScopeErrors(`${directory}/index.ts`, `const href = '${href}';`)).toHaveLength(1);
			for (const other of BAND_UNREAD.routes.filter((route) => route.id !== id)) {
				expect(routeScopeErrors(`${directory}/${id}.ts`, `const href = '${other.href}';`)).toHaveLength(1);
			}
		}
		for (const name of CROSS_ROUTE_SPECS) {
			expect(routeScopeErrors(`tests/${name}.spec.ts`, `const href = '${href}';`)).toHaveLength(1);
		}
	}
	const two = BAND_UNREAD.routes.slice(0, 2).map(({ href }) => `'${href}'`).join(', ');
	expect(routeScopeErrors('tests/console-machine-page.spec.ts', two)).toEqual([]);
	expect(routeScopeErrors('tests/console-machine-data.spec.ts', two)).toHaveLength(1);
	expect(routeScopeErrors(String.raw`tests\console-machine-data.spec.ts`, two)).toHaveLength(1);
});

test('the console define and imports cannot move into shared code or pure-parser specs', () => {
	for (const path of DEFINE_OWNERS) expect(defineScopeErrors(path, 'const chosen = __CONSOLE__;')).toEqual([]);
	for (const path of ['src/lib/components/Panel.svelte', 'tests/appearance-config.spec.ts']) {
		const code = 'const chosen = __CONSOLE__;';
		expect(defineScopeErrors(path, path.endsWith('.svelte') ? `<script lang="ts">${code}</script>` : code)).toHaveLength(1);
	}
	expect(defineScopeErrors('src/lib/components/Panel.svelte', '<p>{__CONSOLE__.shared.chart_height}</p>')).toHaveLength(1);
	const module = '$lib/console/route-console';
	for (const code of [
		`import { routeConsole } from '${module}';`, `import type { RouteConsole } from '${module}';`,
		`import '${module}';`, `export { routeConsole } from '${module}';`,
		`import value = require('${module}');`, `const value = import('${module}');`,
		`type Value = import('${module}').RouteConsole;`, `const value = require('${module}');`
	]) {
		expect(defineScopeErrors('src/lib/server/config.ts', code)).toEqual([]);
		expect(defineScopeErrors('src/routes/console/+page.server.ts', code)).toEqual([]);
		expect(defineScopeErrors('tests/appearance-config.spec.ts', code)).toHaveLength(1);
		expect(defineScopeErrors('src/lib/components/Panel.svelte', `<script>${code}</script>`)).toHaveLength(1);
	}
	expect(defineScopeErrors('tests/appearance-config.spec.ts', "import { routeConsolesFrom } from '../src/lib/server/config';")).toEqual([]);
	expect(defineScopeErrors('src/routes/console-other/+page.ts', `import '${module}';`)).toHaveLength(1);
	expect(defineScopeErrors('tests/appearance-config.spec.ts', "import { routeConsolesFrom } from '../src/lib/console/route-console.ts';")).toHaveLength(1);
	expect(defineScopeErrors('tests/console-route-scope.spec.ts', `const sample = "import '${module}';";`)).toEqual([]);
});

test('named expectations, drivers and specs keep route ownership', () => {
	const errors = [...supportFiles(), ...specFiles()].flatMap((file) => routeScopeErrors(file, readSource(file)));
	expect(errors, 'Move quoted addresses to the owning route expectation or driver').toEqual([]);
});

test('shared window ownership rejects route execution and callback expectations without route addresses', () => {
	for (const path of ['tests/console-window.spec.ts', String.raw`tests\console-window.spec.ts`]) {
		expect(windowOwnershipErrors(path, "import { judgeDay } from './support/console-window/judgement-fixtures';")).toHaveLength(2);
		expect(windowOwnershipErrors(path, "const panel = 'src/routes/console/judgement/JudgeAgreement.svelte';")).toHaveLength(1);
		expect(windowOwnershipErrors(path, "import { machineSpan } from './support/console-window/machine-spans';")).toEqual([]);
		expect(windowOwnershipErrors(path, "import { test } from './support/door-page';")).toEqual([]);
	}
	expect(windowOwnershipErrors('tests/support/console-expect/console-window/judgement.ts', 'export const EXPECT = { execute: () => true };')).toHaveLength(1);
	expect(windowOwnershipErrors('tests/support/console-expect/console-window/judgement.ts', "export const EXPECT = { windowed: ['judge-agreement'] };")).toEqual([]);
	const files = ['tests/console-window.spec.ts', ...['index', ...BAND_UNREAD.routes.map(({ id }) => id)].map(
		(route) => `tests/support/console-expect/console-window/${route}.ts`
	)];
	expect(files.flatMap((file) => windowOwnershipErrors(file, readSource(file)))).toEqual([]);
});

test('named sources expose the console define only through its route boundary', () => {
	const files = [...sourceFiles(), ...supportFiles(), ...specFiles()];
	expect(new Set(sourceFiles()).size).toBe(sourceFiles().length);
	const errors = files.flatMap((file) => defineScopeErrors(file, readSource(file)));
	expect(errors, 'Pass console values as props; test the parser through the server config loader').toEqual([]);
});

test('a moved route requires the cached fixture only for browser execution', () => {
	const href = BAND_UNREAD.routes.find(({ id }) => id === 'machine')!.href;
	const sources = {
		'src/lib/console/machine/PlatformMixPanel.svelte': "<script>import { platformMixQuery } from '$lib/console/queries/machine';</script>",
		'src/routes/console/model/+page.svelte': '<!-- import anything from $lib/console/queries/model -->'
	};
	const moved = movedRoutes(sources);
	expect(moved).toEqual(['machine']);
	const browser = `test('open', async ({ page }) => { await page.goto('${href}'); });`;
	for (const fixture of ['@playwright/test', './support/browser']) {
		expect(doorFixtureErrors('tests/route.spec.ts', `import { test } from '${fixture}'; ${browser}`, moved)).toHaveLength(1);
	}
	for (const fixture of [
		"import { test } from './support/door-page';",
		"import { test as browserTest } from './support/door-page'; const test = browserTest.extend({});"
	]) expect(doorFixtureErrors('tests/route.spec.ts', `${fixture} ${browser}`, moved)).toEqual([]);
	expect(doorFixtureErrors('tests/route.spec.ts', `import type { test } from './support/door-page'; ${browser}`, moved)).toHaveLength(1);
	expect(doorFixtureErrors('tests/route.spec.ts', `import { expect } from './support/door-page'; ${browser}`, moved)).toHaveLength(1);
	expect(doorFixtureErrors('tests/route.spec.ts',
		`import { test as unused } from './support/door-page'; import { test } from '@playwright/test'; ${browser}`, moved)).toHaveLength(1);
	for (const helper of ['console-expect/console-frame', 'console-panels', 'panel-drivers']) {
		const source = `import { BY_ROUTE } from './support/${helper}'; test('open', async ({ page }) => helper(page));`;
		expect(doorFixtureErrors('tests/route.spec.ts', source, moved)).toHaveLength(1);
		expect(doorFixtureErrors('tests/route.spec.ts', `${source} import { test } from './support/door-page';`, moved)).toEqual([]);
	}
	expect(doorFixtureErrors('tests/pure.spec.ts', `const sample = '${href}'; test('literal', () => expect(sample).toBeTruthy());`, moved)).toEqual([]);
	expect(doorFixtureErrors('tests/pure.spec.ts', "import { BY_ROUTE } from './support/console-expect/console-nav'; test('shape', () => expect(BY_ROUTE).toBeTruthy());", moved)).toEqual([]);
	expect(doorFixtureErrors('tests/unmoved.spec.ts', browser, [])).toEqual([]);
});

test('the shipped Hardware query remains a moved route and its browser consumers use door-page', () => {
	const sources = Object.fromEntries(drawnSourceFiles().map((file) => [file, readSource(file)]));
	const moved = movedRoutes(sources);
	expect(moved).toContain('machine');
	expect(specFiles().flatMap((file) => doorFixtureErrors(file, readSource(file), moved))).toEqual([]);
});
