/** Refuse obvious non-questions before the engine sees them.
 *
 * This is a courtesy for the operator, not the boundary. The browser content
 * policy is the boundary on files and hosts.
 */

import type { AskRefusal } from './slice-shapes';

const READ_ONLY = new Set(['SELECT', 'WITH', 'DESCRIBE', 'SUMMARIZE', 'EXPLAIN']);

type Scan = { statements: number; firstWord: string; sql: string };

const TRAILING_SEMICOLON = /;\s*(?:(?:--[^\n]*)|(?:\/\*[\s\S]*?\*\/)|\s)*$/;

function scan(sql: string): Scan {
	let quote: string | null = null;
	let line = false;
	let block = false;
	let statements = 0;
	let firstWord = '';
	let current = '';
	for (let at = 0; at < sql.length; at += 1) {
		const char = sql[at] ?? '';
		const next = sql[at + 1] ?? '';
		if (line) {
			current += char;
			if (char === '\n') line = false;
			continue;
		}
		if (block) {
			current += char;
			if (char === '*' && next === '/') {
				current += next;
				at += 1;
				block = false;
			}
			continue;
		}
		if (quote !== null) {
			current += char;
			if (char === quote && next === quote) {
				current += next;
				at += 1;
			} else if (char === quote) {
				quote = null;
			}
			continue;
		}
		if (char === '-' && next === '-') {
			current += char + next;
			at += 1;
			line = true;
			continue;
		}
		if (char === '/' && next === '*') {
			current += char + next;
			at += 1;
			block = true;
			continue;
		}
		if (char === "'" || char === '"') {
			quote = char;
			current += char;
			continue;
		}
		if (/[A-Za-z]/.test(char) && firstWord === '') {
			const found = /^[A-Za-z_][A-Za-z0-9_]*/.exec(sql.slice(at));
			if (found) firstWord = found[0].toUpperCase();
		}
		if (char === ';') {
			if (current.trim() !== '') statements += 1;
			current = '';
			continue;
		}
		current += char;
	}
	if (current.trim() !== '') statements += 1;
	return { statements, firstWord, sql: sql.trim().replace(TRAILING_SEMICOLON, '') };
}

export function checkStatement(sql: string, maxChars: number): { sql: string; refusal: AskRefusal | null } {
	if (sql.length > maxChars) return { sql, refusal: { kind: 'too-long', chars: sql.length, max: maxChars } };
	const read = scan(sql.trim().replace(TRAILING_SEMICOLON, ''));
	if (read.statements !== 1) return { sql, refusal: { kind: 'statements', count: read.statements } };
	if (!READ_ONLY.has(read.firstWord)) return { sql, refusal: { kind: 'not-read-only', word: read.firstWord || '(empty)' } };
	return { sql: read.sql, refusal: null };
}

export function statementKind(sql: string): string {
	return scan(sql).firstWord;
}
