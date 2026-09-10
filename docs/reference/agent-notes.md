# Agent Notes

**Last Updated**: 2026-09-10

Environment and tool quirks that make a command lie about its result in this
repository. Each entry is a trap that cost real time at least once: the false
result it shows, the cause, and the response.

This page exists so that execution craft has a home inside `docs/`. A lesson
kept only in an agent's private memory is invisible to the next person and to
the next agent (`CLAUDE.md` section 5).

**This is not a place for project knowledge.** A rule about how the pipeline
behaves, what a payload carries, or why a design was chosen belongs in the
living doc that owns it ([documentation-structure.md](documentation-structure.md)).
If an entry starts explaining the product, it has been filed wrong.

## Where an entry lives

The notes are split by **the command you are about to type**, not by the
subsystem the command belongs to. A `gh` call that reads a CI run is a GitHub
trap even when the run was a browser suite.

| Page | Commands it covers | Reach for it when |
| --- | --- | --- |
| [agent-notes/git-and-github.md](agent-notes/git-and-github.md) | `git`, `git worktree`, `gh` | You are branching, merging, cleaning up a worktree, or reading a CI run. |
| [agent-notes/shell-and-tools.md](agent-notes/shell-and-tools.md) | `pwsh`, Git Bash, the editor's own file and search tools, `pip`, `npm ci` | A command returned nothing, returned the wrong thing, or edited a file you were not in. |
| [agent-notes/gates-and-builds.md](agent-notes/gates-and-builds.md) | `test:changed`, `pytest`, `ruff`, `mypy`, the schema export, `npm run build`, the canary day | A gate is red, green or slow for a reason that is not your change. |
| [agent-notes/browser.md](agent-notes/browser.md) | Playwright, the integrated browser, the service worker, the Svelte components a spec drives | A page test fails on something the page does correctly by hand. |

No entry lives on this page. An entry written here is the first line of the file
this split removed.

## Adding an entry

Write it on the page whose command lies, in this shape, and no longer than
twelve lines including the command block:

1. A bold lead naming the FALSE RESULT - "reads as X, is actually Y".
2. One or two sentences of cause.
3. The command or snippet that gets the true answer.

Longer than twelve lines means it is two entries, or it is not a tool quirk.
Date an entry only where it can go stale - a tool version, upstream behaviour, a
workflow that may since have been fixed. A date on a permanent trap is noise.

## See also

- [../how-to/run-the-gates.md](../how-to/run-the-gates.md) - the commands these traps interfere with.
- [../how-to/ship-a-pr.md](../how-to/ship-a-pr.md) - the PR lifecycle the git and `gh` entries serve.
- [documentation-structure.md](documentation-structure.md) - the routing rule that sends a lesson here rather than into private memory.
- [../../CLAUDE.md](../../CLAUDE.md) - section 5 (Documentation Discipline).
