/** Generate the four current planner ledgers and stage their actual bytes for delivery tests. */
import { execFileSync } from 'node:child_process';
import { copyFileSync, mkdirSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { ledgerCopy } from '../../scripts/published-ledgers.mjs';
import { buildLedger } from './ledger-lifecycle';

export const FEED_LEDGERS = [
	'discovered-articles', 'selected-articles', 'feed-health-state', 'plan-runs'
] as const;

export interface FeedFixture {
	columns: Record<string, string[]>;
	rawFile: string;
}

export async function buildFeedLedgers(state: string): Promise<FeedFixture> {
	const repo = resolve('..');
	const fixture: FeedFixture = JSON.parse(execFileSync('bun', [
		join(repo, 'packages', 'ledger-file-writer', 'test', 'feed-ledger-delivery-recording.ts'), state
	], {
		cwd: repo, env: process.env, encoding: 'utf8'
	}));
	await buildLedger(state, {
		ledger: 'host-fingerprint', pinned: '2026-10-20', days: [{ ago: 0, rows: 1 }],
		columns: { cores: 4 }
	});
	return fixture;
}

export function stageFeedLedgers(source: string, target: string) {
	const copy = ledgerCopy(source, [...FEED_LEDGERS, 'host-fingerprint']);
	if (copy.refused.length || copy.missing.length) {
		throw new Error(`Fixture publication refused: ${[...copy.refused, ...copy.missing].join('\n')}`);
	}
	const build = join(target, '..', 'publication-build', 'frontend');
	mkdirSync(build, { recursive: true });
	mkdirSync(join(build, '..', 'config'), { recursive: true });
	copyFileSync(resolve('..', 'config', 'ledgers.json'), join(build, '..', 'config', 'ledgers.json'));
	execFileSync(process.execPath, [resolve('scripts', 'stage-publication.mjs')], {
		cwd: build, encoding: 'utf8',
		env: { ...process.env, STATE_ROOT: source, DIGEST_ROOT: join(build, 'public', 'digest') }
	});
	for (const file of copy.files) {
		const destination = join(target, ...file.split('/'));
		mkdirSync(dirname(destination), { recursive: true });
		copyFileSync(join(build, 'static', 'state', ...file.split('/')), destination);
	}
	return copy;
}
