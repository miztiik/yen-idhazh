# What prerendering weighs, on and off, 2026-09-12

**Last Updated**: 2026-09-12

Frozen. This is one run on one day; it is not updated when a later run
disagrees. A later run gets its own record.

Plan 26 ruled that the prerendered routes stay, on four facts written in prose
([`../../../TODO/20260911-26-retire-prerender-plan.md`](../../../TODO/20260911-26-retire-prerender-plan.md)
section 0.2). A ruling defended only in prose can be argued with; a ruling with
a number beside it can be overturned by a better number. This run is that
number. One tree was built both ways - as it stands, and with the seven
`export const prerender = true` declarations deleted and nothing else changed -
so section 6 of that plan, which prices what retiring prerendering would take,
can be read against what it would save.

**The interesting quantity was never the bytes.** It is whether the site has a
root document at all on the arm without the declarations, because
`adapter-static` has one fallback and GitHub Pages serves it at HTTP 404.

## Conditions

| | |
| --- | --- |
| Instrument | A throwaway PowerShell harness in the user temp directory, not committed. Nothing about it is reusable, and the recipe below is the whole of it |
| Tree | `perf/prerender-both-arms` at `e1eae979`, cut from `main`, in a worktree of its own. `npm ci` from the committed lockfile |
| Arm A | The tree as it stands. Seven declarations present. `npm run build` |
| Arm B | The same tree with those seven lines deleted and nothing else changed. `npm run build` |
| The pin | `BUILD_VERSION=1788285804815`, one literal string across both arms and all six builds. **13 characters**, because a string of another length moves the bytes it was set to hold still ([`../agent-notes/gates-and-builds.md`](../agent-notes/gates-and-builds.md)) |
| Build | `npm run build`, the whole chain. `vite build` alone is not the build - it skips four asset steps and measures whatever the last run left in `static/` |
| Box | Intel Core i7-1265U, 10 cores and 12 logical processors, 31.8 GB, Windows 11 build 26200. node v24.12.0, npm 11.6.2 |
| Load | A shared developer machine with three other agents building and testing in their own worktrees throughout. Every build ran under `backend/utilities/gate_lock.py`, which holds one heavy gate at a time across every worktree |
| Passes | Three an arm, **interleaved** - A, B, A, B, A, B - in one session at one pin |

**Every quantity here is a byte or a file count, so the box bears on none of
them.** It is named because the wall clock is on this page too, and the wall
clock is the one number that belongs to the machine: the same arm A build took
89.6 s and 352.5 s in the same session, 3.9 times apart, because a sibling
started a suite in between. That is why no duration below is used to separate
the arms.

## Method

Six commands, and the only one that is not a gate command is the line deletion.

```powershell
$env:BUILD_VERSION = '1788285804815'
Remove-Item frontend/build, frontend/.svelte-kit -Recurse -Force   # retry until gone
npm --prefix frontend run build
Get-ChildItem frontend/build -Recurse -File | Measure-Object Length -Sum
npm --prefix frontend run bundle-gate
python -m idhazh site-weight --site-tree build                     # from frontend/
```

**The arms are interleaved rather than run three-then-three** because the box
was shared for the whole session. Byte counts cannot drift with load, but a
build that fails for an unrelated reason can, and interleaving means a bad
stretch of the session lands on both arms rather than on one.

**Arm B is a scratch edit, restored from a byte snapshot taken before it.** The
seven files were read into memory and hashed with SHA-256 first; arm B rewrote
each without its one declaration line, and arm A wrote the snapshot back and
refused to continue unless every hash matched. `git status --porcelain
frontend/src` printed nothing at the end. `git diff --numstat` on arm B was
`0 1` on each of the seven files - one line deleted, none added, nowhere else
touched.

**The output directory is deleted before every build, with a retry.** Two builds
back to back can fail with `EPERM` while the previous process still holds
`.svelte-kit/output`, and the second build then writes nothing - so a script
that measures afterwards measures the first build's tree and reports two arms
that agree.

**The pin was checked rather than assumed.** Exactly one `__sveltekit_<id>`
string appears anywhere in each built tree, and it is the same id -
`__sveltekit_wgjgyk` - on both arms and in every pass. More than one would mean
the pin had not taken and every page would throw on hydration.

## The oracle, and it passed on arm A

`npm run bundle-gate` on arm A printed `/404` at **2,165 B** against the 4,400 B
in `config/idhazh.json`, and `/evals/` at **3,238 B** against 6,600 B, and
exited 0. Both ceilings hold with room, so the worktree is the tree these
numbers claim to be about. Had either fired, no figure here would have been
usable.

## The arms

| | Arm A, on | Arm B, off | Difference |
| --- | ---: | ---: | ---: |
| `index.html` documents | 8 | **0** | -8 |
| `__data.json` twins | 5 | **0** | -5 |
| Files in `build/` | 629 | 616 | -13 |
| Bytes in `build/` | 106,316,899 | 104,681,197 | **-1,635,702** |
| `site-weight` total | 101.4 MB | 99.8 MB | -1.6 MB |
| `site-weight` runway to the 1 GB cap | 1,047 published days | 1,065 | +18 |
| `frontend/build/index.html` | **present** | **absent** | - |
| `404.html` | present | present | - |
| `/404`, `gzip -5` | 2,165 B | 2,166 B | +1 B |
| `/evals/`, `gzip -5` | 3,238 B | **no document to weigh** | - |
| `npm run build` exit | 0 | **1** | - |
| `npm run bundle-gate` exit | 0 | **1** | - |

**The file count difference is exactly the documents.** Eight `index.html`
files and five `__data.json` twins come to 13, and 13 is exactly what the two
file counts differ by, so no asset and no payload was added or removed between
the arms.

**Prerendering costs 1.54 percent of the published site.** 1,635,702 bytes of
106,316,899, which is 1.6 MB of a 1,024 MB cap. Plan 26's second ESCALATE
trigger fires above 2 percent; this is below it, so the ruling stands on the
number it was taken on. In the unit the cap is actually spent in, it is **18
published days of runway out of 1,047**.

**One surviving file did change, and it is the fallback.** `/404` measured
2,165 B gzipped on arm A and 2,166 B on arm B. That single byte is the content
hashes in its `modulepreload` list - the same length, different characters,
because the client graph changed when eight entry points stopped being
prerendered. No per-file raw diff was taken, so the 1,635,702 is not claimed to
be the documents alone; it is the tree total, and the documents are what is in
it that the other arm has none of.

## The load-bearing observation: arm B has no root document, and two source comments said so first

**`frontend/build/index.html` does not exist on arm B.** `404.html` is the only
HTML file in the tree. On GitHub Pages that means every address on the site,
including `/`, is answered by the fallback at **HTTP 404**.

Two comments in the tree predicted this before it was measured, and both were
right to the sentence.

| Where | What it predicted | What arm B did |
| --- | --- | --- |
| `frontend/src/routes/+page.server.ts` | "Without this line the site root emits no `index.html` at all and GitHub Pages answers `/` with the fallback, at HTTP 404" | No `index.html` at the site root |
| `frontend/src/routes/evals/+page.ts` | "Without this the page is not written, `config/idhazh.json` names a `/evals/` ceiling that matches no route in the build, and `scripts/bundle-gate.mjs` fails" | `bundle gate FAILED - a guardrail in config/idhazh.json names nothing in the build: /evals/ is capped at 6.6 KB, and no page in the build is that route` |

**`npm run build` itself exits 1 on arm B, and that was not predicted
anywhere.** The Vite build succeeds and `adapter-static` writes the site - the
log says `Wrote site to "build"` and `done` - and then
`frontend/scripts/build-state.ts --complete` throws `The build or the SvelteKit
preview output is missing.` Its `outputFingerprint` requires
`frontend/build/index.html` to exist before it will certify a build, so the root
document is a hard precondition of this project's own build record, not only of
the reader's first screen. Every browser spec runs against a certified build, so
on arm B the whole browser suite would refuse to start.

The tree arm B wrote was still measured, because the adapter said in the log
that it had written it and the certification step is bookkeeping that runs after.
That is stated here rather than left implicit: a non-zero exit normally means a
tree nobody should read.

## The inventory this was measured against was two routes out of date

Plan 26 section 0.3 records **7 declarations over 6 routes**, read from `main`
on 2026-09-11. The declarations are still 7. The routes that ship a document are
now **8**: `/console/judgement/` and `/console/voices/` arrived with plan 25 row
#11 on 2026-09-12 and carry no declaration of their own - they inherit
prerendering from `frontend/src/routes/console/+layout.ts`, which covers all
four console children.

So deleting the seven declarations un-prerenders eight routes, not six, and any
later reading of what prerendering costs has to count the routes in the tree
rather than the declarations in the grep.

## Spread

Three builds an arm at one pin, interleaved. **The spread is zero on every
quantity on both arms.**

| Pass | Arm A files | Arm A bytes | Arm B files | Arm B bytes |
| --- | ---: | ---: | ---: | ---: |
| 1 | 629 | 106,316,899 | 616 | 104,681,197 |
| 2 | 629 | 106,316,899 | 616 | 104,681,197 |
| 3 | 629 | 106,316,899 | 616 | 104,681,197 |

The gate figures repeat too: `/404` at 2,165 B on all three arm A builds and
2,166 B on all three arm B builds, `/evals/` at 3,238 B on all three arm A
builds and absent on all three arm B builds, and `site-weight` printing 101.4 MB
in 629 files against 99.8 MB in 616 on every pass.

**A zero spread is the expected result at a pinned version and is reported
because a non-zero one would have been the finding.** Unpinned, two builds of one
unchanged tree disagree on about 20 percent of `build/` by filename, so the six
builds agreeing to the byte is what says the pin took. The wall clock is the one
thing that did move - 89.6 s to 352.5 s for the same arm A build - and it moved
with the neighbours, not with the arms.

## What it settles

**Arm B produces no root document, so retiring prerendering is not a byte
decision.** It is a decision about whether `/` may answer 404. That is the whole
finding, and it is a file that is absent rather than a number that is large.

**The bytes are small and now measured rather than assumed.** 1.54 percent of
the published site, 1.6 MB, 18 published days of the runway to the Pages cap.
Plan 26's ruling was taken on the belief that the remaining documents are a
rounding error; at 1.54 percent that belief holds, and the ESCALATE trigger set
at 2 percent does not fire.

**Two gates fail on arm B, and one of them is the project's own build record.**
`npm run bundle-gate` fails because `/evals/` has a ceiling and no document, and
`npm run build` fails because `build-state.ts` cannot certify a tree with no
root document. Section 6 of plan 26 lists "re-price two page ceilings" as one
step of a reversal; this run says the build certification is a second one it
does not list.

## What it does not settle

- **Nothing about what a reader experiences.** No decode time, no hydration
  cost, no first paint. The quantities here are the ones the 1 GB Pages cap and
  the page ceilings are written in.
- **Nothing about a runner.** The durations are a shared developer box and are
  not used to separate the arms. The byte and file counts are arithmetic over a
  deterministic build and do travel.
- **Nothing about a site with more days in it.** The 13 documents do not grow
  when the pipeline publishes - that half of prerendering was removed on
  2026-09-09 - but the denominator does, so the 1.54 percent falls as the
  archive grows and this reading is its high-water mark rather than a level.
- **Nothing about the individual routes.** Both arms treat the seven
  declarations as one switch. Whether `/evals/` earns a document of its own is a
  question about `/evals/`, and plan 26 section 8 already records it as a gap.

## See also

- [`../measurements-site.md`](../measurements-site.md) - the instrument log, which carries the figure now in force and links here.
- [`../agent-notes/gates-and-builds.md`](../agent-notes/gates-and-builds.md) - the pin, the `EPERM` trap, and why `vite build` alone is not the build.
- [`../../architecture/publishing/frontend.md`](../../architecture/publishing/frontend.md) - what the prerendered routes are for.
- [`../../../TODO/20260911-26-retire-prerender-plan.md`](../../../TODO/20260911-26-retire-prerender-plan.md) - section 0.2 is the ruling this priced, section 6 is the reversal it prices.
