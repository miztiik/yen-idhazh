/** Compile the actual private Summaries builder against owned native records. */
import { appendFileSync, cpSync, mkdirSync, readFileSync, realpathSync, rmSync, symlinkSync, unlinkSync, writeFileSync } from 'node:fs';
import { spawn } from 'node:child_process';
import { dirname, join } from 'node:path';
import { FRONTEND, sourceFiles } from './console-sources';
import { buildRows, siteCopy, type BuiltRowsDay } from './ledger-lifecycle';
import { publishedSite } from './published-site';
import { cachedParquetAddon, parquetAddon } from '../../scripts/duckdb-addon';
import { ITEM_HEALTH_COLUMNS, SCORE_COLUMNS } from '../../src/lib/server/ledger-rows';
import { assertBuild, REPO } from '../../scripts/build-state';
import { consoleConfig } from '../../src/lib/server/config';

export async function modelRoute(report: string, evidence: 'missing' | 'quiet' | 'populated' | 'sufficient') {
	const verified = assertBuild(REPO, 'canary');
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
		const sufficientCount = Math.max(8, consoleConfig().min_attempts_for_rate);
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
				const measuredScores = evidence === 'sufficient' ? Array.from({ length: sufficientCount }, (_, index) => ({
					...score, version: '2026-10-11', date, run_id: `${date}-one`, model_id: model,
					url_key: `${date}-${index}`, band: index < 2 ? 'low' : 'high', hhem: 0.5 + index / (sufficientCount * 2),
					hhem_delta: 0, unsupported_numbers: index === 0 ? 1 : 0, hedge_dropped: false,
					summary_words: 100 + index * 5, source_words: 500, source_words_before_cap: 500,
					compression: 0.2, extractiveness: 0.2, verbatim_run: 0.1, score_ms: 1000 + index * 200,
					determinism_violation: index === 0, self_repetition: 0, coherence: -0.25, semantic_coverage: 0.5,
					evidential_density: 0.004, speculative_density: 0.001
				})) : scores;
				const measuredItems = evidence === 'sufficient' ? Array.from({ length: sufficientCount }, (_, index) => ({
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
				writeFileSync(metrics, JSON.stringify({
					items_planned: evidence === 'sufficient' ? sufficientCount : 1,
					items_published: evidence === 'sufficient' ? sufficientCount : 1,
					items_failed: evidence === 'sufficient' ? 1 : 0,
					summaries_scored: evidence === 'sufficient' ? sufficientCount : 1,
					determinism_violations: 1, extraction_suspect: 0
				}));
			}
		}
		const frontend = join(root, 'frontend');
		mkdirSync(frontend, { recursive: true });
		// These are bounded output trees from the one verified compilation, not repository discovery.
		cpSync(join(FRONTEND, '.svelte-kit', 'output', 'server'), join(frontend, 'server'), { recursive: true });
		const staticRoot = join(frontend, 'build');
		cpSync(join(FRONTEND, 'build'), staticRoot, { recursive: true });
		writeFileSync(join(frontend, 'package.json'), '{"type":"module"}\n');
		for (const [source, target] of [
			[join(FRONTEND, 'node_modules'), join(frontend, 'node_modules')],
			[join(FRONTEND, '..', 'config'), join(root, 'config')]
		]) {
			symlinkSync(source, target, 'junction');
			links.push(target);
		}
		for (const ledger of ['item-health', 'summary-quality-evals']) rmSync(join(staticRoot, 'state', 'compact', ledger), { recursive: true, force: true });
		if (evidence !== 'missing') for (const ledger of ['item-health', 'summary-quality-evals'] as const) {
			siteCopy(state, join(staticRoot, 'state'), ledger, 365);
		}
		const addon = await parquetAddon();
		const home = join(root, 'node-home');
		const address = new URL(addon.url);
		const cached = join(home, '.duckdb', 'extensions', address.host, ...address.pathname.split('/').filter(Boolean));
		mkdirSync(dirname(cached), { recursive: true });
		writeFileSync(cached, cachedParquetAddon(addon));
		writeFileSync(join(report, 'inputs.json'), JSON.stringify({ verified, sources: sourceFiles() }));
		const runner = join(frontend, 'model-preview.mjs');
		writeFileSync(runner, `
			import { createServer } from 'node:http';
			import { createReadStream, existsSync, mkdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
			import { dirname, extname, join, resolve, sep } from 'node:path';
			import { Server } from './server/index.js';
			import { manifest } from './server/manifest-full.js';
			import { set_building, set_prerendering } from './server/internal.js';
			const output = ${JSON.stringify(staticRoot)};
			set_building(true);
			set_prerendering(true);
			const builder = new Server(manifest);
			await builder.init({ env: process.env, read: (file) => createReadStream(join('server', file)) });
			const dependencies = new Map();
			const response = await builder.respond(new Request('http://model.test/console/model/'), {
				getClientAddress: () => { throw new Error('The private builder has no client address.'); },
				prerendering: { dependencies, remote_responses: new Map() },
				read: (file) => readFileSync(join(output, file))
			});
			if (response.status !== 200) throw new Error('Private builder returned ' + response.status + ': ' + await response.text());
			const page = join(output, 'console', 'model', 'index.html');
			const html = await response.text();
			writeFileSync(page, html);
			writeFileSync(${JSON.stringify(join(report, 'model.html'))}, html);
			for (const [path, dependency] of dependencies) {
				if (!path.startsWith('/console/model/')) continue;
				const file = join(output, path.slice(1));
				mkdirSync(dirname(file), { recursive: true });
				writeFileSync(file, dependency.body);
			}
			const types = { '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript',
				'.json': 'application/json', '.css': 'text/css', '.svg': 'image/svg+xml', '.wasm': 'application/wasm',
				'.woff2': 'font/woff2', '.png': 'image/png', '.webmanifest': 'application/manifest+json' };
			const server = createServer((request, reply) => {
				let file = resolve(output, '.' + decodeURIComponent(new URL(request.url, 'http://model.test').pathname));
				if (!file.startsWith(output + sep)) { reply.writeHead(403).end(); return; }
				if (existsSync(file) && statSync(file).isDirectory()) file = join(file, 'index.html');
				if (!existsSync(file)) { reply.writeHead(404).end(); return; }
				reply.writeHead(200, { 'Content-Type': types[extname(file)] ?? 'application/octet-stream' });
				createReadStream(file).pipe(reply);
			});
			await new Promise((done) => server.listen(0, '127.0.0.1', done));
			console.log('MODEL_ORIGIN=http://127.0.0.1:' + server.address().port + '/');
			process.stdin.resume();
			process.stdin.on('data', () => server.close(() => process.exit(0)));
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
			const timer = setTimeout(() => fail(new Error(`Private Summaries builder did not finish:\n${output}`)), 150_000);
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
