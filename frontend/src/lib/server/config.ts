/** The published surface's knobs, read from `config/idhazh.json` at build time.
 *
 * Nothing in a component is hardcoded that an operator might reasonably want
 * different (Holy Law #6).
 */

import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { REPO_ROOT } from './payload';

export interface UiConfig {
	sections: string[];
	theme_default: 'system' | 'light' | 'dark';
	visual_side: 'above' | 'leading' | 'trailing';
	source_mark: boolean;
	show_filter: boolean;
	repo_url: string;
	site_title: string;
	tagline: string;
}

const DEFAULTS: UiConfig = {
	sections: ['notice', 'topics', 'items'],
	theme_default: 'system',
	visual_side: 'above',
	source_mark: true,
	show_filter: true,
	repo_url: 'https://github.com/miztiik/yen-idhazh',
	site_title: 'yen-idhazh',
	tagline: 'A daily digest that checks its own work.'
};

export function uiConfig(): UiConfig {
	const path = join(REPO_ROOT, 'config', 'idhazh.json');
	if (!existsSync(path)) return DEFAULTS;
	const parsed = JSON.parse(readFileSync(path, 'utf8')) as { ui?: Partial<UiConfig> };
	return { ...DEFAULTS, ...(parsed.ui ?? {}) };
}
