/** How does a test build the real Judgement route on its own recorded data?
 *
 * Named route entries and their literal module imports form the private source
 * tree. No committed directory is walked. The production configuration builds
 * that tree, with private cache and output, before preview serves the browser.
 */
import { execFileSync, spawn } from 'node:child_process';
import {
	appendFileSync, copyFileSync, existsSync, mkdirSync, mkdtempSync,
	readFileSync, realpathSync, rmSync, symlinkSync, unlinkSync, writeFileSync
} from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, relative, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { compile } from 'svelte/compiler';
import ts from 'typescript';
import { publishedSite } from './published-site';
import { buildLedger } from './ledger-lifecycle';

const FRONTEND = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const ENTRIES = [
	'src/app.html', 'src/app.d.ts',
	'src/routes/+layout.ts', 'src/routes/+layout.svelte', 'src/routes/+error.svelte',
	'src/routes/console/+layout.ts', 'src/routes/console/+layout.svelte',
	'src/routes/console/judgement/+page.server.ts',
	'src/routes/console/judgement/+page.svelte',
	'src/routes/console/data-explorer/+page.ts',
	'src/routes/console/data-explorer/+page.svelte',
	'src/styles/app.css', 'src/styles/tokens.css', 'src/styles/frame.generated.css',
	'vite.config.ts', 'svelte.config.js', 'asset-base.js',
	'scripts/query-engine-assets.ts', 'scripts/raw-listed-through.mjs',
	'scripts/published-ledgers.mjs'
] as const;

function stageModules(frontend: string): string[] {
	const staged = new Set<string>();
	function stage(name: string): void {
		name = name.split(sep).join('/');
		if (staged.has(name)) return;
		const source = join(FRONTEND, name);
		const text = readFileSync(source, 'utf8');
		const target = join(frontend, name);
		mkdirSync(dirname(target), { recursive: true });
		copyFileSync(source, target);
		staged.add(name);
		if (!/\.(svelte|ts|js|mjs)$/.test(name)) return;
		const code = name.endsWith('.svelte')
			? compile(text, { filename: source, generate: 'server' }).js.code
			: text;
		for (const imported of ts.preProcessFile(code, true, true).importedFiles) {
			const specifier = imported.fileName;
			if (specifier.endsWith('/$types') || specifier === './$types') continue;
			const base = specifier.startsWith('$lib/')
				? join(FRONTEND, 'src', 'lib', specifier.slice(5))
				: specifier.startsWith('.') ? resolve(dirname(source), specifier) : null;
			if (base === null) continue;
			const file = [base, ...['.ts', '.js', '.svelte', '.json', '.mjs', '.css'].map((extension) => base + extension),
				join(base, 'index.ts')].find((candidate) => existsSync(candidate) && /\.[^\\/.]+$/.test(candidate));
			if (file === undefined) throw new Error(`The Judgement fixture cannot resolve ${specifier} from ${name}`);
			const next = relative(FRONTEND, file);
			if (next.startsWith('..')) throw new Error(`The Judgement fixture import leaves frontend: ${name} -> ${specifier}`);
			stage(next);
		}
	}
	for (const entry of ENTRIES) stage(entry);
	return [...staged].sort();
}

export async function judgementRoute(report: string): Promise<{
	origin: string;
	inputs: string[];
	buildMs: number;
	close: () => Promise<void>;
}> {
	mkdirSync(report, { recursive: true });
	const root = realpathSync.native(mkdtempSync(join(tmpdir(), 'idhazh-judgement-')));
	const links: string[] = [];
	let child: ReturnType<typeof spawn> | undefined;
	const close = async () => {
		if (child !== undefined && child.exitCode === null) {
			await new Promise<void>((done) => {
				const timer = setTimeout(() => { child?.kill(); }, 10_000);
				child?.once('exit', () => { clearTimeout(timer); done(); });
				child?.stdin?.end('close\n');
			});
		}
		for (const link of links) unlinkSync(link);
		rmSync(root, { recursive: true });
	};
	try {
		const site = publishedSite(join(root, 'public'), { published: ['2030-06-15'] });
		writeFileSync(join(site.digest, '2030', '06', '15', 'run.json'), JSON.stringify({
			date: '2030-06-15',
			runs: [
				{ run_id: '2030-06-15-2', completed_at: '2030-06-15T23:00:00Z', same_story_floor_applied: 0.937 },
				{ run_id: '2030-06-15-1', completed_at: '2030-06-15T12:00:00Z', same_story_floor_applied: 0.945 }
			]
		}));
		const state = join(root, 'state');
		await buildLedger(state, {
			ledger: 'fitted-thresholds', pinned: '2030-06-15',
			days: [{ ago: 1, rows: 1 }],
			columns: {
				run_id: '2030-06-14-1', previous: 0.95, proposed: 0.952,
				after_damping: 0.952, applied: 0.952, clamp_kind: 'none',
				clamp_movement: 0, held_reason: 'none', max_down_step: 0.01,
				max_up_step: 0.01, pairs_in_band: 10, pairs_judged: 10,
				pairs_usable: 10, disagreement_rate: 0, unclear_rate: 0,
				negatives_on_record: 5, above_line_on_record: 5,
				days_on_record: 1, cosine_weight: 1
			}
		});
		for (const ledger of ['holdout-pairs', 'merge-line-holdout-scores'] as const) {
			await buildLedger(state, {
				ledger, pinned: '2030-06-15', days: [{ ago: 0, state: 'empty' }]
			});
		}
		const frontend = join(root, 'frontend');
		const inputs = stageModules(frontend);
		copyFileSync(join(FRONTEND, 'package.json'), join(frontend, 'package.json'));
		copyFileSync(join(FRONTEND, 'tsconfig.json'), join(frontend, 'tsconfig.json'));
		mkdirSync(join(frontend, 'static'), { recursive: true });
		const band = join(frontend, 'static', 'console', 'band.json');
		execFileSync(process.env.IDHAZH_PYTHON ?? 'python', ['-c', `
from pathlib import Path
import sys
from idhazh import config
from idhazh.telemetry.publish.console_band import build
settings = config.load(Path(sys.argv[1]))
band = build(generated_at="2030-06-15T23:00:00Z", days=[], feeds=[],
    health_rows=[], record=None, machine_rows=[], months=[],
    run=settings.app.run, collect=settings.app.collect)
target = Path(sys.argv[2])
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(band.to_json(), encoding="utf-8", newline="\\n")
		`, join(FRONTEND, '..', 'config'), band], {
			env: { ...process.env, PYTHONPATH: join(FRONTEND, '..', 'backend') }
		});
		for (const [source, target] of [
			[join(FRONTEND, 'node_modules'), join(frontend, 'node_modules')],
			[join(FRONTEND, '..', 'config'), join(root, 'config')],
			[join(FRONTEND, 'static', 'fonts'), join(frontend, 'static', 'fonts')],
			[join(FRONTEND, 'static', 'icons'), join(frontend, 'static', 'icons')]
		]) {
			symlinkSync(source, target, 'junction');
			links.push(target);
		}
		for (const file of ['favicon.svg', 'manifest.webmanifest', 'service-worker-kill.json']) {
			copyFileSync(join(FRONTEND, 'static', file), join(frontend, 'static', file));
		}
		writeFileSync(join(report, 'inputs.json'), `${JSON.stringify(inputs, null, 2)}\n`);
		const runner = join(frontend, 'judgement-preview.mjs');
		writeFileSync(runner, `
			import { build, preview } from 'vite';
			const started = performance.now();
			await build({ cacheDir: ${JSON.stringify(join(root, 'vite-cache'))} });
			console.log('JUDGEMENT_BUILD_MS=' + Math.round(performance.now() - started));
			const server = await preview({ preview: { host: '127.0.0.1', port: 0 } });
			console.log('JUDGEMENT_ORIGIN=' + server.resolvedUrls.local[0]);
			process.stdin.resume();
			process.stdin.on('data', () => server.httpServer.close(() => process.exit(0)));
		`, 'utf8');
		child = spawn(process.execPath, [runner], {
			cwd: frontend,
			env: { ...process.env, DIGEST_ROOT: site.digest, STATE_ROOT: state,
				TELEMETRY_ROOT: site.telemetry, BASE_PATH: '' },
			stdio: ['pipe', 'pipe', 'pipe']
		});
		let output = '';
		const record = (bytes: Buffer) => {
			output += bytes.toString();
			appendFileSync(join(report, 'server.log'), bytes);
		};
		child.stdout?.on('data', record);
		child.stderr?.on('data', record);
		const running = child;
		const ready = await new Promise<{ origin: string; buildMs: number }>((done, fail) => {
			const timer = setTimeout(() => fail(new Error(`Private Judgement compilation did not finish:\n${output}`)), 150_000);
			const exited = (code: number | null) => {
				clearTimeout(timer);
				fail(new Error(`Private Judgement build exited ${code}:\n${output}`));
			};
			running.once('exit', exited);
			running.once('error', (error) => { clearTimeout(timer); fail(error); });
			running.stdout?.on('data', () => {
				const origin = output.match(/JUDGEMENT_ORIGIN=(http:\/\/[^\s]+)/)?.[1];
				const duration = output.match(/JUDGEMENT_BUILD_MS=(\d+)/)?.[1];
				if (origin === undefined || duration === undefined) return;
				clearTimeout(timer);
				running.off('exit', exited);
				done({ origin, buildMs: Number(duration) });
			});
		});
		writeFileSync(join(report, 'build.json'), `${JSON.stringify(ready)}\n`);
		return { ...ready, inputs, close };
	} catch (error) {
		await close();
		throw error;
	}
}
