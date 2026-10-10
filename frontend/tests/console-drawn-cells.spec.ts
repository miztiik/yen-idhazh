/** Which named console sinks can turn drawn data into markup or an address? */
import { expect, test } from '@playwright/test';
import { compile, parse, type AST } from 'svelte/compiler';
import { render } from 'svelte/server';
import type { Component } from 'svelte';
import { posix } from 'node:path';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
import ts from 'typescript';
import { drawnSourceFiles, readSource, scriptTree } from './support/console-sources';

interface ReviewedSink {
	readonly file: string;
	readonly attribute: string;
	readonly value: string;
	readonly origin: string;
	readonly count?: number;
}

// Exact expressions, not file exemptions. These existing surfaces retire in rows 6/11.
const GRANDFATHERED: readonly ReviewedSink[] = [
	{ file: 'src/lib/charts/Chart.svelte', attribute: '@html', value: '{@html svg}', count: 2,
		origin: 'Legacy server/chart-render.ts produces this SVG through renderToSvg; not a ledger text cell.' },
	{ file: 'src/routes/console/+page.svelte', attribute: 'fetch', value: '`${base}/telemetry/${month}.csv`',
		origin: 'Legacy static telemetry month; month comes from the published band months, not drawn text.' },
	{ file: 'src/routes/console/+layout.ts', attribute: 'fetch', value: '`${base}/console/band.json`',
		origin: 'Fixed published console band under the SvelteKit base.' },
	{ file: 'src/lib/components/ItemVisual.svelte', attribute: 'fetch', value: '`${__ASSET_BASE_URL__ || base}/${file}`',
		origin: 'Public reader only; publishedVisualData(file) validates a visual manifest path before fetch; asset origin is a build define.' }
];

const ADDRESS_ALLOWED: readonly ReviewedSink[] = [
	{ file: 'src/lib/components/ConsoleBand.svelte', attribute: 'href', value: 'href="{base}{band.worst.href}"',
		origin: 'readBand maps the worst route id to the fixed BAND_UNREAD route href, never a ledger URL.' },
	{ file: 'src/lib/components/ConsoleNav.svelte', attribute: 'href', value: 'href="{base}{route.href}"',
		origin: 'The fixed BAND_UNREAD route inventory.' },
	{ file: 'src/lib/components/DigestItem.svelte', attribute: 'href', value: 'href={day.href}',
		origin: 'Public reader day permalink from FoundStories, made from index date and recomputed item identity.' },
	{ file: 'src/lib/components/FilterBar.svelte', attribute: 'href', value: 'href={verticalHref(base, datePrefix, vertical.id)}',
		origin: 'Public reader internal topic link from links.ts and the published vertical id.' },
	{ file: 'src/lib/components/FilterBar.svelte', attribute: 'href', value: 'href={root}',
		origin: 'Public reader dayRoot(base, datePrefix), not article text.' },
	{ file: 'src/lib/components/FoundStories.svelte', attribute: 'href', value: '{href}',
		origin: 'Public reader local const href joins base, index date and recomputed item_id.' },
	{ file: 'src/lib/components/ItemMeta.svelte', attribute: 'href', value: 'href="{base}/{onDate}/#{other.item_id}"',
		origin: 'Public reader date and recomputed coverage item identity, not source_url.' },
	{ file: 'src/lib/components/ItemMeta.svelte', attribute: 'href', value: 'href="/{ran.date.replaceAll(\'-\', \'/\')}/#{ran.item_id}"',
		origin: 'Public reader run date and recomputed item identity.' },
	{ file: 'src/lib/components/ItemMeta.svelte', attribute: 'url', value: 'url={item.source_url}',
		origin: 'Existing public reader verification exit through SourceLink, deliberately not allowed to console ledger callers.' },
	{ file: 'src/lib/components/LeadingStories.svelte', attribute: 'href', value: 'href="#{story.item_id}"',
		origin: 'Public reader recomputed story identity, internal fragment only.' },
	{ file: 'src/lib/components/MoreDays.svelte', attribute: 'href', value: 'href="{base}/{day.date}/"',
		origin: 'Public reader day index date, internal day route.' },
	{ file: 'src/lib/components/NotHere.svelte', attribute: 'href', value: 'href={base || \'/\'}',
		origin: 'SvelteKit base or fixed site root.' },
	{ file: 'src/lib/components/PayloadState.svelte', attribute: 'href', value: 'href={other.href}',
		origin: 'Public reader held days from archive-calendar internal day addresses.' },
	{ file: 'src/lib/components/SiteFooter.svelte', attribute: 'href', value: 'href={repoUrl}',
		origin: 'Authored ui.repo_url passed by the root layout.' },
	{ file: 'src/lib/components/SiteHeader.svelte', attribute: 'href', value: 'href={base || \'/\'}',
		origin: 'SvelteKit base or fixed site root.' },
	{ file: 'src/lib/components/SourceLink.svelte', attribute: 'href', value: 'href={url}',
		origin: 'Existing public reader verification exit; ItemMeta is the reviewed source_url caller. Console callers remain refused.' },
	{ file: 'src/lib/components/ThroughputTrend.svelte', attribute: 'href', value: 'href={reference}',
		origin: 'Legacy Model measurementsReference, authored repo_url plus fixed documentation path.' },
	{ file: 'src/lib/console/explorer/RunStatus.svelte', attribute: 'href', value: 'href={href}',
		origin: 'Explorer answerLink, only the fixed #data-explorer-rows fragment or empty string.' },
	{ file: 'src/routes/console/+layout.svelte', attribute: 'href', value: 'href="#{group.id}"',
		origin: 'Authored console panel group id, internal fragment only.' },
	{ file: 'src/routes/console/+layout.svelte', attribute: 'band', value: 'band={data.band}',
		origin: 'readBand reconstructs the worst link from a validated route id and BAND_UNREAD, not a fetched source URL.' },
	{ file: 'src/routes/console/data-explorer/+page.svelte', attribute: 'href', value: 'href={`${data.docsBase}/blob/main/docs/how-to/query-a-ledger-from-the-console.md`}',
		origin: 'Page docsBase is authored ui.repo_url; suffix is a fixed documentation path.' },
	{ file: 'src/routes/console/data-explorer/+page.svelte', attribute: 'href', value: 'href={answerLink}',
		origin: 'Only the fixed #data-explorer-rows fragment or empty string, never the operator-written SQL.' },
	{ file: 'src/routes/console/model/+page.svelte', attribute: 'href', value: 'href={data.measurementsReference}',
		origin: 'Server page joins authored ui.repo_url with fixed docs/reference/pipeline-cost.md.' },
	{ file: 'src/routes/console/model/+page.svelte', attribute: 'href', value: 'href={data.faithfulnessReference}',
		origin: 'Server page joins authored ui.repo_url with fixed summary-quality documentation path.' },
	{ file: 'src/routes/console/model/+page.svelte', attribute: 'reference', value: 'reference={data.throughputReference}',
		origin: 'Legacy ThroughputTrend receives the authored repository documentation reference, not a ledger cell.' },
	{ file: 'src/lib/components/ChoiceTiles.svelte', attribute: 'spread', value: '{...{ [tileAttribute]: item.value }}',
		origin: 'The single computed attribute is typed data-${string}, not a URL or HTML attribute.' }
];

interface Sink {
	readonly file: string;
	readonly attribute: string;
	readonly value: string;
	readonly references?: readonly string[];
}

function memberName(expression: ts.Expression): string | null {
	if (ts.isPropertyAccessExpression(expression)) return expression.name.text;
	if (ts.isElementAccessExpression(expression) && ts.isStringLiteralLike(expression.argumentExpression)) return expression.argumentExpression.text;
	return ts.isIdentifier(expression) ? expression.text : null;
}

function sinks(file: string, source: string, addressProps: ReadonlyMap<string, ReadonlySet<string>> = new Map(),
	followComponents = false): Sink[] {
	const found: Sink[] = [];
	const add = (attribute: string, value: string, references?: readonly string[]) =>
		found.push({ file: file.replaceAll('\\', '/'), attribute, value, references });
	const tree = scriptTree(file, source);
	const components = new Map<string, string>();
	for (const statement of tree.statements) {
		if (!ts.isImportDeclaration(statement) || !ts.isStringLiteral(statement.moduleSpecifier) || !statement.importClause?.name) continue;
		const module = statement.moduleSpecifier.text;
		if (!module.endsWith('.svelte')) continue;
		components.set(statement.importClause.name.text, module.startsWith('$lib/') ? `src/lib/${module.slice(5)}` :
			posix.normalize(posix.join(posix.dirname(file.replaceAll('\\', '/')), module)));
	}
	function javascript(node: ts.Node): void {
		if (ts.isBinaryExpression(node) && node.operatorToken.kind >= ts.SyntaxKind.FirstAssignment &&
			node.operatorToken.kind <= ts.SyntaxKind.LastAssignment &&
			['innerHTML', 'outerHTML', 'srcdoc'].includes(memberName(node.left) ?? '')) {
			add('DOM HTML', node.getText(tree));
		}
		if (ts.isCallExpression(node)) {
			const name = memberName(node.expression);
			if (['fetch', 'sendBeacon', 'open', 'insertAdjacentHTML', 'write', 'writeln', 'html'].includes(name ?? '')) {
				const object = ts.isPropertyAccessExpression(node.expression) || ts.isElementAccessExpression(node.expression)
					? node.expression.expression.getText(tree) : '';
				if (name !== 'open' && name !== 'write' && name !== 'writeln' ||
					name === 'open' && ['window', 'globalThis'].includes(object) ||
					(name === 'write' || name === 'writeln') && object === 'document') {
					add(name ?? 'call', node.arguments[0]?.getText(tree) ?? '');
				}
			}
		}
		ts.forEachChild(node, javascript);
	}
	javascript(tree);
	if (!file.endsWith('.svelte')) return found;
	const root = parse(source, { modern: true });
	function references(parts: readonly (AST.Text | AST.ExpressionTag)[]): string[] {
		const names = new Set<string>();
		for (const part of parts) {
			if (part.type !== 'ExpressionTag') continue;
			const code = ts.createSourceFile(tree.fileName, `(${source.slice(part.start + 1, part.end - 1)})`, ts.ScriptTarget.Latest, true);
			function visit(node: ts.Node): void {
				if (ts.isIdentifier(node) && !(ts.isPropertyAccessExpression(node.parent) && node.parent.name === node)) names.add(node.text);
				ts.forEachChild(node, visit);
			}
			visit(code);
		}
		return [...names];
	}
	function fragment(fragment: AST.Fragment | null | undefined): void {
		fragment?.nodes.forEach(template);
	}
	function expression(start: number, end: number): void {
		const code = ts.createSourceFile(tree.fileName, source.slice(start, end), ts.ScriptTarget.Latest, true);
		// Template expressions can contain calls and assignments too.
		function visit(node: ts.Node): void {
			if (ts.isCallExpression(node) && ['fetch', 'sendBeacon', 'open', 'insertAdjacentHTML', 'write', 'writeln', 'html'].includes(memberName(node.expression) ?? '')) {
				add('template call', node.getText(code));
			}
			if (ts.isBinaryExpression(node) && ['innerHTML', 'outerHTML', 'srcdoc'].includes(memberName(node.left) ?? '') &&
				node.operatorToken.kind >= ts.SyntaxKind.FirstAssignment && node.operatorToken.kind <= ts.SyntaxKind.LastAssignment) {
				add('DOM HTML', node.getText(code));
			}
			ts.forEachChild(node, visit);
		}
		visit(code);
	}
	function template(node: AST.Fragment['nodes'][number]): void {
		if (node.type === 'Comment' || node.type === 'Text') return;
		if (node.type === 'HtmlTag') add('@html', source.slice(node.start, node.end));
		if ('attributes' in node) {
			for (const attribute of node.attributes) {
				if (attribute.type === 'SpreadAttribute') add('spread', source.slice(attribute.start, attribute.end));
				if (attribute.type === 'BindDirective' && ['innerHTML', 'outerHTML'].includes(attribute.name)) add('bind HTML', source.slice(attribute.start, attribute.end));
				if (attribute.type === 'Attribute') {
					const name = attribute.name;
					const value = attribute.value;
					const parts = value === true ? [] : Array.isArray(value) ? value : [value];
					const dynamic = parts.some((part) => part.type === 'ExpressionTag');
					const literal = source.slice(attribute.start, attribute.end);
					if (name === 'srcdoc') add(name, literal);
					else if (dynamic && (['href', 'src', 'srcset', 'action', 'formaction', 'xlink:href', 'url', 'reference', 'repoUrl', 'docsBase'].includes(name) ||
						(followComponents || /^src\/(?:lib\/console\/|routes\/console\/)/.test(file.replaceAll('\\', '/'))) &&
						addressProps.get(components.get('name' in node ? node.name : '') ?? '')?.has(name))) {
						// A base-prefixed fixed path is safe; another expression after base is not.
						const fixedBase = parts[0]?.type === 'ExpressionTag' && parts[0].expression.type === 'Identifier' &&
							parts[0].expression.name === 'base' && parts.slice(1).every((part) => part.type === 'Text');
						if (!fixedBase) add(name, literal, references(parts));
					}
					for (const part of parts) if (part.type === 'ExpressionTag') expression(part.start + 1, part.end - 1);
				}
			}
		}
		if (node.type === 'ExpressionTag') expression(node.start + 1, node.end - 1);
		if ('fragment' in node) fragment(node.fragment);
		if (node.type === 'EachBlock' || node.type === 'SnippetBlock') fragment(node.body);
		if (node.type === 'EachBlock') fragment(node.fallback);
		if (node.type === 'IfBlock') { fragment(node.consequent); fragment(node.alternate); }
		if (node.type === 'AwaitBlock') { fragment(node.pending); fragment(node.then); fragment(node.catch); }
	}
	fragment(root.fragment);
	return found;
}

function sinkKey(sink: Sink): string {
	return `${sink.file} | ${sink.attribute} | ${sink.value}`;
}

function boundaryErrors(file: string, source: string, reviewed: readonly ReviewedSink[] = [...ADDRESS_ALLOWED, ...GRANDFATHERED],
	addressProps: ReadonlyMap<string, ReadonlySet<string>> = new Map()): string[] {
	const allowed = new Set(reviewed.map(sinkKey));
	return sinks(file, source, addressProps).filter((sink) => !allowed.has(sinkKey(sink))).map(sinkKey);
}

/** Follow exposed component inputs feeding a named address sink, including local aliases. */
function componentAddressInputs(inputs: Readonly<Record<string, string>>): ReadonlyMap<string, ReadonlySet<string>> {
	const result = new Map<string, Set<string>>();
	const components = Object.entries(inputs).filter(([file]) => file.endsWith('.svelte')).map(([file, source]) => {
		const tree = scriptTree(file, source);
		const props = new Map<string, string>();
		const aliases = new Map<string, Set<string>>();
		function identifiers(node: ts.Node): Set<string> {
			const names = new Set<string>();
			function visit(child: ts.Node): void { if (ts.isIdentifier(child)) names.add(child.text); ts.forEachChild(child, visit); }
			visit(node);
			return names;
		}
		function visit(node: ts.Node): void {
			if (ts.isVariableDeclaration(node) && node.initializer) {
				if (ts.isObjectBindingPattern(node.name) && ts.isCallExpression(node.initializer) &&
					ts.isIdentifier(node.initializer.expression) && node.initializer.expression.text === '$props') {
					for (const entry of node.name.elements) if (ts.isIdentifier(entry.name)) {
						const property = entry.propertyName;
						props.set(entry.name.text, property && (ts.isIdentifier(property) || ts.isStringLiteral(property)) ? property.text : entry.name.text);
					}
				}
				if (ts.isIdentifier(node.name)) aliases.set(node.name.text, identifiers(node.initializer));
			}
			ts.forEachChild(node, visit);
		}
		visit(tree);
		return { file, source, props, aliases };
	});
	let changed = true;
	while (changed) {
		changed = false;
		for (const { file, source, props, aliases } of components) {
			const reached = new Set<string>();
			for (const sink of sinks(file, source, result, true)) {
				if (['@html', 'spread', 'fetch', 'bind HTML', 'DOM HTML', 'template call'].includes(sink.attribute)) continue;
				for (const name of sink.references ?? []) reached.add(name);
			}
			for (let size = -1; size !== reached.size;) {
				size = reached.size;
				for (const name of reached) for (const alias of aliases.get(name) ?? []) reached.add(alias);
			}
			const addresses = result.get(file) ?? new Set<string>();
			for (const name of reached) {
				const property = props.get(name);
				if (property !== undefined && !addresses.has(property)) { addresses.add(property); changed = true; }
			}
			result.set(file, addresses);
		}
	}
	return result;
}

function reviewErrors(inputs: Readonly<Record<string, string>>, reviewed: readonly ReviewedSink[],
	addressProps: ReadonlyMap<string, ReadonlySet<string>> = new Map()): string[] {
	const actual = Object.entries(inputs).flatMap(([file, source]) => sinks(file, source, addressProps)).map(sinkKey);
	const errors: string[] = [];
	const keys = new Set<string>();
	for (const entry of reviewed) {
		const key = sinkKey(entry);
		if (keys.has(key)) errors.push(`Duplicate review: ${key}`);
		keys.add(key);
		if (!entry.origin.trim() || !inputs[entry.file]) errors.push(`Unknown review: ${key}`);
		if (actual.filter((sink) => sink === key).length !== (entry.count ?? 1)) errors.push(`Missing or changed reviewed expression: ${key}`);
	}
	return errors;
}

test('drawn cell oracle refuses raw markup, insertion and extra fetches, not comments or native text', () => {
	const file = 'src/lib/console/machine/bite.svelte';
	for (const source of [
		'{@html rows.detail}', '<div bind:innerHTML={detail}></div>', '<iframe srcdoc={detail}></iframe>',
		'<script>node.innerHTML = row.detail;</script>', '<script>node["outerHTML"] = row.detail;</script>',
		'<script>node.insertAdjacentHTML("beforeend", row.detail);</script>', '<script>document.write(row.detail);</script>',
		'<script>$(node).html(row.detail);</script>', '<script>fetch(row.url);</script>',
		'<script>navigator.sendBeacon(row.url, row.detail);</script>', '<script>window.open(row.url);</script>',
		'<button onclick={() => fetch(row.url)}>Open</button>', '<a href={row.canonical_url}>Open</a>',
		'<a href="{base}/{row.url}">Open</a>', '<SourceLink url={row.source_url} />',
		'<RunStatus href={row.detail} />', '<div {...row}></div>'
	]) expect(boundaryErrors(file, source), source).not.toEqual([]);
	expect(boundaryErrors(file, '<script>// fetch(row.url)\nconst note = "innerHTML";</script><!-- {@html rows.detail} --><p>{rows.detail}</p>')).toEqual([]);
	expect(boundaryErrors(file, '<a href="{base}/console/">Console</a>')).toEqual([]);
});

test('native Svelte string rendering keeps web text as text, not elements or addresses', async () => {
	const source = '<script>let { value } = $props();</script><p>{value}</p>';
	const compiled = compile(source, { generate: 'server', filename: 'DrawnCell.svelte' });
	const code = compiled.js.code.replace(/(['"])svelte\/internal\/server\1/g,
		JSON.stringify(pathToFileURL(createRequire(import.meta.url).resolve('svelte/internal/server')).href));
	const module = await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`);
	const component: Component<{ value: string }> = module.default;
	const value = '<img src="https://untrusted.invalid/" onerror="fetch(row.url)"> & <script>run()</script>';
	const html = render(component, { props: { value } }).body;
	expect(html).toContain('&lt;img');
	expect(html).toContain('&lt;script');
	expect(html).toContain('&amp;');
	expect(html).not.toContain('<img');
	expect(html).not.toContain('<script');
	expect(boundaryErrors('src/lib/console/model/native-string.svelte', source)).toEqual([]);
});

test('review entries fail closed on an unknown file, typo, changed expression or missing origin', () => {
	const file = 'src/lib/components/SourceLink.svelte';
	const source = '<a href={url}>Read the original</a>';
	const reviewed: ReviewedSink = { file, attribute: 'href', value: 'href={url}', origin: 'Public verification exit' };
	expect(reviewErrors({ [file]: source }, [reviewed])).toEqual([]);
	for (const invalid of [
		{ ...reviewed, file: 'UNKNOWN' }, { ...reviewed, attribute: 'hfer' },
		{ ...reviewed, value: 'href={row.url}' }, { ...reviewed, origin: '' }
	]) expect(reviewErrors({ [file]: source }, [invalid])).not.toEqual([]);
	expect(boundaryErrors(file, '<a href={row.url}>Read</a>', [reviewed])).not.toEqual([]);
	expect(reviewErrors({ [file]: source }, [reviewed, reviewed])).not.toEqual([]);
});

test('console callers cannot pass ledger cells into another component address input', () => {
	const inputs = {
		'src/lib/components/SourceLink.svelte': '<script>let { url } = $props();</script><a href={url}>Read</a>',
		'src/lib/components/ItemMeta.svelte': '<script>let { item } = $props();</script><SourceLink url={item.source_url}/>',
		'src/lib/components/LinkBox.svelte': '<script>let { destination: target } = $props(); const address = target;</script><a href={address}>Read</a>',
		'src/lib/components/QuotedLink.svelte': '<script>let { path } = $props();</script><a href="/record/{path}">Read</a>',
		'src/lib/components/Wrapper.svelte': '<script>import ItemMeta from "./ItemMeta.svelte"; let { record } = $props();</script><ItemMeta item={record}/>'
	};
	const props = componentAddressInputs(inputs);
	for (const [component, property] of [['SourceLink', 'url'], ['ItemMeta', 'item'], ['LinkBox', 'destination'], ['QuotedLink', 'path'], ['Wrapper', 'record']]) {
		const source = `<script>import ${component} from '$lib/components/${component}.svelte';</script><${component} ${property}={row.detail}/>`;
		expect(boundaryErrors('src/lib/console/model/bite.svelte', source, [], props)).not.toEqual([]);
	}
});

test('named console sources have only their narrowly reviewed standing sinks', () => {
	const inputs = Object.fromEntries(drawnSourceFiles().map((file) => [file, readSource(file)]));
	const props = componentAddressInputs(inputs);
	expect(reviewErrors(inputs, [...ADDRESS_ALLOWED, ...GRANDFATHERED], props)).toEqual([]);
	expect(Object.entries(inputs).flatMap(([file, source]) => boundaryErrors(file, source, [...ADDRESS_ALLOWED, ...GRANDFATHERED], props))).toEqual([]);
});

test('reviewed fetch and link origins retain their closed construction', () => {
	expect(readSource('src/lib/components/ItemVisual.svelte')).toContain('if (!publishedVisualData(file))');
	expect(readSource('src/routes/console/data-explorer/+page.svelte')).toContain("? '#data-explorer-rows' : ''");
	expect(readSource('src/routes/console/data-explorer/+page.ts')).toContain('docsBase:');
	expect(readSource('src/lib/components/ChoiceTiles.svelte')).toContain('tileAttribute: `data-${string}`');
	expect(readSource('src/routes/console/model/+page.server.ts')).toContain("uiConfig().repo_url.replace(/\\/+$/, '')");
});
