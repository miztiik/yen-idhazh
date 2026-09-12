/** The manifest that makes a second origin safe, driven both ways.
 *
 * The encoder now has somewhere else to come from when this site cannot serve
 * it. That is only defensible because of what is in this file: every arriving
 * file is hashed against a digest committed in `config/idhazh.json`, and a
 * single miss discards the whole set. Without that, the second origin would be
 * a permission for another party to put bytes into a reader's tab.
 *
 * **The arm that matters is the failing one.** A verifier that always answered
 * "fine" would pass every happy-path test ever written and would defend
 * nothing, so most of this file drives the refusals: a wrong digest, a
 * truncation, a 404, an unreachable host, a deadline. Each one has to end with
 * the caller holding no files at all.
 *
 * This is a `logic` spec and not a browser one. Nothing here touches the
 * network (Guardrail #7): every response is built in memory from bytes this file
 * owns, and the real weights are never fetched. `crypto.subtle` is the same
 * implementation in node as in the tab, so the hashing under test is the
 * hashing that ships.
 */

import { expect, test } from '@playwright/test';
import {
	fetchVerifiedWeights,
	manifestPaths,
	NO_SECOND_ORIGIN,
	remoteUrl,
	sha256Hex,
	type EncoderSource
} from '../src/lib/assist/weights';

/** Bytes standing in for one encoder file. Small, so a test is a test. */
const FILES: Record<string, Uint8Array> = {
	'config.json': new TextEncoder().encode('{"model_type":"bert"}'),
	'onnx/model_quantized.onnx': new Uint8Array([0x08, 0x01, 0x12, 0x04, 0x74, 0x65, 0x73, 0x74]),
	'tokenizer.json': new TextEncoder().encode('{"version":"1.0"}')
};

/** A manifest whose digests are the real SHA-256 of the bytes above. */
async function honest(): Promise<EncoderSource> {
	const digests: Record<string, string> = {};
	for (const [path, bytes] of Object.entries(FILES)) {
		digests[path] = await sha256Hex(bytes.buffer as ArrayBuffer);
	}
	return {
		baseUrl: 'https://huggingface.co/Xenova/all-MiniLM-L6-v2',
		cdnOrigins: ['https://us.aws.cdn.hf.co'],
		revision: '751bff37182d3f1213fa05d7196b954e230abad9',
		digests,
		deadlineMs: 5000
	};
}

/** An origin that answers with whatever `bytesFor` decides, and counts the asks. */
function origin(bytesFor: (path: string) => Uint8Array | number | 'hang') {
	const asked: string[] = [];
	const fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
		const url = String(input);
		const path = url.split('/resolve/')[1]!.split('/').slice(1).join('/');
		asked.push(path);
		const answer = bytesFor(path);
		if (answer === 'hang') {
			// Never resolves on its own. Only the deadline ends this.
			return new Promise<Response>((_, reject) => {
				init?.signal?.addEventListener('abort', () => reject(new Error('aborted')));
			});
		}
		if (typeof answer === 'number') return new Response(null, { status: answer });
		return new Response(answer as BodyInit, { status: 200 });
	}) as typeof globalThis.fetch;
	return { asked, fetch };
}

test.describe('a verified set', () => {
	test('every file is fetched from the pinned commit, not a branch', async () => {
		const source = await honest();
		expect(remoteUrl(source, 'onnx/model_quantized.onnx')).toBe(
			'https://huggingface.co/Xenova/all-MiniLM-L6-v2/resolve/' +
				'751bff37182d3f1213fa05d7196b954e230abad9/onnx/model_quantized.onnx'
		);
	});

	test('only paths the manifest names can be asked for', async () => {
		// The URL is built from two committed values and a KEY of the manifest, so
		// there is no path a caller could hand in that this module would fetch.
		// Nothing here reads a payload field or any fetched text (Guardrail #11).
		const source = await honest();
		const { asked, fetch } = origin((path) => FILES[path]!);
		await fetchVerifiedWeights(source, { fetch });
		expect(asked.sort()).toEqual(manifestPaths(source));
	});

	test('all of it is handed back when every digest matches', async () => {
		const source = await honest();
		const { fetch } = origin((path) => FILES[path]!);
		const outcome = await fetchVerifiedWeights(source, { fetch });
		expect(outcome.ok).toBe(true);
		if (!outcome.ok) return;
		expect([...outcome.files.keys()].sort()).toEqual(manifestPaths(source));
		for (const [path, bytes] of outcome.files) {
			expect(await sha256Hex(bytes)).toBe(source.digests[path]);
		}
	});
});

test.describe('a set with anything wrong in it is discarded whole', () => {
	test('one corrupted file discards the set, and the good files with it', async () => {
		// THE ORACLE. A single flipped bit in one file, and the caller gets
		// nothing - not the two files that verified, not a partial set, nothing.
		// Provenance is never mixed: four of ours and one of theirs is the outcome
		// this refusal exists to make impossible.
		const source = await honest();
		const tampered = new Uint8Array(FILES['tokenizer.json']!);
		tampered[2] ^= 0x01;
		const { fetch } = origin((path) => (path === 'tokenizer.json' ? tampered : FILES[path]!));

		const outcome = await fetchVerifiedWeights(source, { fetch });

		expect(outcome.ok).toBe(false);
		if (outcome.ok) return;
		expect(outcome.reason).toBe('mismatch');
		expect(outcome.path).toBe('tokenizer.json');
		expect('files' in outcome).toBe(false);
	});

	test('a digest that is close is still wrong', async () => {
		// A verifier comparing prefixes, or lengths, or "starts with", passes the
		// test above and fails this one.
		const source = await honest();
		const almost = { ...source, digests: { ...source.digests } };
		const real = almost.digests['config.json']!;
		almost.digests['config.json'] = real.slice(0, -1) + (real.endsWith('a') ? 'b' : 'a');
		const { fetch } = origin((path) => FILES[path]!);

		const outcome = await fetchVerifiedWeights(almost, { fetch });

		expect(outcome.ok).toBe(false);
		if (!outcome.ok) expect(outcome.reason).toBe('mismatch');
	});

	test('a truncated body is a mismatch, not a short file', async () => {
		const source = await honest();
		const half = FILES['onnx/model_quantized.onnx']!.slice(0, 4);
		const { fetch } = origin((path) =>
			path === 'onnx/model_quantized.onnx' ? half : FILES[path]!
		);

		const outcome = await fetchVerifiedWeights(source, { fetch });

		expect(outcome.ok).toBe(false);
		if (!outcome.ok) expect(outcome.reason).toBe('mismatch');
	});

	test('a non-200 refuses before anything is hashed', async () => {
		const source = await honest();
		const { fetch } = origin((path) => (path === 'tokenizer.json' ? 404 : FILES[path]!));

		const outcome = await fetchVerifiedWeights(source, { fetch });

		expect(outcome.ok).toBe(false);
		if (!outcome.ok) expect(outcome.reason).toBe('refused');
	});

	test('an origin that cannot be reached refuses', async () => {
		const source = await honest();
		const fetch = (async () => {
			throw new TypeError('Failed to fetch');
		}) as typeof globalThis.fetch;

		const outcome = await fetchVerifiedWeights(source, { fetch });

		expect(outcome.ok).toBe(false);
		if (!outcome.ok) expect(outcome.reason).toBe('unreachable');
	});

	test('a set that never finishes ends at the deadline', async () => {
		// The deadline covers the SET and not each file, which is why one hanging
		// file ends the whole attempt rather than four of them adding up.
		const source = { ...(await honest()), deadlineMs: 60 };
		const { fetch } = origin((path) => (path === 'config.json' ? 'hang' : FILES[path]!));

		const outcome = await fetchVerifiedWeights(source, { fetch });

		expect(outcome.ok).toBe(false);
		if (!outcome.ok) expect(outcome.reason).toBe('timeout');
	});

	test('no second origin is a refusal and not an empty success', async () => {
		// `NO_SECOND_ORIGIN` is what every failed config read answers, so this is
		// the arm that keeps a missing or malformed block from turning into a
		// fetch nobody meant to make.
		let called = 0;
		const fetch = (async () => {
			called += 1;
			return new Response(null, { status: 200 });
		}) as typeof globalThis.fetch;

		const outcome = await fetchVerifiedWeights(NO_SECOND_ORIGIN, { fetch });

		expect(outcome.ok).toBe(false);
		if (!outcome.ok) expect(outcome.reason).toBe('off');
		expect(called).toBe(0);
	});

	test('a manifest with no digests fetches nothing, however good the URL is', async () => {
		let called = 0;
		const fetch = (async () => {
			called += 1;
			return new Response(null, { status: 200 });
		}) as typeof globalThis.fetch;

		const outcome = await fetchVerifiedWeights({ ...(await honest()), digests: {} }, { fetch });

		expect(outcome.ok).toBe(false);
		if (!outcome.ok) expect(outcome.reason).toBe('off');
		expect(called).toBe(0);
	});
});
