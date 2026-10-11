/** Compile the actual private Summaries builder against owned native records. */
import { appendFileSync, copyFileSync, mkdirSync, readFileSync, realpathSync, rmSync, symlinkSync, unlinkSync, writeFileSync } from 'node:fs';
import { spawn } from 'node:child_process';
import { dirname, join } from 'node:path';
import { FRONTEND, sourceFiles } from './console-sources';
import { buildRows, siteCopy, type BuiltRowsDay } from './ledger-lifecycle';
import { publishedSite } from './published-site';
import { cachedParquetAddon, parquetAddon } from '../../scripts/duckdb-addon';
import { ITEM_HEALTH_COLUMNS, SCORE_COLUMNS } from '../../src/lib/server/ledger-rows';

export async function modelRoute(report: string, evidence: 'missing' | 'quiet' | 'populated' | 'sufficient') {
	mkdirSync(report, { recursive: true });
	const root = join(realpathSync.native(report), 'isolated-model');
	mkdirSync(root, { recursive: true });
	const links: string[] = [];
	let child: ReturnType<typeof spawn> | undefined;
	const close = async () => {
		if (child !== undefined && child.exitCode === null) await new Promise<void>((done) => {
			const timer = setTimeout(() => child?.kill(), 10_000);
			child?.once('exit', () => { clearTimeout(timer); done(); });
			child?.stdin?.end('close\n');
		});
		for (const link of links) unlinkSync(link);
		rmSync(root, { recursive: true });
	};
	try {
		const site = publishedSite(join(root, 'public'), { published: evidence === 'missing' ? [] : ['2030-06-15'] });
		if (evidence === 'sufficient') {
			const payload = join(site.digest, '2030', '06', '15', 'digest.json');
			const items = [{ band: 'low', band_reason: 'faithfulness' }, { band: 'medium', band_reason: 'unsupported_number' }];
			const body = JSON.stringify({ date: '2030-06-15', items });
			writeFileSync(payload, body);
			const publication = JSON.parse(readFileSync(join(site.site, 'publication.json'), 'utf8'));
			publication.entries[0].bytes = Buffer.byteLength(body);
			publication.entries[0].items = items.length;
			publication.total_bytes = Buffer.byteLength(body);
			publication.total_items = items.length;
			writeFileSync(join(site.site, 'publication.json'), JSON.stringify(publication));
		}
		const state = join(root, 'state');
		mkdirSync(state, { recursive: true });
		if (evidence !== 'missing') {
			const score = Object.fromEntries(SCORE_COLUMNS.map((column) => [column, null]));
			const article = Object.fromEntries(ITEM_HEALTH_COLUMNS.map((column) => [column, null]));
			const scores = evidence === 'quiet' ? [] : [1, 2].map((index) => ({
				...score, version: '2026-10-11', date: '2030-06-14', run_id: `2030-06-14-${index}`,
				model_id: 'recorded-model', band: 'low', hhem: 0.4, unsupported_numbers: 0,
				hedge_dropped: false, truncation_flagged: false, extractiveness: 0.2, verbatim_run: 0.1,
				determinism_violation: true, summary_words: 100, source_words: 500,
				source_words_before_cap: 500, self_repetition: 0, coherence: -0.25, semantic_coverage: 0.5
			}));
			const articles = evidence === 'quiet' ? [] : [{
				...article, version: '2026-10-11', date: '2030-06-14', run_id: '2030-06-14-1',
				stage: 'summarize', outcome: 'ok', summarize_ms: 1000
			}];
			const dates = evidence === 'sufficient' ? ['2030-06-10', '2030-06-11', '2030-06-12', '2030-06-13', '2030-06-14'] : ['2030-06-14'];
			const scoreDays: BuiltRowsDay[] = [];
			const itemDays: BuiltRowsDay[] = [];
			for (const date of dates) {
				const model = date === '2030-06-10' ? 'before-model' : 'after-model';
				const measuredScores = evidence === 'sufficient' ? Array.from({ length: 8 }, (_, index) => ({
					...score, version: '2026-10-11', date, run_id: `${date}-one`, model_id: model,
					url_key: `${date}-${index}`, band: index < 2 ? 'low' : 'high', hhem: 0.5 + index / 20,
					hhem_delta: 0, unsupported_numbers: index === 0 ? 1 : 0, hedge_dropped: false,
					summary_words: 100 + index * 5, source_words: 500, source_words_before_cap: 500,
					compression: 0.2, extractiveness: 0.2, verbatim_run: 0.1, score_ms: 1000 + index * 200,
					determinism_violation: index === 0, self_repetition: 0, coherence: -0.25, semantic_coverage: 0.5,
					evidential_density: 0.004, speculative_density: 0.001
				})) : scores;
				const measuredItems = evidence === 'sufficient' ? Array.from({ length: 8 }, (_, index) => ({
					...article, version: '2026-10-11', date, run_id: `${date}-one`, model_id: model,
					url_key: `${date}-${index}`, source_id: 'recorded-source', stage: 'summarize',
					outcome: index === 0 ? 'failed' : 'ok', code: index === 0 ? 'context_exceeded' : null,
					failed_rule: index === 0 ? 'Recorded context limit' : null,
					summary_finish_reason: index === 0 ? 'length' : 'stop', label_finish_reason: 'stop',
					summarize_ms: date === '2030-06-10' ? 2000 : 3000, prefill_ms: 1000, decode_ms: 2000,
					input_tokens: 100, cached_tokens: 0, output_tokens: 100 + index * 10
				})) : articles;
				const empty = evidence === 'sufficient' && date !== '2030-06-10' && date !== '2030-06-14';
				scoreDays.push({ covers: date, rows: empty ? [] : measuredScores });
				itemDays.push({ covers: date, rows: empty ? [] : measuredItems });
			}
			await buildRows(state, 'summary-quality-evals', scoreDays);
			await buildRows(state, 'item-health', itemDays);
			if (evidence === 'populated' || evidence === 'sufficient') for (const date of dates) {
				const metrics = join(state, 'day-metrics', '2030', '06', `${date.slice(-2)}.json`);
				mkdirSync(dirname(metrics), { recursive: true });
				writeFileSync(metrics, JSON.stringify({ summaries_scored: evidence === 'sufficient' ? 8 : 1, determinism_violations: 1, extraction_suspect: 0 }));
			}
		}
		const frontend = join(root, 'frontend');
		const inputs = sourceFiles().filter((file) =>
			file.startsWith('src/lib/') || (file.startsWith('src/routes/') &&
				(file.startsWith('src/routes/console/model/') || ['src/routes/+layout.ts', 'src/routes/+layout.svelte',
					'src/routes/+error.svelte', 'src/routes/console/+layout.ts', 'src/routes/console/+layout.svelte'].includes(file))) ||
			['vite.config.ts', 'svelte.config.js', 'asset-base.js', 'src/app.d.ts', 'src/query-engine-assets.d.ts',
				'src/service-worker.ts'].includes(file) || (file.startsWith('scripts/') && !file.startsWith('scripts/tests/')));
		inputs.push('src/app.html', 'src/styles/app.css', 'src/styles/frame.generated.css', 'src/styles/tokens.css',
			'package.json', 'tsconfig.json');
		for (const file of inputs) {
			const target = join(frontend, file);
			mkdirSync(dirname(target), { recursive: true });
			copyFileSync(join(FRONTEND, file), target);
		}
		const staticRoot = join(frontend, 'static');
		mkdirSync(staticRoot, { recursive: true });
		for (const [source, target] of [
			[join(FRONTEND, 'node_modules'), join(frontend, 'node_modules')],
			[join(FRONTEND, '..', 'config'), join(root, 'config')],
			[join(FRONTEND, 'static', 'fonts'), join(staticRoot, 'fonts')],
			[join(FRONTEND, 'static', 'icons'), join(staticRoot, 'icons')]
		]) {
			symlinkSync(source, target, 'junction');
			links.push(target);
		}
		for (const file of ['favicon.svg', 'manifest.webmanifest', 'service-worker-kill.json']) {
			copyFileSync(join(FRONTEND, 'static', file), join(staticRoot, file));
		}
		if (evidence !== 'missing') for (const ledger of ['item-health', 'summary-quality-evals'] as const) {
			siteCopy(state, join(staticRoot, 'state'), ledger, 365);
		}
		const addon = await parquetAddon();
		const home = join(root, 'node-home');
		const address = new URL(addon.url);
		const cached = join(home, '.duckdb', 'extensions', address.host, ...address.pathname.split('/').filter(Boolean));
		mkdirSync(dirname(cached), { recursive: true });
		writeFileSync(cached, cachedParquetAddon(addon));
		writeFileSync(join(report, 'inputs.json'), JSON.stringify(inputs));
		const runner = join(frontend, 'model-preview.mjs');
		writeFileSync(runner, `
			import { build, preview } from 'vite';
			await build({ cacheDir: ${JSON.stringify(join(root, 'vite-cache'))}, logLevel: 'warn',
				build: { reportCompressedSize: false } });
			const server = await preview({ preview: { host: '127.0.0.1', port: 0 } });
			console.log('MODEL_ORIGIN=' + server.resolvedUrls.local[0]);
			process.stdin.resume();
			process.stdin.on('data', () => server.httpServer.close(() => process.exit(0)));
		`);
		child = spawn(process.execPath, [runner], { cwd: frontend,
			env: { ...process.env, HOME: home, USERPROFILE: home, BASE_PATH: '', DIGEST_ROOT: site.digest,
				STATE_ROOT: state, TELEMETRY_ROOT: site.telemetry }, stdio: ['pipe', 'pipe', 'pipe'] });
		let output = '';
		const record = (bytes: Buffer) => { output += bytes.toString(); appendFileSync(join(report, 'server.log'), bytes); };
		child.stdout?.on('data', record);
		child.stderr?.on('data', record);
		const running = child;
		const origin = await new Promise<string>((done, fail) => {
			const timer = setTimeout(() => fail(new Error(`Private Summaries compilation did not finish:\n${output}`)), 150_000);
			const exited = (code: number | null) => { clearTimeout(timer); fail(new Error(`Private Summaries exited ${code}:\n${output}`)); };
			running.once('exit', exited);
			running.once('error', (error) => { clearTimeout(timer); fail(error); });
			running.stdout?.on('data', () => {
				const found = output.match(/MODEL_ORIGIN=(http:\/\/[^\s]+)/)?.[1];
				if (found === undefined) return;
				clearTimeout(timer);
				running.off('exit', exited);
				done(found);
			});
		});
		return { origin, staticRoot: join(frontend, 'build'), close };
	} catch (error) { await close(); throw error; }
}
