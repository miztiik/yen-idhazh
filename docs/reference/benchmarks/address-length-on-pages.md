# Address length on GitHub Pages

**Last Updated**: 2026-10-06

How long a Data explorer page address can be before GitHub Pages refuses it, and how long an ASCII question can be while still fitting a shared link.

GitHub Pages answered a request target of 8,192 bytes and refused 8,193 bytes. With all 25 current ledgers and a custom date span, the address test's 6,939-character question uses an 8,191-byte request target; one more character uses 8,193 bytes. Compression depends on the question text, so this measured cap is for the test's fixed input, not a promise for every question. The address writer still drops the question when the complete link exceeds 8,192 bytes.

## Conditions

| Subject | Value |
| --- | --- |
| Date | 2026-10-02T17:36:35Z |
| Host | `https://miztiik.github.io` |
| Page | `/yen-idhazh/console/data-explorer/` |
| Instrument | Node `fetch`, `redirect: 'manual'`, with the script below |
| Accepted response | HTTP 200 or HTTP 404, because the fallback document answers this route |
| Refused response | HTTP 414 |

The probe did not run through a browser and did not load the page. It measured the front end that receives the HTTP request.

## Method

The script doubled `q` until GitHub Pages refused the request, then bisected the last accepted and first refused lengths. It used base64url characters so every `q` character was one byte in the address.

```js
// Row 5's reading: the longest address GitHub Pages answers for the Data explorer page.
const base = 'https://miztiik.github.io/yen-idhazh/console/data-explorer/?q=';
const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_';
const q = (n) => Array.from({ length: n }, (_, i) => alphabet[(i * 7) % 64]).join('');
const seen = [];
async function probe(n) {
  const url = base + q(n);
  let status;
  try {
    const r = await fetch(url, { redirect: 'manual', headers: { 'user-agent': 'yen-idhazh address-length probe' } });
    status = r.status; await r.arrayBuffer();
  } catch (e) { status = 'error ' + (e.cause?.code ?? e.message); }
  seen.push({ n, url: url.length, status });
  console.log(`q ${n} chars, address ${url.length} chars -> ${status}`);
  return status === 200 || status === 404;
}
let lo = 0, hi = null, n = 1024;
while (hi === null) { if (await probe(n)) { lo = n; n *= 2; if (n > 1 << 20) break; } else { hi = n; } }
while (hi !== null && hi - lo > 1) { const mid = Math.floor((lo + hi) / 2); if (await probe(mid)) lo = mid; else hi = mid; }
console.log(`LONGEST answered q: ${lo} chars, address ${base.length + lo} chars; first refused q: ${hi}`);
const refusal = seen.find((s) => s.n === hi);
console.log(`refusal status: ${refusal?.status}`);
console.log(`measured ${new Date().toISOString()}`);
```

## Reading

| Case | `q` characters | Whole address | Result |
| --- | ---: | ---: | --- |
| Longest answered | 8,155 | 8,217 | HTTP 404 fallback document |
| First refused | 8,156 | 8,218 | HTTP 414 |

The origin, `https://miztiik.github.io`, is 25 bytes. Removing it leaves the request target: path plus query. The longest answered request target is 8,192 bytes: 8,217 minus 25. The first refused request target is 8,193 bytes: 8,218 minus 25.

## Query size in force

The Data explorer page link must leave room for the path, every ledger name and a custom span with `from=YYYY-MM-DD` and `end=YYYY-MM-DD`. The address writer uses `URLSearchParams`, so each comma between ledgers is `%2C`, three bytes.

| Part | Bytes |
| --- | ---: |
| Base path, `/yen-idhazh/console/data-explorer/` | 34 |
| `?ledgers=` | 9 |
| All 25 ledger names, with a raw comma between each | 338 |
| The 24 encoded commas, two extra bytes each over a raw comma | 48 |
| `&from=YYYY-MM-DD` | 16 |
| `&end=YYYY-MM-DD` | 15 |
| `&q=` | 3 |
| Fixed total before the encoded question | 487 |
| Encoded test question at 6,939 characters | 7,704 |
| Whole request target at 6,939 characters | 8,191 |

The question uses the deterministic printable ASCII sequence in `frontend/tests/console-data-explorer-address.spec.ts`, seed `0x1234abcd`, then `CompressionStream('deflate-raw')` and base64url encoding. The browser produced:

```text
6,939 characters -> 5,778 compressed bytes -> 7,704 base64url characters
487 + 7,704 = 8,191 bytes
6,940 characters -> 5,779 compressed bytes -> 7,706 base64url characters
487 + 7,706 = 8,193 bytes
```

The configured cap is 6,939 characters. The address test checks that the question fits at this cap and is left out one character later. The cap is tied to that fixed test input; the byte limit remains the final guard for other question text.

## What would make this stale

GitHub changing its Pages front end or request-line limit would make this reading stale. A different host, such as a custom domain or a local preview server, needs its own reading.

## See also

- [../documentation-structure.md](../documentation-structure.md) - what a benchmark record carries.
- [../../how-to/run-the-gates.md](../../how-to/run-the-gates.md) - how local tests and CI divide the checks.
- [../../../TODO/20260928-55-one-page-queries-every-ledger-plan.md](../../../TODO/20260928-55-one-page-queries-every-ledger-plan.md) - row 5, which uses this reading.
