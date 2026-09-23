# What the site weighs, and when it stops fitting

**Last Updated**: 2026-09-23

GitHub Pages refuses a site over 1 GB. This page holds the instrument that
measures against that: which tree it measures, why a page-weight failure and a
broken day are two different failures with two different places in the
publishing order, and why the answer it prints is a runway in published days
rather than a level in megabytes. What the migrations bought against that
ceiling is
[the-served-day-and-the-documents-that-stopped-being-written.md](the-served-day-and-the-documents-that-stopped-being-written.md);
what may be deleted is [retention.md](retention.md).

## The weight gate measures the built bundle, not the payload tree

The 1 GB cap is on `frontend/build/`, the directory the Pages deploy uploads -
not on `frontend/public/digest/`, which is what the pipeline writes. The two are
an order of magnitude apart and grow at different rates, so neither can stand in
for the other, and an alarm on the smaller one would have run every pipeline
run, cost real seconds and never warned anybody. **That is worse than no alarm,
because a green light is read as safety.**

**So the measurement runs where the site exists.** The bundle does not exist
while `assemble` runs, so `idhazh site-weight --site-tree build` is its own step
in every job that builds the site - `ci.yml`'s `site` job, `digest.yml`'s
`assemble` job, and `backfill.yml` - before the commit that publishes a day.

**The tree has no default**, because a default is how the old call came to name
the wrong one. The workflow names it at the call site, and a contract test reads
the path back off `pages.yml`'s own upload step.

**Two lines, and only one of them fails a build.** Over `retention.site_budget_mb`
the step prints a warning and passes; past `retention.pages_hard_cap_mb` it
fails. Failing at the budget would stop publishing while there was still room,
and a reader would lose a working site to a number we chose. Past the cap the
bytes cannot be published at all.

**The cap is a knob in one direction only.** It is a config field bounded
`le=1024`: an operator can name a smaller cap and the schema refuses a larger
one. Lowering it buys an earlier and louder failure while there is headroom to
act; no value buys more room, because the 1 GB is GitHub's. The console's site
band draws against the platform's 1 GB rather than the configured cap - it
reports the ceiling that exists, not the one this run chose to stop at.

**`site_bytes` on the run manifest is the committed payload tree**, which is
genuinely useful about repository growth. It now says which tree it holds, so
nobody reads it as the site ([../contracts/schemas.md](../contracts/schemas.md)).

**The deploy is not gated.** Every byte that reaches `main` passes through the
`assemble` job or through `ci.yml`, and both measure it before the push. Gating
the deploy would stop the deploy, leaving the reader on yesterday's digest until
somebody looked - the same trade the section below settles, the same way.

**`BASE_PATH` does not move what CI measures.** `pages.yml` builds with a
repository sub-path and `ci.yml` does not, so on paper they measure different
documents. The sub-path is a short repeated string and gzip charges almost
nothing for a repeat: the largest per-route move measured is under one percent,
on the smallest page, inside the spread between two plain builds of one tree.

## A bad day is stopped before the commit; the weight ratchet is not

Two failures with nothing in common used to be welded into one step before the commit that publishes, and only one of them is worth a day.

**An invalid payload is caught before the commit, and the build is not what catches it.** A reading document carries a seed and the browser fetches the rest, so no build opens the stories past the seed. `idhazh validate-days` opens all of them, against the committed shape the build reads and the served shape a browser fetches, and it runs immediately before `npm run build` in both publishing jobs. That day is broken, it must not publish, and both checks run before the commit. The guarantee's name is the part worth stating: **a broken day can no longer be merged**, and the publishing step is what keeps the pipeline's own pushes inside it - `ci.yml` never starts from a push the pipeline made ([frontend.md](frontend.md)).

**A weight failure is a number we wrote down ourselves.** `page_weight.ceilings_bytes` in `config/idhazh.json` says how heavy each named page's prerendered HTML may get. Past it the page still reads correctly - what grew is the document, not the meaning. So the gate runs after the commit, in `digest.yml` and in `backfill.yml` alike, and it names only `/404` and `/evals/`, which move when a person edits source and never when a run publishes ([../../how-to/run-the-gates.md](../../how-to/run-the-gates.md)).

**Leaving it before the commit was the alternative, and it was rejected on the trade rather than on the principle.** It buys something real: `main` stays green, and the ceiling is discussed before any reader sees the heavy page. It buys that by spending a published day and the runner budget that produced it (Guardrail #2) on a page nobody would have complained about. A digest that never arrives is the larger failure.

**It stays fatal, and that costs something.** The day publishes, then the `assemble` job goes red. A page-weight number crossed on a Tuesday leaves `main` red until somebody looks at it. That is the price of the trade and it is not hidden. The property the four deleted ceilings stood in for is asserted by `frontend/tests/payload-weight.spec.ts` with no number in it ([../../how-to/run-the-gates.md](../../how-to/run-the-gates.md#the-console-has-no-page-number)). A warning was rejected for the same reason a green light on a broken alarm was: nobody reads it.

**"At the next CI run" is not "at the next push", and the difference is a delay.** `ci.yml` triggers on every push to `main`, but the pipeline's own pushes never start it: GitHub does not begin a workflow from a push made with the job's `GITHUB_TOKEN`. So the red job the pipeline produces is the `assemble` job inside the digest run, and `main`'s own CI stays green until the next merge somebody pushes. **Read a red `site` job as a page that has been over its ceiling since some earlier publish**, not as something the merge in front of you did.

**The gate reads a build made after the last commit step.** A lost push is retried by rebuilding the day against origin's new tip, so a build made before the commit can describe a tree the retry has already replaced - and the gate would then weigh one tree's pages against another tree's records. The rebuild is `npm run build` alone, 17 s against a run of 164 to 184 min. `npm ci` is deliberately not repeated with it: the lockfile moves rarely and `frontend/src` moves several times a day, so a reinstall would delete `node_modules` every run to cover the rarer case, and `npm ci` has its own partial-extract failure mode.

**Re-running the failed job is not the repair, and it looks like one.** A re-run checks out the original commit, so it rebuilds the old source, compares it with the old record and passes - green for a tree that is no longer `main` ([../../reference/ci-environment.md](../../reference/ci-environment.md#platform-limits-that-shape-the-workflows)).

**`site-weight` did not move.** The 1 GB Pages cap is the platform's limit, not our record of our own bytes, and past it the deploy fails whatever we do - so refusing to publish is the honest answer there and it still runs before the commit.

## The size instrument reports a runway, not a level

A megabyte figure and a headroom figure are both levels. **Neither is a rate, so neither answers the only question anyone asks a size instrument: when does this stop working?** Three things were added and none of them fails a build.

**`by_directory` - the top-level children of `build/`.** One total cannot say whether the visuals grew or the telemetry did, so the day the total moves is the day somebody starts guessing. The split is asserted to sum exactly to the total, because a split that quietly loses bytes names the wrong directory on the one occasion it is used to decide what to cut.

**`bytes_per_published_item` - the unit that holds still.** A rate per day is not stable here: the day rate moves with the item mix, where the per-item figure holds. So the day rate is derived - per-item times `run.safety_ceiling_per_run`, the ceiling in force - rather than averaged over whichever days happen to be on disk. That is a worst-case day by construction, which is what a runway needs (Guardrail #10). The readings are in [../../reference/site-weight.md](../../reference/site-weight.md#days-to-the-1-gb-pages-ceiling).

**`days_to_alarm` and `days_to_cap` - the runway.** Headroom divided by that rate, in published days rather than calendar days. It is printed on every run, including the runs nowhere near either line, because the day the alarm fires is not the day anybody wanted to first learn the date.

**The count comes from the tree that was measured, and that is not a detail.** Items are read from the day payloads staged under `build/digest/`, never from `frontend/public/digest/` and never from a run manifest. Bytes and items have to come from one corpus, or the rate divides a numerator by somebody else's denominator - which is the shape of the defect the section above exists to refuse, one level down.

**It reports and it gates nothing new.** `npm run bundle-gate` already fails a build on a crossed per-route ceiling and `cap_breach` already fails one past the platform's. A third gate would be a third thing to keep green for coverage that exists.

**A runway from nothing raises rather than returning a comfortable number.** Zero published items divides into an infinite runway, and an infinite runway reads exactly like a healthy site. So the per-item property raises on an empty tree, the CLI checks before it asks, and a tree carrying no day payloads prints `runway: unknown` instead.

**The printed runway is a floor, not an estimate of the date.** The rate averages the whole tree, so it charges the on-device encoder and the JavaScript bundle - neither of which grows with a day - to every future item. `by_directory` is on the same output so a reader can take them out rather than read the floor as the answer.

## Why retention is the third lever and not the first

Retention was demoted after the byte arithmetic showed that encoding and the existing visual rule together move the ceiling from months to years. A policy that deletes a reader's archive to reclaim a fraction of a percent of the bytes would have been solving the wrong problem. What may be deleted, when, and what bounds every collection a run appends to is [retention.md](retention.md).

## Rejected alternatives

| Option | Why rejected |
| --- | --- |
| Measuring the site cap over `frontend/public/digest` | It is not the site. Measured 2026-08-27: 7,027,075 bytes against the built bundle's 128,064,853, eighteen times apart and growing at different rates, so neither can stand in for the other. |
| Deriving the site size from the payload tree with a calibrated multiplier | The ratio moved from 21x to 18x on one pull request. A multiplier nobody can re-measure per run is an unmeasured number justifying a design (Guardrail #10). |
| A gate that fails on one directory's share of the site | The cap is on the whole tree. One directory's share does not yield a date, and a second weight gate is a second thing to keep green beside `bundle-gate`, which already fails on a crossed page ceiling. |
| A day rate averaged over the days on disk | It moved by a factor of six across seven mature days measured 2026-08-29, because the item counts did. Bytes per published item over the same days held inside 23,066 to 26,538. |
| Failing the build at the 800 MB alarm point | It stops publishing about two weeks before it has to. A reader loses a working site to a budget that still had room; the cap is where refusing the bytes is the honest answer. |
| Measuring the site in the Pages deploy instead | The day is already committed by then, and undoing it is a revert. Gating before the push is what turns a broken site into a run that publishes nothing. |
| Leaving the page-weight gate before the commit | It keeps `main` green by spending a finished day and the two to three hours that built it, on a page that reads correctly and that no reader would have complained about. See [A bad day is stopped before the commit; the weight ratchet is not](#a-bad-day-is-stopped-before-the-commit-the-weight-ratchet-is-not). |
| Making the page-weight gate a warning instead of moving it | A warning that fires on every heavy publish is a line in a log nobody opens, and the ceiling then drifts with no date on it. Red after the day is published is read; amber before it is not. |
| A default value for `--site-tree` | A default is how the measurement came to name the wrong tree. The workflow names it, and a test reads it back off the deploy's own upload step. |
| Deleting text alongside images under one retention knob | Text is a fraction of a percent of the bytes. |

## See also

- [layout.md](layout.md) - the tree the pipeline writes, which is not the tree this measures.
- [the-served-day-and-the-documents-that-stopped-being-written.md](the-served-day-and-the-documents-that-stopped-being-written.md) - the two migrations that more than doubled the runway, and the date they bought.
- [retention.md](retention.md) - the third lever: what may be deleted and when.
- [console-site-size.md](console-site-size.md) - the operator panel this instrument feeds.
- [../../reference/site-weight.md](../../reference/site-weight.md#days-to-the-1-gb-pages-ceiling) - the readings themselves, and the units error that made them wrong until 2026-08-27.
- [../../how-to/run-the-gates.md](../../how-to/run-the-gates.md) - the page ceilings, the bundle gate, and what runs where.
- [../../reference/github-actions.md](../../reference/github-actions.md) - the jobs the measurement is a step in.
- [../../concepts/config/run-limits.md](../../concepts/config/run-limits.md) - the alarm point and the cap, and why one reports and one stops.
