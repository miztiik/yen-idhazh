/** How does a test build the real Judgement route on its own recorded data?
 *
 * A fixed named inventory forms the private source tree. A new module must be
 * named here before compilation can use it. No import discovery or directory
 * walk expands the inputs. Cache, output and preview remain private.
 */
import { execFileSync, spawn } from 'node:child_process';
import {
	appendFileSync, copyFileSync, mkdirSync, readFileSync,
	realpathSync, rmSync, symlinkSync, unlinkSync, writeFileSync
} from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { publishedSite } from './published-site';
import { buildLedger } from './ledger-lifecycle';
import { cachedParquetAddon, parquetAddon } from '../../scripts/duckdb-addon';

const FRONTEND = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const INPUTS = [
	'asset-base.js',
	'scripts/published-ledgers.mjs',
	'scripts/query-engine-assets.ts',
	'scripts/raw-listed-through.mjs',
	'src/app.d.ts',
	'src/app.html',
	'src/lib/assist/day.ts',
	'src/lib/assist/encoder.ts',
	'src/lib/assist/loader.ts',
	'src/lib/assist/month.ts',
	'src/lib/assist/search.ts',
	'src/lib/assist/session.ts',
	'src/lib/assist/weights.ts',
	'src/lib/bands.ts',
	'src/lib/charts/d3/DateSeries.svelte',
	'src/lib/charts/d3/Distribution.svelte',
	'src/lib/charts/d3/EmptyState.svelte',
	'src/lib/charts/d3/Flow.svelte',
	'src/lib/charts/d3/PairedScatter.svelte',
	'src/lib/charts/d3/PartsOfOne.svelte',
	'src/lib/charts/d3/TileStrip.svelte',
	'src/lib/charts/d3/axis.ts',
	'src/lib/charts/d3/dateSeries.ts',
	'src/lib/charts/d3/distribution.ts',
	'src/lib/charts/d3/empty.ts',
	'src/lib/charts/d3/flow.ts',
	'src/lib/charts/d3/ordered-colour.ts',
	'src/lib/charts/d3/pairedScatter.ts',
	'src/lib/charts/d3/partsOfOne.ts',
	'src/lib/charts/d3/scale.ts',
	'src/lib/charts/d3/tileStrip.ts',
	'src/lib/charts/frame.ts',
	'src/lib/charts/glance.ts',
	'src/lib/charts/indexed-runs.ts',
	'src/lib/charts/machine-colour.ts',
	'src/lib/charts/machine-name.ts',
	'src/lib/charts/rank.ts',
	'src/lib/charts/readout.ts',
	'src/lib/charts/series.ts',
	'src/lib/charts/skeleton.ts',
	'src/lib/charts/sparkline.ts',
	'src/lib/charts/stacked.ts',
	'src/lib/charts/targetbar.ts',
	'src/lib/charts/theme.ts',
	'src/lib/charts/viewport.ts',
	'src/lib/components/ChartReadout.svelte',
	'src/lib/components/ChoiceTiles.svelte',
	'src/lib/components/ConsoleBand.svelte',
	'src/lib/components/ConsoleNav.svelte',
	'src/lib/components/NotHere.svelte',
	'src/lib/components/Notice.svelte',
	'src/lib/components/Panel.svelte',
	'src/lib/components/RankedList.svelte',
	'src/lib/components/Reserved.svelte',
	'src/lib/components/SiteFooter.svelte',
	'src/lib/components/SiteHeader.svelte',
	'src/lib/components/TargetBar.svelte',
	'src/lib/components/ThemeToggle.svelte',
	'src/lib/components/WindowControl.svelte',
	'src/lib/components/WindowControlSource.svelte',
	'src/lib/components/WindowStatus.svelte',
	'src/lib/console/applied-line.ts',
	'src/lib/console/band.ts',
	'src/lib/console/chrome.ts',
	'src/lib/console/completeness.ts',
	'src/lib/console/eval-instruments.ts',
	'src/lib/console/explorer/AnswerTable.svelte',
	'src/lib/console/explorer/ColumnList.svelte',
	'src/lib/console/explorer/ColumnPicker.svelte',
	'src/lib/console/explorer/ColumnType.svelte',
	'src/lib/console/explorer/CopyAnswer.svelte',
	'src/lib/console/explorer/HistoryList.svelte',
	'src/lib/console/explorer/LedgerList.svelte',
	'src/lib/console/explorer/QueryEditor.svelte',
	'src/lib/console/explorer/QuestionStrip.svelte',
	'src/lib/console/explorer/RunStatus.svelte',
	'src/lib/console/explorer/ShapePanel.svelte',
	'src/lib/console/explorer/address.ts',
	'src/lib/console/explorer/answer.ts',
	'src/lib/console/explorer/chart-roles.ts',
	'src/lib/console/explorer/column-groups.ts',
	'src/lib/console/explorer/days-read.ts',
	'src/lib/console/explorer/floating-list.ts',
	'src/lib/console/explorer/gaps.ts',
	'src/lib/console/explorer/keep.ts',
	'src/lib/console/explorer/preset-span.ts',
	'src/lib/console/explorer/registry.ts',
	'src/lib/console/explorer/role-row.ts',
	'src/lib/console/explorer/shape.ts',
	'src/lib/console/explorer/status.ts',
	'src/lib/console/explorer/strip-fit.ts',
	'src/lib/console/explorer/type-colour.ts',
	'src/lib/console/explorer/type-family.ts',
	'src/lib/console/explorer/utc-instant.ts',
	'src/lib/console/holdout.ts',
	'src/lib/console/judgement-evidence.ts',
	'src/lib/console/merge-line.ts',
	'src/lib/console/recording.ts',
	'src/lib/console/route-console.ts',
	'src/lib/console/span-words.ts',
	'src/lib/console/strip.ts',
	'src/lib/console/verdict-split.ts',
	'src/lib/console/waiting.ts',
	'src/lib/console/window-slot.ts',
	'src/lib/data/ask-reader.ts',
	'src/lib/data/compact-index.ts',
	'src/lib/data/engine.ts',
	'src/lib/data/fetched-bytes.ts',
	'src/lib/data/ledger-columns.ts',
	'src/lib/data/ledger-reach.ts',
	'src/lib/data/ledger.ts',
	'src/lib/data/page-keeper.ts',
	'src/lib/data/raw-day-index.ts',
	'src/lib/data/site-window.ts',
	'src/lib/data/slice-query.ts',
	'src/lib/data/slice-reader.ts',
	'src/lib/data/slice-shapes.ts',
	'src/lib/data/slice.ts',
	'src/lib/data/statement.ts',
	'src/lib/day-shape.ts',
	'src/lib/feed-health.ts',
	'src/lib/format.ts',
	'src/lib/icons/Icon.svelte',
	'src/lib/icons/generated.ts',
	'src/lib/offline.generated.ts',
	'src/lib/offline.ts',
	'src/lib/payload/desks.ts',
	'src/lib/payload/drawing.ts',
	'src/lib/payload/project.ts',
	'src/lib/payload/types.ts',
	'src/lib/server/config.ts',
	'src/lib/server/ledger-disk.ts',
	'src/lib/server/ledger-rows.ts',
	'src/lib/server/payload.ts',
	'src/lib/server/publication.ts',
	'src/lib/server/recorded-line.ts',
	'src/lib/server/content-similarity-holdout.ts',
	'src/lib/server/content-similarity-judge.ts',
	'src/lib/server/window-day.ts',
	'src/lib/theme.ts',
	'src/routes/+error.svelte',
	'src/routes/+layout.svelte',
	'src/routes/+layout.ts',
	'src/routes/console/+layout.svelte',
	'src/routes/console/+layout.ts',
	'src/routes/console/data-explorer/+page.svelte',
	'src/routes/console/data-explorer/+page.ts',
	'src/routes/console/judgement/+page.server.ts',
	'src/routes/console/judgement/+page.svelte',
	'src/routes/console/judgement/HoldoutMargin.svelte',
	'src/routes/console/judgement/JudgeAgreement.svelte',
	'src/routes/console/judgement/MergeLinePlot.svelte',
	'src/routes/console/judgement/MergedStoriesPanel.svelte',
	'src/routes/console/judgement/RecordGates.svelte',
	'src/routes/console/judgement/VerdictSplit.svelte',
	'src/styles/app.css',
	'src/styles/frame.generated.css',
	'src/styles/tokens.css',
	'svelte.config.js',
	'vite.config.ts'
] as const;

function stageModules(frontend: string): void {
	for (const name of INPUTS) {
		const source = join(FRONTEND, name);
		const target = join(frontend, name);
		mkdirSync(dirname(target), { recursive: true });
		copyFileSync(source, target);
	}
}

export async function judgementRoute(
	report: string,
	options: { scoreRecord?: 'populated'; evidence?: 'absent' | 'empty' | 'unknown-denominators' | 'missing-gate' } = {}
): Promise<{
	origin: string;
	inputs: string[];
	staticRoot: string;
	close: () => Promise<void>;
}> {
	mkdirSync(report, { recursive: true });
	const root = join(realpathSync.native(report), 'isolated-route');
	mkdirSync(root, { recursive: true });
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
		const absent = options.evidence === 'absent';
		const site = publishedSite(join(root, 'public'), { published: absent ? [] : ['2030-06-15'] });
		const state = join(root, 'state');
		mkdirSync(state, { recursive: true });
		if (!absent) {
		writeFileSync(join(site.digest, '2030', '06', '15', 'run.json'), JSON.stringify({
			date: '2030-06-15',
			runs: [
				{ run_id: '2030-06-15-2', completed_at: '2030-06-15T23:00:00Z', same_story_floor_applied: 0.937 },
				{ run_id: '2030-06-15-1', completed_at: '2030-06-15T12:00:00Z', same_story_floor_applied: 0.945 }
			]
		}));
		await buildLedger(state, {
			ledger: 'fitted-thresholds', pinned: '2030-06-15',
			days: options.evidence === 'empty' ? [{ ago: 0, state: 'empty' }] : [{ ago: 1, rows: 1 }],
			columns: {
				run_id: '2030-06-14-1', previous: 0.95, proposed: 0.952,
				after_damping: 0.952, applied: 0.952, clamp_kind: 'none',
				clamp_movement: 0, held_reason: 'none', max_down_step: 0.01,
				max_up_step: 0.01, pairs_in_band: 10, pairs_judged: 10,
				pairs_usable: 10, disagreement_rate: 0, unclear_rate: 0,
				negatives_on_record: 5, above_line_on_record: 5,
				days_on_record: 1,
				cosine_weight: options.evidence === 'unknown-denominators' ? null : 1,
				...(options.evidence === 'unknown-denominators' ? { pairs_judged: null } : {}),
				...(options.evidence === 'missing-gate' ? {
					negatives_on_record: null, disagreement_rate: 0.5, held_reason: 'judge_unstable'
				} : {})
			}
		});
		for (const ledger of ['holdout-pairs', 'merge-line-holdout-scores'] as const) {
			await buildLedger(state, {
				ledger, pinned: '2030-06-15', days: [{ ago: 0, state: 'empty' }]
			});
		}
		if (options.scoreRecord === 'populated') {
			const tuning = JSON.parse(readFileSync(join(FRONTEND, '..', 'config', 'idhazh.json'), 'utf8'))
				.assemble.same_story.adaptive_dedup_threshold;
			const judge = join(state, 'content-similarity-judge');
			mkdirSync(judge, { recursive: true });
			writeFileSync(join(judge, 'score-distribution.json'), JSON.stringify({
				band_low: tuning.band_low, band_high: tuning.band_high,
				bin_width: tuning.bin_width, counted_dates: ['2030-06-14'],
				slots: [
					{ bin_low: 0.91, same_count: 1, different_count: 2, unclear_count: 0 },
					{ bin_low: 0.95, same_count: 3, different_count: 4, unclear_count: 0 }
				]
			}));
		}
		}
		writeFileSync(join(report, 'evidence.json'), JSON.stringify({
			digestDays: absent ? [] : ['2030-06-15'],
			fittedDays: absent || options.evidence === 'empty' ? [] : ['2030-06-14'],
			scoreRecord: absent ? null : options.scoreRecord ?? null,
			holdoutPairs: [], holdoutScores: []
		}));
		const frontend = join(root, 'frontend');
		stageModules(frontend);
		const inputs = [...INPUTS];
		const addon = await parquetAddon();
		const home = join(root, 'node-home');
		const address = new URL(addon.url);
		const cached = join(home, '.duckdb', 'extensions', address.host, ...address.pathname.split('/').filter(Boolean));
		mkdirSync(dirname(cached), { recursive: true });
		writeFileSync(cached, cachedParquetAddon(addon));
		writeFileSync(join(report, 'addon.json'), JSON.stringify({ source: addon.file, requested: address.pathname }));
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
			await build({ cacheDir: ${JSON.stringify(join(root, 'vite-cache'))},
				logLevel: 'warn', build: { reportCompressedSize: false } });
			const server = await preview({ preview: { host: '127.0.0.1', port: 0 } });
			console.log('JUDGEMENT_ORIGIN=' + server.resolvedUrls.local[0]);
			process.stdin.resume();
			process.stdin.on('data', () => server.httpServer.close(() => process.exit(0)));
		`, 'utf8');
		child = spawn(process.execPath, [runner], {
			cwd: frontend,
			env: { ...process.env, HOME: home, USERPROFILE: home, DIGEST_ROOT: site.digest, STATE_ROOT: state,
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
		const ready = await new Promise<{ origin: string }>((done, fail) => {
			const timer = setTimeout(() => fail(new Error(`Private Judgement compilation did not finish:\n${output}`)), 150_000);
			const exited = (code: number | null) => {
				clearTimeout(timer);
				fail(new Error(`Private Judgement build exited ${code}:\n${output}`));
			};
			running.once('exit', exited);
			running.once('error', (error) => { clearTimeout(timer); fail(error); });
			running.stdout?.on('data', () => {
				const origin = output.match(/JUDGEMENT_ORIGIN=(http:\/\/[^\s]+)/)?.[1];
				if (origin === undefined) return;
				clearTimeout(timer);
				running.off('exit', exited);
				done({ origin });
			});
		});
		writeFileSync(join(report, 'build.json'), `${JSON.stringify(ready)}\n`);
		return { ...ready, inputs, staticRoot: join(frontend, 'build'), close };
	} catch (error) {
		await close();
		throw error;
	}
}
