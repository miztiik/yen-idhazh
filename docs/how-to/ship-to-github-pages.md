# How To Ship To GitHub Pages

**Last Updated**: 2026-08-20

The runbook for deploying a static site to GitHub Pages, and for changing anything that has to keep working under a project base path: routing, asset URLs, deep links, and the deployment workflow itself.

This runbook is written to be **domain-neutral**, so it can be copied between projects unchanged (CLAUDE.md section 5). It states the constraints GitHub Pages imposes and the checks that catch each one; the build tool, framework and command names are project-specific and are named in the "Project bindings" section at the end.

## When to run

- Changing routing, internal links, or any URL that must resolve in production.
- Changing the deployment workflow, the published directory, or the build's base-path handling.
- Adding a file that must be reachable at a stable published URL (a data payload, a manifest, a feed).
- Any first deploy.

## The one rule that causes most failures

**A project page is served from `/<repo>/`, not from `/`.** Every internal link, asset reference and fetched path must resolve under that prefix. A path that starts with `/` points at the *user* page root, escapes the project, and 404s - while working perfectly in local development, where the site is usually served from `/`.

So:

- Set the build's base path from a deploy-time variable rather than hardcoding it, so a local build and a deploy build differ only in that variable.
- Compute runtime paths from the framework's base-URL primitive, never by string-concatenating a leading `/`.
- Persisted paths, logs, manifests and doc cross-links use relative POSIX paths (CLAUDE.md section 2).
- Never navigate to a literal `/` from an in-page control. That leaves the project.

## Deep links and the fallback

GitHub Pages serves static files. A request for a path with no corresponding file returns the repository's `404.html`.

- If the site is multi-page (one real file per route), deep links work natively and no fallback is needed.
- If the site routes on the client, the published `404.html` must be a copy of the entry document so a deep link boots the app.

Either way, GitHub Pages may return an HTTP 404 *status* alongside the fallback body. **A smoke check must inspect the body, not just the status code**, or it will report a working deep link as broken.

## Deployment shape

Prefer the first-party Pages deployment path - build in a job, upload the built directory as a Pages artifact, deploy it in a dependent job with the Pages environment - over committing built output to a branch. It keeps built artifacts out of history and makes the deployment atomic.

Two workflow-level things to get right:

- **Permissions**: the deploy job needs `pages: write` and `id-token: write`. Grant them on the job, not the whole workflow.
- **Concurrency**: a single Pages concurrency group so two runs cannot race a deploy.

The published directory is a build output and is gitignored. What is committed is the source and any data payload the site renders.

## Caching and staleness

GitHub Pages caches aggressively at the edge. The entry document is the file most likely to be served stale after a deploy.

- Let the build content-hash asset filenames so a changed asset is a changed URL.
- Do not content-hash a data payload that is fetched by a stable path; version it inside the payload instead, so the site can tell what it got.
- After a deploy, verify against a cache-busted request before concluding a change did not ship.

## Validation

Run in order; each step catches a different failure:

1. **Build in deploy mode** - with the production base path set, not the local default.
2. **Inspect the built entry document** for the base prefix in its asset URLs. This catches the leading-slash bug before deployment rather than after.
3. **Confirm the fallback**, if the site routes on the client: the published `404.html` matches the entry document.
4. **Deploy, then smoke the live URL**: the entry page, one deep link (inspecting the body), and one fetched data payload.
5. **Read the browser console**: zero errors, zero 404s (CLAUDE.md section 12).
6. **Confirm the page renders with its data payload absent or empty.** This is a normal state, not an error state, and it is the check most often skipped.

## Common failures

| Symptom | Cause |
| --- | --- |
| Works locally, blank in production | Asset URLs built with a leading `/` instead of the base path. |
| Entry page works, deep link 404s | No `404.html` fallback for a client-routed site. |
| Deep link "fails" a smoke check but works in a browser | The check asserted on the HTTP status instead of the body. |
| Deploy succeeded, old content served | Edge cache on the entry document; re-check cache-busted. |
| Data payload 404s in production only | Path built root-absolute, or the payload is not inside the published directory. |
| Deploy job fails on permissions | Missing `pages: write` / `id-token: write` on the deploy job. |

## Project bindings

Record the project's specifics here the first time you deploy, so the rest of this document stays neutral:

- Build command and deploy-mode variable: _to fill_
- Published directory: _to fill_
- Routing mode (multi-page or client-routed): _to fill_
- Deploy workflow file: _to fill_
- Live URL: _to fill_

## See also

- [ship-a-pr.md](ship-a-pr.md) - the PR lifecycle this deployment follows.
- [../concepts/ui-shell.md](../concepts/ui-shell.md) - the published surfaces and their required states.
- [../../CLAUDE.md](../../CLAUDE.md) - section 2 (path rules), section 12 (published-surface verification).
