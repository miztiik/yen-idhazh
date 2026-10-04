# Address length on GitHub Pages

**Last Updated**: 2026-10-03

How long a Records page address can be before GitHub Pages refuses it, and how long an ASCII question can be while still fitting a shared link.

GitHub Pages answered a request target of 8,192 bytes and refused 8,193 bytes. For this page, that means the largest ASCII statement that fits a worst-case link is 5,782 characters. ASCII means one byte per character; non-ASCII text can still fit, but this number does not promise it.

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
// Row 5's reading: the longest address GitHub Pages answers for the Records page.
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

The Records page link must leave room for the path, every ledger name, the widest span preset and row 6's future `end=YYYY-MM-DD` field. The address writer uses `URLSearchParams`, so each comma between ledgers is `%2C`, three bytes.

| Part | Bytes |
| --- | ---: |
| Base path, `/yen-idhazh/console/data-explorer/` | 34 |
| `?ledgers=` | 9 |
| All 24 ledger names | 361 |
| The 23 encoded commas, two extra bytes each over a raw comma | 46 |
| `&days=90` | 8 |
| `&end=YYYY-MM-DD` reserved for row 6 | 15 |
| `&q=` | 3 |
| Fixed total before the encoded question | 476 |
| Space left under 8,192 bytes | 7,716 |

A stored `deflate-raw` block for an incompressible ASCII statement costs the statement bytes plus a 5-byte header. Base64url without padding needs at most `ceil(4 * bytes / 3)` characters. The largest `n` that fits is:

```text
476 + ceil(4 * (n + 5) / 3) <= 8192
ceil(4 * (5782 + 5) / 3) = 7716
476 + 7716 = 8192
ceil(4 * (5783 + 5) / 3) = 7718
476 + 7718 = 8194, which is 2 bytes too long
```

So the current answer is 5,782 ASCII characters. The test `frontend/tests/console-data-explorer-address.spec.ts` binds this number to the real encoder by writing a 5,782-character printable ASCII statement, adding every ledger name, using the 90-day preset and reserving 15 bytes for `end=YYYY-MM-DD`.

## What would make this stale

GitHub changing its Pages front end or request-line limit would make this reading stale. A different host, such as a custom domain or a local preview server, needs its own reading.

## See also

- [../documentation-structure.md](../documentation-structure.md) - what a benchmark record carries.
- [../../how-to/run-the-gates.md](../../how-to/run-the-gates.md) - how local tests and CI divide the checks.
- [../../../TODO/20260928-55-one-page-queries-every-ledger-plan.md](../../../TODO/20260928-55-one-page-queries-every-ledger-plan.md) - row 5, which uses this reading.
