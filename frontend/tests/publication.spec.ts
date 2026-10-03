import { expect, test } from '@playwright/test';
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { publicFiles, stateFiles } from '../src/lib/server/publication';
import { indexMonths, publishedDates, telemetryMonths } from '../src/lib/server/payload';
import ts from 'typescript';
import { stagedPath } from '../scripts/staged-publication.mjs';
import { shellSeedItems } from '../src/lib/server/config';

function inventory(files: string[]): string {
	return JSON.stringify({
		version: '2026-10-03', changelog: [], dates: [],
		entries: files.map((file) => ({
			root: file.startsWith('state/') ? 'state' : 'public',
			path: file.startsWith('state/') ? file.slice('state/'.length) : file,
			bytes: 0, items: 0
		})),
		total_bytes: 0, total_items: 0
	}) + '\n';
}

test('staging serves named days and marks but never run inputs', () => {
	expect(stagedPath('digest/2026/08/30/run.json', false)).toBeNull();
	expect(stagedPath('digest/2026/08/30/digest.json', true)).toBe('digest/2026/08/30/digest.json');
	expect(stagedPath('digest/2026/08/30/story-01.json', false)).toBe('digest/2026/08/30/story-01.json');
	expect(stagedPath('digest/2026/08/30/story-01.json', true)).toBeNull();
	expect(stagedPath('assist/index/2026-08.bin', false)).toBe('index/2026-08.bin');
	expect(stagedPath('publication.json', false)).toBeNull();
});

test('only a canary build uses the seed count from its named fixture config', () => {
	const previous = process.env.CANARY_BUILD;
	try {
		delete process.env.CANARY_BUILD;
		const production = shellSeedItems();
		const configured = JSON.parse(readFileSync(join(import.meta.dirname, '..', '..',
			'config', 'canary.json'), 'utf8')).shell_seed_items;
		process.env.CANARY_BUILD = '1';
		expect(shellSeedItems()).toBe(configured);
		delete process.env.CANARY_BUILD;
		expect(shellSeedItems()).toBe(production);
	} finally {
		if (previous === undefined) delete process.env.CANARY_BUILD;
		else process.env.CANARY_BUILD = previous;
	}
});

test('the frontend publication field set matches the producer contract', () => {
	const schema = JSON.parse(readFileSync(join(import.meta.dirname, '..', '..', 'tests',
		'fixtures', 'contracts', 'publication-inventory', 'schema.json'), 'utf8'));
	const source = readFileSync(join(import.meta.dirname, '..', 'src', 'lib', 'server', 'publication.ts'), 'utf8');
	const tree = ts.createSourceFile('publication.ts', source, ts.ScriptTarget.Latest, true);
	const model = tree.statements.find((node): node is ts.InterfaceDeclaration =>
		ts.isInterfaceDeclaration(node) && node.name.text === 'PublicationInventory');
	expect(model).toBeDefined();
	expect(model?.members.map((member) => member.name?.getText(tree)).sort())
		.toEqual(Object.keys(schema.properties).sort());
});

test('publication file vocabulary keeps public and state names distinct', () => {
	const root = mkdtempSync(join(tmpdir(), 'publication-vocabulary-'));
	try {
		for (const files of [['digest/2026/08/30/digest.json'], ['state/feed-health/2026/08/30/run.csv']]) {
			writeFileSync(join(root, 'publication.json'), inventory(files));
			expect(publicFiles(root)).toEqual(files.filter((file) => !file.startsWith('state/')));
			expect(stateFiles(root)).toEqual(files.filter((file) => file.startsWith('state/'))
				.map((file) => file.slice('state/'.length)));
		}
		for (const file of ['../day.json', '/day.json', 'state\\day.csv', 'state//day.csv']) {
			writeFileSync(join(root, 'publication.json'), inventory([file]));
			expect(() => publicFiles(root)).toThrow(/invalid relative file path/);
		}
	} finally {
		rmSync(root, { recursive: true, force: true });
	}
});

test('the frontend entry root vocabulary matches the producer contract', () => {
	const schema = JSON.parse(readFileSync(join(import.meta.dirname, '..', '..', 'tests',
		'fixtures', 'contracts', 'publication-inventory', 'schema.json'), 'utf8'));
	const entry = Object.values(schema.$defs).find((value) =>
		(value as { properties?: { root?: unknown } }).properties?.root);
	const roots = (entry as { properties: { root: { enum: string[] } } }).properties.root.enum;
	const source = readFileSync(join(import.meta.dirname, '..', 'src', 'lib', 'server', 'publication.ts'), 'utf8');
	const tree = ts.createSourceFile('publication.ts', source, ts.ScriptTarget.Latest, true);
	const model = tree.statements.find((node): node is ts.InterfaceDeclaration =>
		ts.isInterfaceDeclaration(node) && node.name.text === 'PublicationInventory');
	const entries = model?.members.find((member) => member.name?.getText(tree) === 'entries');
	expect(entries && ts.isPropertySignature(entries) && entries.type &&
		ts.isArrayTypeNode(entries.type)).toBeTruthy();
	if (!entries || !ts.isPropertySignature(entries) || !entries.type ||
		!ts.isArrayTypeNode(entries.type) || !ts.isTypeLiteralNode(entries.type.elementType)) {
		throw new Error('Publication entries must declare their element fields.');
	}
	const root = entries.type.elementType.members.find((member) => member.name?.getText(tree) === 'root');
	if (!root || !ts.isPropertySignature(root) || !root.type || !ts.isUnionTypeNode(root.type)) {
		throw new Error('Publication entry root must declare its vocabulary.');
	}
	const declared = root.type.types.map((node) => {
		if (!ts.isLiteralTypeNode(node) || !ts.isStringLiteral(node.literal)) {
			throw new Error('Publication entry root must name string literals.');
		}
		return node.literal.text;
	});
	expect(declared.sort()).toEqual([...roots].sort());
});

test('publication discovery reads named inventory files, not other files in the tree', () => {
	const root = mkdtempSync(join(tmpdir(), 'publication-'));
	try {
		const files = [
			'assist/index/2026-08.json', 'digest/2026/08/30/digest.json',
			'state/feed-health/2026/08/30/run.csv', 'telemetry/2026-08.csv'
		];
		writeFileSync(join(root, 'publication.json'), inventory(files));
		const day = join(root, 'digest', '2026', '08', '30');
		mkdirSync(day, { recursive: true });
		writeFileSync(join(day, 'digest.json'), '{}\n');
		const stray = join(root, 'digest', '2027', '01', '01');
		mkdirSync(stray, { recursive: true });
		writeFileSync(join(stray, 'digest.json'), '{}\n');
		expect(publicFiles(root)).toEqual(files.filter((file) => !file.startsWith('state/')));
		expect(stateFiles(root)).toEqual(['feed-health/2026/08/30/run.csv']);
		expect(publishedDates(join(root, 'digest'), -1)).toEqual(['2026-08-30']);
		expect(indexMonths(join(root, 'assist', 'index'), -1)).toEqual(['2026-08']);
		expect(telemetryMonths(join(root, 'telemetry'), -1)).toEqual(['2026-08']);
	} finally {
		rmSync(root, { recursive: true, force: true });
	}
});

test('a missing or unsafe inventory fails rather than discovering replacement files', () => {
	const root = mkdtempSync(join(tmpdir(), 'publication-'));
	try {
		expect(() => publicFiles(root)).toThrow(/inventory is missing/);
		writeFileSync(join(root, 'publication.json'), inventory(['../secret.json']));
		expect(() => publicFiles(root)).toThrow(/invalid relative file path/);
	} finally {
		rmSync(root, { recursive: true, force: true });
	}
});

test('legacy file-list inventories stay readable without a directory migration', () => {
	const root = mkdtempSync(join(tmpdir(), 'publication-legacy-'));
	try {
		writeFileSync(join(root, 'publication.json'), JSON.stringify({
			version: '2026-10-03', changelog: [], dates: [],
			files: ['digest/2026/08/30/digest.json', 'state/feed-health/2026/08/30/run.csv'],
			state_files: ['feed-health/2026/08/30/run.csv']
		}));
		expect(publicFiles(root)).toEqual(['digest/2026/08/30/digest.json']);
		expect(stateFiles(root)).toEqual(['feed-health/2026/08/30/run.csv']);
	} finally {
		rmSync(root, { recursive: true, force: true });
	}
});
