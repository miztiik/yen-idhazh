# Agent Notes - Browser

**Last Updated**: 2026-09-10

Traps in Playwright, the integrated browser, the service worker, and the Svelte
components a spec drives. Index and scope:
[../agent-notes.md](../agent-notes.md).

## The integrated browser

It never drives layout and never paints, so a whole class of assertions returns
zero and reads as broken code. Verify anything geometric, animated or
interactive in the Playwright suite instead.

**Its page starts with no viewport, so `page.screenshot` throws `Cannot take screenshot with 0 width`** and aborts the whole snippet - every assertion after it is lost, which reads as a page failure. First line of any snippet that screenshots:

```javascript
await page.setViewportSize({ width: 1280, height: 900 });
```

**Every geometric answer is that same zero until you do.** `window.innerHeight` is 0, so "is it on screen" is always false and the maximum scroll position equals the whole document height - on 2026-09-01 a deep-link check read `scrollY` 281,307 of a 281,306 px document while every story measured 10,000 to 31,000 px tall. `getBoundingClientRect` returns zero width for every element, so any guard that returns early on a non-positive width takes that branch every time and the feature reads as unwired. Print `window.innerHeight` beside the assertion so a repeat is obvious. The `style` attribute is still correct and still worth asserting.

**`document.visibilityState` is `hidden` here, so `requestAnimationFrame` never fires** and anything gated on a frame never starts. A screenshot forces a frame, which is why the viewport fix above is needed in the same snippet.

**`locator.click`, `page.fill`, `locator.screenshot` and `scrollIntoViewIfNeeded` all hang the same way here**, because Playwright decides "stable" by comparing the box across two animation frames and none arrive. `{ force: true }` does not help - it fails the viewport check instead of the stability one. Drive from the DOM instead: set the value and dispatch the event the framework listens for, call `scrollIntoView` inside `page.evaluate`, set `details.open = true` where a click would have. Read the state first:

```javascript
await page.evaluate( => ({ hidden: document.hidden, state: document.visibilityState }));
```

**"waiting for element to be stable" does not mean the element is moving.** Sampling one box six times 400 ms apart on 2026-09-09 gave an identical `top`, `height` and `width` every time, with `document.getAnimations` reporting zero running. The page was still; the browser was not painting. Take that sample before you go looking for an animation, then run a headless Chromium from `frontend/` for the shot - not from a scratch directory, where node reports `Cannot find package`.

**This browser runs at a device scale of 1.25**, so every pixel figure read from it is 1.25 times the CSS number. `{ width: 1024 }` produced `window.innerWidth` 819 on 2026-09-01, so a `@media (min-width: 1024px)` rule did not match - which reads exactly like a breakpoint that was never written. Confirm with `document.documentElement.clientWidth`, remembering the media query counts the scrollbar and `clientWidth` does not. The Playwright suite has no scale factor, so it settles a breakpoint question.

**The host swallows a real `Escape` keypress**, so a dismiss handler reads as unwired. Dispatch it inside the page, where it reaches the same listener a reader's key does.

**`page.route` reports `blocked: 0` here even when the pattern is right**, because there is no context to create and the site's worker answers first. Unregister every worker AND empty every cache, navigate again, and only then install the block; a fresh registration does not control the page it was made on, so the request reaches the network. Count the aborts - that count is the only thing that tells the two outcomes apart.

**Under load it may refuse to connect at all**, timing out at 30 s with `browserType.connectOverCDP: Timeout 30000ms exceeded` on every following call, which reads as a broken build rather than a busy host. Do not keep retrying; drive Chromium yourself from `frontend/`, which also drives layout, so every quirk above stops applying.

## Waiting and routing

**A count taken straight after `goto` or `reload` measures the shell, not the day.** One document answers every dated address, so the stories arrive when the day's fetch resolves - after the load event - and whether a one-shot count finds them is a property of the machine. `service-worker.spec.ts` passed on a Windows box three runs out of three and took `main` red on `ubuntu-latest` with `Expected: 8, Received: 0`. Wait for the page's own `data-payload-state` to read `ready` through `frontend/tests/support/day-ready.ts`, and write the assertion so it retries:

```javascript
await expect(locator, 'why').toHaveCount(n); // retries
expect(await locator.count).toBe(n); // does not
```

The helper exists because seven specs already waited longhand and the eighth, written without it, was the one that broke.

**A negated `toHaveAttribute` passes when the element is absent**, so it is the wrong shape for "the page is not in state X" - it reports a state the page never reached. Playwright special-cases only `toHaveCount`, `toBeVisible`, `toBeHidden`, `toBeAttached`, `toBeDetached` and `toBeInViewport` for a locator resolving to nothing; everything else falls through to `matches = options.isNot`. Assert the positive form of the state you do want. It is strictly stronger and fails with "element(s) not found" rather than passing.

**A vacuity guard built on a pixel threshold is a cross-platform time bomb.** A spec kept "every panel with `top < 900`" and asserted the set was non-empty; the first panel sits at 894 on Windows, the runner's taller fonts pushed it past 900, the set emptied and the guard fired - green locally every time, red on `main` every time. Cut the set on something the page itself draws (the first panel's own top), never on a number you chose, and print the margin rather than the verdict when it fires: the failure said the set was empty and did not say the nearest item missed by six pixels, which is the difference between a minute and an hour. Any pixel out of a browser moves between platforms: fonts, scrollbar width, form-control metrics, fractional rounding. Measured 2026-09-09 at 1280x900 on a developer machine against the canary build.

**A polled `page.evaluate` straight after `page.goto` fails on a page that is fine**, with `Execution context was destroyed, most likely because of a navigation` - the client router does its own first navigation under the poll. Two tests failed out of 625 that way on 2026-08-31 with nothing wrong with the page. A locator assertion retries against the live document and does not race: `await expect(page.locator('html')).toHaveAttribute('data-theme', theme)`.

**A page carrying a meta refresh makes three Playwright calls lie.** On 2026-09-02, in order: `page.goto('/evals/')` rejected with `net::ERR_ABORTED; maybe frame was detached?` because the document retired the navigation that delivered it; a locator reading that document timed out having logged the new address; and a multi-route walk reported a `requestfailed` on the destination from every arm, which reads exactly like a dead link in the footer. Poll `page.url`, which is a property rather than an evaluate, and ignore a DOCUMENT request whose failure is `net::ERR_ABORTED`.

```typescript
await page.goto('/evals/', { waitUntil: 'commit' }).catch( => {});
await expect.poll( => page.url).toMatch(/\/console\/$/);
```

**`page.url` read straight after a click still says the page you left**, because every route is prerendered and the client router takes the click - so a smoke reports that a link went nowhere. Wait for the address alongside the click: `await Promise.all([page.waitForURL('**/archive/'), locator.click])`.

**`page.goto` to the same path with a different fragment never re-mounts the shell.** It is a same-document navigation, so `afterNavigate` does not fire and anything the layout does on arrival does not run - a 2026-09-01 restore spec resolved its locator 33 times and never saw the attribute. A repeated arm also measures nothing: three visits read 680, 26 and 30 ms, and the 26 is a navigation that did no work. Navigate somewhere else first, and give every visit its own browser context.

**A `page.route` pattern written as a glob can intercept nothing and say nothing.** `page.route('**/digest/**/digest.json')` counted zero aborts against a URL it should have matched on 2026-09-01, where the same handler as a `RegExp` counted one. Prefer a `RegExp`, and print the count - a route that never fired is a null result, not a pass. A pattern one segment too wide counts the page's own assets: `**/digest/**` catches an item's picture as well, so an arm asserting "this reached the network for nothing" failed at 2 on a fetch nobody made.

**`page.route` cannot block what the service worker answers.** The worker's fetches do not pass through the page's route table, so an interception arm silently covers nothing: four aborted navigations left a day page fully rendered with `aborted: 0` (2026-09-05), and a `**/*.svg` 404 route let all 43 drawings draw (2026-09-06). Block workers for the spec, and use `context.route` so a page opened later is covered too:

```javascript
test.use({ serviceWorkers: 'block' }); // the suite's own default in playwright.config.ts
const context = await browser.newContext({ serviceWorkers: 'block' });
```

`PerformanceResourceTiming.workerStart` is how you tell what a worker answered - read it over `getEntriesByType('navigation')` and `('resource')` and count the entries above zero. Each Playwright test gets its own `CacheStorage`, so a warm-cache scenario must warm it inside the test, and a faked error response is never written because transformers.js caches only a 200.

**A payload the cold document already carries is never fetched**, so a spec waiting for its request waits for ever and reports `blocked: 0` twice. The console's band is read by a universal `load`, so SvelteKit resolves that fetch against the staged payload at build time; a move between two routes under the same layout reuses layout data too. The one moment a browser really fetches it is when the layout is ENTERED from outside it - start on a page under a different layout, install the block, then click a link in, and prove the move was client-side with `performance.getEntriesByType('navigation').length === 1`.

**A request-wave count reads as a round-trip guard and cannot fail.** Grouping a trace into waves - open a new wave when a request starts after every request in the current wave has finished - lets one slow download hold its wave open and absorb a whole serial chain running beside it, so the number does not move when the chain lengthens. Proved on 2026-09-10 against `frontend/tests/console-cold-load.spec.ts`: two round trips inserted ahead of the telemetry fetches took the real chain from three to five and left the wave count at three. Count the longest run of requests that each ended before the next began, and take the times from Chromium rather than from the handler - `performance.now` inside `requestfinished` measures when Playwright's socket delivered the event, so quick local responses arrive batched and every chain reads as one hop.

```typescript
const t = request.timing; // ms, and responseEnd is relative to startTime
const end = t.responseEnd >= 0 ? t.startTime + t.responseEnd : t.startTime;
```

**A cross-origin failure is invisible to Playwright's `response` event.** The event never fires for a response the browser refuses on the same-origin policy, so a chain recorded from it stops at the last hop that passed and prints "no request left the browser" for a request that had left and come back refused. Listen for `requestfailed` as well; it is the only listener that names the hop that broke. `curl` cannot answer this either - it enforces no same-origin policy and prints a 200 with the right bytes.

**A route answering 500 does not simulate a failed download.** transformers.js treats only a 404 from a same-origin path as a miss; any other status is read as the file, so it takes the error body as the model, fires its own `done` event, and dies about 200 ms later inside the ONNX runtime with `protobuf parsing failed` - neither where the route is nor in the library the route names. The route is also not total: a pattern matching only `.onnx` still lets the tokenizer files and the 21.6 MB wasm through, and that arriving file is what made a retry test flaky by reporting progress after the failure.

**A lazy fetch fires only for what is near the viewport.** `ItemVisual.svelte` observes with a `100%` root margin, so a single jump to the bottom steps over every slot and the observer never fires. Scroll one viewport at a time; zero fetches at the top of a long page is a null result.

**Aborting a fetch makes Chrome log a console error of its own**, so a zero-console-error assertion (`CLAUDE.md` section 12) reports a failure the page did not cause. Classify rather than count: match the errors your own abort produced by URL, and report how many of each there were.

## Driving components

**A test driving a hydrated control must wait for hydration**, not for the element. Every `[data-window-preset]` input is `disabled` in the prerendered document and enabled on mount, so a click issued before that lands times out at about 15 s with no useful message:

```typescript
await expect(page.locator(`[data-window-preset="${DEFAULT_DAYS}"] input`)).toBeEnabled;
```

**A bare `[data-attr]` selector can match a wrapper and a child at once**, so a geometry read off the wrong one is silently wrong rather than an error. On the digest page `[data-band]` is on the `<article>` and on the confidence chip inside it. Name the element as well as the attribute: `span[data-band]`.

**A CSS length read off `style` is the browser's serialisation** - a bar drawn at `inline-size: 100.0000%` comes back as `100%` while every other row at `52.9412%` round-trips, so a string comparison fails on exactly one row and reads like a bug in the one case the arithmetic cannot get wrong (2026-08-30). Compare parsed numbers against `Number(expected.toFixed(4))`.

**`getComputedStyle(document.body).backgroundColor` is `rgba(0, 0, 0, 0)`.** `app.css` puts the background on `html` and the browser propagates the root element's background to the canvas, so the body genuinely has none and a theme assertion written against it fails on every route at once - which reads exactly like the stylesheet not loading. Read `documentElement`, the element that paints.

**A transitioned paint property read straight after `hover` or `focus` returns an interpolation**, so a card eased over `--dur-fast` reported `rgb(86, 78, 230)` against an accent of `rgb(79, 70, 229)`. One `requestAnimationFrame` lands mid-ease. Poll until it settles and let the poll be the assertion, resolving the expected value through a throwaway element so the comparison is against the token rather than a string somebody typed.

**`locator.hover` scrolls the element into view**, so a viewport-relative rect taken afterwards says the element moved - `top` 332 before and 18 after, a 314 px jump the CSS does not contain (2026-08-31). Take `rect.top + window.scrollY`, and scroll before the first reading as well.

**A chart below the fold cannot be pointed at**, and the failure is silent: `boundingBox` returns PAGE coordinates, so `page.mouse.move` at y=8,000 in a 1,000 px viewport lands nowhere, the pointer handler never fires, and the readout prints its resting string. `await plot.scrollIntoViewIfNeeded` before every hover on a long page. A chart also follows a reactive option change in place - `Chart.svelte` hands the live chart each new option through `update`, so assert that the option count rose while the instance count held, not that it re-rendered.

**`locator.screenshot` on a console panel times out on "waiting for element to be stable"**, because something above it is still settling and the wait is for the whole page. Scroll it into view inside an `evaluate`, wait once, then take a VIEWPORT screenshot - the element form failed twice at 10 s on `/console/model/` where the viewport one returned immediately (2026-09-06).

**Walking the reading page's pager runs past the test timeout.** `Show N more` adds twelve stories and re-renders the list, so a 627-story day is 52 clicks over a list that grows to 627 nodes - 1.3 minutes on a quiet machine and past the 180 s timeout on a loaded one, for a comparison the control's own label answers in one read. Read the label.

**Playwright prints the code frame from disk and runs the version loaded at collection**, so after an edit the frame and the behaviour can disagree. Re-run rather than reasoning about the frame.

**One arm of a two-arm test failing is a race, not a regression**, when the other arm passes on the same commit. `layout-overflow.spec.ts` runs the same routes and widths in dark and then light, and a theme changes colour and not text metrics: on 2026-09-01 the dark arm failed in 5.3 s on a `scrollWidth` of 789 while the light arm passed the identical assertions 1.1 min later, and the spec alone passed 6 of 6. A per-day figure and a per-article figure need different degraded arms - emptying every ledger reaches only the whole-surface empty state, so drop one real day and one real item instead.

**Two fixtures that both fit inside the narrowest preset make a window oracle pass on a route that ignores the window.** Every preset then selects every row, so the assertion is true for the wrong reason. Pick a fixture with a row only the widest preset can reach; a stronger assertion does not fix it.

**A new chart component that draws a `<path>` fails the icon gate.** `icons.spec.ts::no component holds a path of its own` forbids path data outside `frontend/src/lib/icons/`, and its exemption for charts is a NAME regex - the existing charts draw with `line`, `rect` and `polyline` and never needed it. The failure names the icon rule, which is nowhere near the row that caused it.

**A spec cannot import a client module that imports `$app/paths` as a value.** The WHOLE suite fails at load time with `Error: Cannot find package '$app' imported from...` - not one test, all of them, before a browser opens, and the error naming a package rather than a test is the tell. Split the module, or bundle it: UMD output rather than IIFE, because the wrapper assigns the global itself; `addInitScript` rather than `addScriptTag`, because it is a debugger injection and `script-src 'self'` need not be relaxed; and a stub holding a PROJECT path rather than the empty string the preview server uses, or a URL built without `base` cannot match the route pattern and the interception count silently falls to zero.

## Svelte

**A `<style>` inside `<noscript>` compiles, and it is the only way to write a no-script rule** - Svelte treats the root `<style>` as the component's CSS block and every nested one as an ordinary element, so the rule reaches the prerendered document verbatim. But the rule is unscoped, and a Svelte scoped class rule outranks it: `.field.svelte-<hash>` is specificity (0,2,0) against (0,1,0) for the attribute selector a `<noscript>` block has to use, so the control it should hide stays on the page and the symptom only appears with scripting off. Keep `display` off the element carrying the attribute and put the layout on a child, or the fix becomes an `!important`.

**`$service-worker`'s `files` is every file under `static/`, and `build` is not the shell.** `frontend/static/digest/` is staged from the pipeline's output, so the default baked every published day and every rendered visual into `build/service-worker.js` - 16,888 bytes of strings on 2026-09-02, growing with every published day, with the file size the only tell because the worker filters them at run time. `kit.serviceWorker.files` is the filter and the same worker is 4,825 bytes with it. And `build` is the whole client bundle, 23.56 MB across 57 files of which 21.60 MB is the search encoder's ONNX runtime, so `cache.addAll(build)` in the install handler downloads 23.5 MB to a reader who opened one day.

**SvelteKit's own service-worker registration has no `.catch`**, so any browser that refuses - a policy, a private window, `serviceWorkers: 'block'` - becomes an unhandled rejection on every page, and every spec counting console errors goes red at once. `kit.serviceWorker.register: false` plus one registration call of your own fixes it, and leaves exactly one file naming the worker API for a test to assert on.

**Widening a Svelte action's node type to a union breaks its listeners**, because `addEventListener` overload sets do not merge across element types - `SVGSVGElement | HTMLElement` produced eight errors on lines that were not edited. Keep one `[type, handler]` list and attach through a single `const events: EventTarget = node`, so the add and remove halves cannot drift apart.

## See also

- [../agent-notes.md](../agent-notes.md) - the index and what belongs on these pages.
- [gates-and-builds.md](gates-and-builds.md) - running the browser suite, and serving a build to measure it.
- [shell-and-tools.md](shell-and-tools.md) - reading a long browser-suite log.
- [../../concepts/design-system.md](../../concepts/design-system.md) - the surfaces these specs assert on.
