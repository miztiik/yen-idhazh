# Agent Notes - Browser

**Last Updated**: 2026-09-29

Checks before trusting a browser result. Follow the [browser smoke procedure](../../how-to/run-the-gates.md).

## The integrated browser

- Set a viewport and verify its actual CSS dimensions before measuring layout.
- If embedded tools cannot paint or deliver input, repeat the affected check through the project's Playwright runner. DOM-dispatched events do not prove native pointer or keyboard input works.

## Waiting and routing

- **A worker content-policy refusal reads absent through `page.on('console')`, but exists in the worker log.** Playwright forwards worker `console.log`-style calls, not worker log entries such as CSP refusals. Open a CDP session, `Target.setAutoAttach`, enable `Log` on worker targets, and read `Target.receivedMessageFromTarget`; Playwright still emits `request` and `requestfailed` for the blocked request, with `failure().errorText === 'csp'`, and no `response`.

- Wait for page readiness and enabled controls with retrying assertions. Assert the intended state positively; an absent element must not pass a state check.
- Use fresh browser contexts for cold-load cases. Distinguish full navigation, client-side routing and fragment-only changes.
- Prove that a failure test reached its target request. Account for service workers, caches and data already in the document; zero interceptions do not exercise a network failure.
- Register a browser-context route before navigation to serve a dedicated worker's add-on from a local file. In Playwright 1.62.1 with Chromium 151, this also intercepted requests forwarded by a pass-through service worker; such a request has no page frame. Verify the production service worker separately.
- Routing disables HTTP caching. A context that intercepts an add-on can prove offline test delivery, but cannot certify browser-cache behavior. Keep cache-sensitive checks separate and count actual requests.

## Driving components

- Scope locators to the intended component. Scroll lazy content into view and wait for its rendered state before measuring or interacting.
- Compare coordinates in the same reference frame. Check that screenshots contain the whole target and rendered text does not overlap or overflow.
- Check desktop and small-screen layouts in both themes with representative text. A small fixture does not prove longer real text fits.
- Exercise loaded, absent and empty data separately. Verify the expected degraded state and that unaffected content still works.
- Read page errors, console errors and failed requests. Exempt only failures deliberately caused by the case, matched to the affected request.

## Svelte

- Verify hydration through an enabled, working control; populated HTML alone does not prove the client started.
- Test no-script rendering separately. Scoped component CSS can override unscoped rules inside `<noscript>`; keep layout on a child when the wrapper's visibility is controlled there.

## See also

- [../../concepts/design-system.md](../../concepts/design-system.md) - visual and interaction requirements.
- [gates-and-builds.md](gates-and-builds.md) - selecting and serving the correct build.
- [../agent-notes.md](../agent-notes.md) - related command checks.
