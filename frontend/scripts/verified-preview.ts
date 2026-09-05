import { spawn } from 'node:child_process';
import { join } from 'node:path';
import { assertBuild, REPO } from './build-state.ts';

const mode = process.env.IDHAZH_TEST_BUILD ?? 'canary';
if (mode !== 'canary' && mode !== 'real') throw new Error('IDHAZH_TEST_BUILD must be canary or real.');
assertBuild(REPO, mode);
const child = spawn(process.execPath, [join(REPO, 'frontend/node_modules/vite/bin/vite.js'),
	'preview', ...process.argv.slice(2)], { cwd: join(REPO, 'frontend'), stdio: 'inherit' });
child.once('error', (error) => { console.error(error.message); process.exitCode = 1; });
child.once('close', (code) => { process.exitCode = code ?? 1; });
process.once('SIGTERM', () => { child.kill('SIGTERM'); });
process.once('SIGINT', () => { child.kill('SIGINT'); });
