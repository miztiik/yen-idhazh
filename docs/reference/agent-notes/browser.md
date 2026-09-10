# Agent Notes - Browser

**Last Updated**: 2026-09-10

Traps in Playwright, the integrated browser, the service worker, and the Svelte
components a spec drives. Index and scope:
[../agent-notes.md](../agent-notes.md).

## The integrated browser

**Its page starts with no viewport, so `page.screenshot()` throws `Cannot take screenshot with 0 width`** and aborts the whole snippet - every assertion after it is lost, which reads as a page failure. First line of any snippet that screenshots:

```javascript
await page.setViewportSize({ width: 1280, height: 900 });
```

**`getBoundingClientRect()` returns zero width for every element on some routes**, so correct code with an early-return guard looks broken and a layout assertion fails on a page that renders fine. Check the element you grabbed is the one you meant (match on a data attribute, not a tag), and prefer a headless run from `frontend/` for anything dimensional.

**`document.visibilityState` is `hidden` here, so `requestAnimationFrame` never fires** and anything gated on a frame never starts. A screenshot forces a frame, which is why the viewport fix above is needed in the same snippet.

**The page can be hidden outright, and then every `click()` times out** with a message about actionability. Read `document.hidden` first.

**`locator.click()`, `page.fill()`, `locator.screenshot()` and `scrollIntoViewIfNeeded()` all hang the same way here.** Drive from the DOM instead - set the value and dispatch the event, or call `scrollIntoView` inside `page.evaluate`.

**"waiting for element to be stable" does not mean the element is moving.** Sample the bounding box twice before believing it.

**This browser runs at a device scale of 1.25**, so every pixel figure read from it is 1.25 times the CSS number.

**The host swallows a real `Escape` keypress**, so a dismiss path cannot be tested through the keyboard here.

**`page.url()` read straight after a click still says the page you left.** Wait on the destination, not on the call returning.

**Under load it may refuse to connect at all.** Drive Chromium yourself from `frontend/` rather than retrying.

## Waiting and routing

**A polled `page.evaluate` straight after `page.goto` fails**, because the poll starts before the document exists. Use a locator assertion, which retries against the live page.

**Walking the reading page's pager on a real day runs past the test timeout.** A published day carries hundreds of stories, so clicking through to the end is minutes of navigation. Read the pager's own label for the count instead of walking it, or drive the canary day, which is fixed in size.

**A count taken straight after `goto` or `reload` measures the shell, not the day.** One document answers every dated address, so the stories arrive when the day's fetch resolves - after the load event - and whether a one-shot count finds them is a property of the machine. `service-worker.spec.ts` passed on a Windows box three runs out of three and took `main` red on `ubuntu-latest` with `Expected: 8, Received: 0`. Wait for the page's own `data-payload-state` to read `ready`, and write the assertion so it retries:

```javascript
await expect(locator, 'why').toHaveCount(n);   // retries
expect(await locator.count()).toBe(n);         // does not
```

**A vacuity guard built on a pixel threshold is a cross-platform time bomb.** A spec kept "every panel with `top < 900`" and asserted the set was non-empty; the first panel sits at 894 on Windows, the runner's taller fonts pushed it past 900, the set emptied and the guard fired - green locally every time, red on `main` every time. Cut the set on something the page itself draws (the first panel's own top), never on a number you chose, and print the margin rather than the verdict when it fires. Any pixel out of a browser moves between platforms: fonts, scrollbar width, form-control metrics, fractional rounding.

**A page carrying a meta refresh makes three Playwright calls lie.** `page.url()`, a URL assertion and a locator can each answer about the page you asked for while the browser is already elsewhere. Assert on the destination.

**A `page.route()` pattern written as a glob can intercept nothing and say nothing.** Prefer a `RegExp`, and print the count of intercepted requests - a route that never fired is a null result, not a pass. A pattern one segment too wide counts the page's own assets as well as the ones you meant.

**`page.route` cannot block what the service worker answers.** The worker's fetches do not pass through the page's route table, so an interception arm silently covers nothing. Block workers for the spec, or unregister and clear the caches on every load:

```javascript
test.use({ serviceWorkers: 'block' });
```

`PerformanceResourceTiming.workerStart` is how you tell what a worker answered. Each Playwright test gets its own `CacheStorage`, so a warm-cache scenario must warm it inside the test.

**A payload the cold document already carries is never fetched**, so a spec waiting for its request waits for ever. Assert on what rendered.

**A cross-origin failure is invisible to Playwright's `response` event.** Listen for `requestfailed` as well, or the spec passes through a blocked request.

**A route answering 500 does not simulate a failed download.** The client treats only 404 as a miss, so the 500 arm exercises a path that does not exist.

**A lazy fetch fires only for what is near the viewport.** Scroll one viewport at a time; zero fetches at the top of a long page is a null result.

**Aborting a fetch makes Chrome log a console error of its own**, so a zero-console-error assertion has to classify the errors rather than count them.

## Driving components

**A test driving a hydrated control must wait for hydration**, not for the element. The markup is prerendered, so the control exists and does nothing.

**A CSS length read off `style` is the browser's serialisation** - `100.0000%` comes back as `100%`. Compare parsed numbers.

**`getComputedStyle(document.body).backgroundColor` is `rgba(0, 0, 0, 0)`.** The page paints on `documentElement`; read that.

**A transitioned paint property read straight after `hover()` or `focus()` returns an interpolation**, so the assertion fails on a value between the two states. Poll until it settles.

**`locator.hover()` scrolls the element into view**, so a viewport-relative rect taken afterwards says the element moved.

**A chart below the fold cannot be pointed at**, and a chart follows a reactive option change in place - assert the option count, not a re-render.

**Playwright prints the code frame from disk and runs the version loaded at collection**, so after an edit the frame and the behaviour can disagree. Re-run rather than reasoning about the frame.

**One arm of a two-arm test failing is a race, not a regression**, when the other arm passes on the same commit. A per-day figure and a per-article figure need different degraded arms.

**Two fixtures that both fit inside the narrowest preset make a window oracle pass on a route that ignores the window.** Pick fixtures that straddle the boundary.

**A new chart component that draws a `<path>` fails the icon gate**, which counts path elements to find unlicensed icons. Register the component or draw with primitives.

**A spec cannot import a client module that imports `$app/paths` as a value.** Bundle it first (esbuild or vite, UMD output, a stub for the app module) and inject with `addInitScript`.

## Svelte

**A `<style>` inside `<noscript>` compiles, and it is the only way to write a no-script rule** - but the rule is unscoped, so a scoped class rule on the same property outranks it. Match the specificity deliberately.

**`$service-worker`'s `files` is every file under `static/`, and `build` is not the shell** - it is the whole client bundle, 23.56 MB when measured. Precaching either by default ships far more than intended. Set `kit.serviceWorker.files` to a filter.

**SvelteKit's own service-worker registration has no `.catch()`**, so a failed registration is an unhandled rejection in the console rather than a caught error.

**Widening a Svelte action's node type to a union breaks its listeners**, because the event map narrows to the intersection. Keep the action typed to the element it is used on.

## See also

- [../agent-notes.md](../agent-notes.md) - the index and what belongs on these pages.
- [gates-and-builds.md](gates-and-builds.md) - running the browser suite, and serving a build to measure it.
- [shell-and-tools.md](shell-and-tools.md) - reading a long browser-suite log.
