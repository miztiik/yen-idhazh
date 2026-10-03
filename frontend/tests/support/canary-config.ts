import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

interface CanaryConfig {
	shell_seed_items: number;
}

export function canarySeedItems(): number {
	const root = resolve(process.cwd(), '..');
	const config = JSON.parse(
		readFileSync(resolve(root, 'config', 'canary.json'), 'utf8')
	) as Partial<CanaryConfig>;
	const seed = config.shell_seed_items;
	if (typeof seed !== 'number' || !Number.isInteger(seed) || seed < 1) {
		throw new Error('config/canary.json shell_seed_items must be a positive integer.');
	}
	return seed;
}
