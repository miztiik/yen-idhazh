# Agent Notes - Git and GitHub

**Last Updated**: 2026-09-29

Checks for agents using Git and GitHub. Follow the
[PR workflow](../../how-to/ship-a-pr.md) and [git rules](../../../CLAUDE.md#8-git-hygiene).

## Worktrees

- Confirm the checkout, branch and changed paths before staging. Do not alter another worker's checkout.
- Before removing a worktree, verify its pull request is merged, its remote branch is gone, and its tree is clean. Keep its branch attached so cleanup can identify it.
- Do not use `git branch --merged` as proof after a squash merge: the original branch tip is not an ancestor of `main`.

## The moving base

- Compare fixed commit ids. Shared worktrees can update `origin/main` between commands.
- Review `git diff --name-only <base>...HEAD` before publishing; a clean checkout does not prove the branch contains only your changes.
- Resolve conflicts from both changes' intent. Do not take `--ours` or `--theirs` for every file without checking what it discards.

## The `gh` CLI

- Confirm the repository and authenticated account before a write. Never print or export tokens to check an account.
- After an interrupted push or merge, verify remote state before retrying: `git ls-remote` for a branch; `gh pr view <number> --repo <owner/repo> --json state,mergeCommit` for a pull request.
- Treat `UNKNOWN` and missing checks as unresolved, not success. Check mergeability and workflow triggers before waiting.

## Reading a run

- Match checks to the candidate commit and inspect individual jobs. Skipped jobs are not passes, even when the run summary is green.
- Check job status, log availability and verbosity before treating missing output as proof that something did not run.

## See also

- [../../how-to/run-the-gates.md](../../how-to/run-the-gates.md) - required checks.
- [../documentation-structure.md](../documentation-structure.md) - keep current rules and reasons, not incident records or developer-machine configuration.
- [../agent-notes.md](../agent-notes.md) - related command checks.
