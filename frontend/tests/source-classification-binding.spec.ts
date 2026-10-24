import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { expect, test } from '@playwright/test';
import ts from 'typescript';
import { backendPython } from './support/backend-python';

type Schema = {
	$defs?: Record<string, Schema>;
	$ref?: string;
	anyOf?: Schema[];
	properties?: Record<string, Schema>;
	type?: string;
};

type Primitive = 'boolean' | 'null' | 'number' | 'string';

const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const BANDS = path.join(REPO, 'frontend', 'src', 'lib', 'bands.ts');
const PYTHON_SCHEMA = [
	'import json',
	'from idhazh.contracts.taxonomy import SourceKindDefinition',
	'print(json.dumps(SourceKindDefinition.model_json_schema()))'
].join('\n');

function pythonTypes(schema: Schema, root: Schema): Primitive[] {
	if (schema.$ref) {
		const match = /^#\/\$defs\/([^/]+)$/.exec(schema.$ref);
		if (!match || !root.$defs?.[match[1]!]) {
			throw new Error(`Unsupported Python schema reference: ${schema.$ref}`);
		}
		return pythonTypes(root.$defs[match[1]!]!, root);
	}
	if (schema.anyOf) return schema.anyOf.flatMap((part) => pythonTypes(part, root)).sort();
	if (schema.type === 'string' || schema.type === 'boolean' || schema.type === 'number') {
		return [schema.type];
	}
	if (schema.type === 'null') return ['null'];
	throw new Error(`Unsupported Python schema type: ${JSON.stringify(schema)}`);
}

function typescriptTypes(node: ts.TypeNode): Primitive[] {
	if (ts.isUnionTypeNode(node)) return node.types.flatMap(typescriptTypes).sort();
	if (node.kind === ts.SyntaxKind.StringKeyword) return ['string'];
	if (node.kind === ts.SyntaxKind.BooleanKeyword) return ['boolean'];
	if (node.kind === ts.SyntaxKind.NumberKeyword) return ['number'];
	if (ts.isLiteralTypeNode(node)) {
		if (node.literal.kind === ts.SyntaxKind.NullKeyword) return ['null'];
		if (ts.isStringLiteral(node.literal)) return ['string'];
		if (node.literal.kind === ts.SyntaxKind.TrueKeyword || node.literal.kind === ts.SyntaxKind.FalseKeyword) {
			return ['boolean'];
		}
		if (ts.isNumericLiteral(node.literal)) return ['number'];
	}
	throw new Error(`Unsupported TypeScript field type: ${node.getText()}`);
}

function assertFieldTypeMatches(name: string, type: ts.TypeNode, property: Schema, root: Schema): void {
	expect(typescriptTypes(type).sort(), `TypeScript field ${name}`).toEqual(
		pythonTypes(property, root).sort()
	);
}

function pythonSchema(): Schema {
	const output = execFileSync(backendPython(REPO), ['-c', PYTHON_SCHEMA], {
		cwd: REPO,
		env: { ...process.env, PYTHONPATH: path.join(REPO, 'backend') },
		encoding: 'utf8'
	});
	return JSON.parse(output) as Schema;
}

test('the Python source-kind schema and TypeScript interface have the same fields and value types', () => {
	const schema = pythonSchema();
	if (!schema.properties) throw new Error('Python source-kind schema has no properties');

	const source = ts.createSourceFile(
		BANDS,
		readFileSync(BANDS, 'utf8'),
		ts.ScriptTarget.Latest,
		true,
		ts.ScriptKind.TS
	);
	const declaration = source.statements.find(
		(statement): statement is ts.InterfaceDeclaration =>
			ts.isInterfaceDeclaration(statement) && statement.name.text === 'SourceKindDefinition'
	);
	if (!declaration) throw new Error('bands.ts has no SourceKindDefinition interface');

	const fields = new Map<string, ts.PropertySignature>();
	for (const member of declaration.members) {
		if (!ts.isPropertySignature(member) || !member.type || !ts.isIdentifier(member.name)) {
			throw new Error('SourceKindDefinition must use named fields with declared types');
		}
		if (fields.has(member.name.text)) {
			throw new Error(`SourceKindDefinition repeats ${member.name.text}`);
		}
		fields.set(member.name.text, member);
	}

	expect([...fields.keys()].sort()).toEqual(Object.keys(schema.properties).sort());
	for (const [name, property] of Object.entries(schema.properties)) {
		const field = fields.get(name);
		if (!field?.type) throw new Error(`TypeScript is missing field ${name}`);
		assertFieldTypeMatches(name, field.type, property, schema);
	}
});

test('the Python type binding refuses a boolean field changed to string', () => {
	const schema = pythonSchema();
	const property = schema.properties?.show_on_item;
	if (!property) throw new Error('Python source-kind schema has no show_on_item field');
	const changedType = ts.factory.createKeywordTypeNode(ts.SyntaxKind.StringKeyword);
	expect(() => assertFieldTypeMatches('show_on_item', changedType, property, schema)).toThrow();
});
