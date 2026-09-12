#!/usr/bin/env node
/**
 * Can a reader's browser fetch the encoder weights from somewhere that is not us?
 *
 * Run by hand, against the deployed site, when the answer might have changed.
 * It is NOT a test and it joins no suite: Guardrail #7 forbids a test that touches
 * the network, and every request below leaves the machine. pytest does not
 * collect a `.mjs`, the frontend selector globs `frontend/tests/`, and
 * `test-scope.ts` widens only for `gate_lock.py`, so nothing here runs on a push.
 *
 * Two gates decide whether a cross-origin fetch works, and only one of them is
 * ours. Our Content-Security-Policy `connect-src` is a build-time list we
 * control. CORS is the other origin's answer and no config of ours can change
 * it. curl checks neither, which is why this drives a real browser from the
 * real page origin.
 *
 * Usage:
 *
 *   node backend/utilities/encoder_origin_probe.mjs
 *   node backend/utilities/encoder_origin_probe.mjs --csp widened
 *   node backend/utilities/encoder_origin_probe.mjs --page https://miztiik.github.io/yen-idhazh/ \
 *       --only raw,huggingface --json out.json
 *
 * `--csp as-deployed` (the default) loads the page exactly as published, so a
 * refusal is our own policy talking. `--csp widened` rewrites the `connect-src`
 * directive in the served document to allow every host the targets use - the
 * change a later row would ship - so a refusal is then the other origin talking.
 * Run both. One arm alone cannot tell the two gates apart.
 *
 * Every response is data (Guardrail #11). Nothing read from a response becomes a
 * shell argument, a file path or a fetched URL: the one value taken from a
 * response and put back into a URL is a release asset id, and it is refused
 * unless it is digits.
 */

import { createHash } from 'node:crypto';
import { createRequire } from 'node:module';
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = join(HERE, '..', '..');

/** Playwright lives in the frontend's dependency tree; this tool adds none of its own. */
const require = createRequire(join(ROOT, 'frontend', 'package.json'));
const { chromium } = require('playwright');

/** The five files, flat asset name against the path they take under the model directory. */
const FILES = [
	{ asset: 'config.json', path: 'config.json' },
	{ asset: 'special_tokens_map.json', path: 'special_tokens_map.json' },
	{ asset: 'tokenizer_config.json', path: 'tokenizer_config.json' },
	{ asset: 'tokenizer.json', path: 'tokenizer.json' },
	{ asset: 'model_quantized.onnx', path: 'onnx/model_quantized.onnx' }
];

const DEFAULTS = {
	page: 'https://miztiik.github.io/yen-idhazh/',
	repo: 'miztiik/yen-idhazh',
	ref: 'main',
	hub: 'Xenova/all-MiniLM-L6-v2',
	revision: '751bff37182d3f1213fa05d7196b954e230abad9',
	weights: 'frontend/static/assist/models/all-minilm-l6-v2-quantized/2026-08-22',
	csp: 'as-deployed',
	only: 'raw,huggingface'
};

function parseArgs(argv) {
	const opts = { ...DEFAULTS, json: '' };
	for (let i = 0; i < argv.length; i += 1) {
		const key = argv[i].replace(/^--/, '');
		if (!(key in opts)) throw new Error(`unknown option: ${argv[i]}`);
		opts[key] = argv[i + 1];
		i += 1;
	}
	if (!/^[0-9a-f]{40}$/.test(opts.revision)) throw new Error('--revision must be a 40-hex commit SHA');
	return opts;
}

/** What we hold on disk, so the browser's bytes are checked against ours and not against a literal. */
function localDigests(opts) {
	const out = new Map();
	for (const f of FILES) {
		try {
			const bytes = readFileSync(join(ROOT, opts.weights, f.path));
			out.set(f.asset, { bytes: bytes.length, sha256: createHash('sha256').update(bytes).digest('hex') });
		} catch {
			out.set(f.asset, null);
		}
	}
	return out;
}

function targetsFor(name, opts) {
	const [owner, repo] = opts.repo.split('/');
	if (name === 'raw') {
		return FILES.map((f) => ({
			asset: f.asset,
			url: `https://raw.githubusercontent.com/${owner}/${repo}/${opts.ref}/${opts.weights}/${f.path}`
		}));
	}
	if (name === 'huggingface') {
		return FILES.map((f) => ({
			asset: f.asset,
			url: `https://huggingface.co/${opts.hub}/resolve/${opts.revision}/${f.path}`
		}));
	}
	throw new Error(`unknown target family: ${name}`);
}

/** Every origin the probe will ask for, so the widened arm allows exactly those and nothing else. */
function originsOf(families, opts) {
	const set = new Set();
	for (const family of families) {
		for (const t of targetsFor(family, opts)) set.add(new URL(t.url).origin);
	}
	// The host a redirect lands on. A CSP source list is matched against every
	// hop, so the first hop's origin alone is not enough.
	set.add('https://us.aws.cdn.hf.co');
	return [...set].sort();
}

/** The one in-page routine. It returns what arrived, or why nothing did. */
const IN_PAGE_FETCH = async ({ url, headers }) => {
	const started = performance.now();
	try {
		const res = await fetch(url, { headers: headers ?? {}, mode: 'cors', cache: 'no-store' });
		const buf = await res.arrayBuffer();
		const digest = await crypto.subtle.digest('SHA-256', buf);
		return {
			ok: res.ok,
			status: res.status,
			type: res.type,
			finalUrl: res.url,
			bytes: buf.byteLength,
			sha256: [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, '0')).join(''),
			ms: Math.round(performance.now() - started)
		};
	} catch (err) {
		return { ok: false, error: String(err && err.message ? err.message : err), ms: Math.round(performance.now() - started) };
	}
};

async function main() {
	const opts = parseArgs(process.argv.slice(2));
	const families = opts.only.split(',').map((s) => s.trim()).filter(Boolean);
	const local = localDigests(opts);
	const browser = await chromium.launch();
	const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
	const page = await context.newPage();


	const allowed = originsOf(families, opts, assetIds);
	const cspList = ["'self'", ...allowed].join(' ');
	if (opts.csp === 'widened') {
		await page.route(opts.page, async (route) => {
			const res = await route.fetch();
			const body = (await res.text()).replace(/connect-src [^;"]*/g, `connect-src ${cspList}`);
			await route.fulfill({ response: res, body });
		});
	} else if (opts.csp !== 'as-deployed') {
		throw new Error("--csp must be 'as-deployed' or 'widened'");
	}

	// Two listeners, not one. A response that fails the CORS check is never
	// delivered to `response`, so a chain recorded from that event alone stops at
	// the last hop that passed and looks like a request that never left.
	let hops = [];
	page.on('response', (res) => {
		hops.push({
			url: res.url(),
			host: new URL(res.url()).host,
			status: res.status(),
			acao: res.headers()['access-control-allow-origin'] ?? null,
			blocked: null
		});
	});
	page.on('requestfailed', (req) => {
		hops.push({
			url: req.url(),
			host: new URL(req.url()).host,
			status: null,
			acao: null,
			blocked: req.failure()?.errorText ?? 'failed'
		});
	});

	await page.goto(opts.page, { waitUntil: 'domcontentloaded' });
	// A service worker answers from its own cache and page.route never sees the
	// request, so the document under test would not be the one we just served.
	await page.evaluate(async () => {
		for (const r of await navigator.serviceWorker.getRegistrations()) await r.unregister();
		for (const n of await caches.keys()) await caches.delete(n);
	});
	await page.goto(opts.page, { waitUntil: 'domcontentloaded' });

	const documentCsp = await page.evaluate(
		() => document.querySelector('meta[http-equiv="Content-Security-Policy"]')?.content ?? '(none)'
	);
	const origin = await page.evaluate(() => location.origin);
	const secure = await page.evaluate(() => window.isSecureContext);

	const report = {
		page: opts.page,
		documentOrigin: origin,
		secureContext: secure,
		cspArm: opts.csp,
		connectSrcInDocument: (documentCsp.match(/connect-src [^;]*/) ?? ['(none)'])[0],
		families: {}
	};

	for (const family of families) {
		report.families[family] = [];
		for (const target of targetsFor(family, opts)) {
			hops = [];
			const got = await page.evaluate(IN_PAGE_FETCH, { url: target.url, headers: target.headers });
			await page.waitForTimeout(250);
			const chain = hops.filter((h) => h.url.startsWith('http'));
			const held = local.get(target.asset);
			report.families[family].push({
				asset: target.asset,
				url: target.url,
				...got,
				expectedSha256: held ? held.sha256 : null,
				expectedBytes: held ? held.bytes : null,
				digestMatches: held && got.sha256 ? got.sha256 === held.sha256 : null,
				chain
			});
		}
	}

	await browser.close();

	const line = (s) => process.stdout.write(`${s}\n`);
	line(`page          ${report.page}`);
	line(`origin        ${report.documentOrigin}   secure context: ${report.secureContext}`);
	line(`csp arm       ${report.cspArm}`);
	line(`connect-src   ${report.connectSrcInDocument}`);
	for (const [family, rows] of Object.entries(report.families)) {
		line('');
		line(`## ${family}`);
		for (const r of rows) {
			const verdict = r.error ? `REFUSED  ${r.error}` : r.digestMatches ? `read ${r.bytes} B, digest matches` : `read ${r.bytes} B, DIGEST MISMATCH ${r.sha256}`;
			line(`  ${r.asset.padEnd(24)} ${verdict}`);
			for (const h of r.chain) {
				const tail = h.blocked
					? `BLOCKED HERE  ${h.blocked}`
					: `access-control-allow-origin: ${h.acao ?? 'absent'}`;
				line(`      ${String(h.status ?? '---').padEnd(4)} ${h.host}   ${tail}`);
			}
			if (r.chain.length === 0) line('      the browser recorded no hop at all');
		}
	}
	const chainHosts = new Set();
	for (const rows of Object.values(report.families)) {
		for (const r of rows) for (const h of r.chain) chainHosts.add(h.host);
	}
	line('');
	line(`hosts seen    ${[...chainHosts].sort().join(' ') || '(none)'}`);
	if (opts.json) {
		writeFileSync(opts.json, `${JSON.stringify(report, null, 2)}\n`);
		line(`wrote         ${opts.json}`);
	}
}

main().catch((err) => {
	process.stderr.write(`${err.stack ?? err}\n`);
	process.exitCode = 1;
});
