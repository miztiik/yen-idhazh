import { defineConfig } from '@playwright/test';
import { fileURLToPath } from 'node:url';
import config from './playwright.config';
import { groupedSpecs } from './scripts/test-groups';

export default defineConfig({
	...config,
	outputDir: 'test-results/logic',
	webServer: undefined,
	globalSetup: undefined,
	projects: [{
		name: 'logic',
		testMatch: groupedSpecs(fileURLToPath(new URL('./tests/', import.meta.url))).logic
			.map((filename) => `**/${filename}`)
	}]
});
