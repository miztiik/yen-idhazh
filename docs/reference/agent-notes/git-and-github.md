# Agent Notes - Git and GitHub

**Last Updated**: 2026-10-09

Checks for agents using Git and GitHub. Follow the
[PR workflow](../../how-to/ship-a-pr.md) and [git rules](../../../CLAUDE.md#8-git-hygiene).

## Worktrees

- Confirm the checkout, branch and changed paths before staging. Do not alter another worker's checkout.
- Before removing a worktree, verify its pull request is merged, its remote branch is gone, and its tree is clean. Keep its branch attached so cleanup can identify it.
- Do not use `git branch --merged` as proof after a squash merge: the original branch tip is not an ancestor of `main`.
- A failed removal can delete tracked files before a locked generated executable stops it. Inspect both `git worktree list --porcelain` and the remaining directory before retrying. Leave the residue when its process cannot safely be stopped; do not force deletion or terminate another task.
- **A merge succeeds but cleanup reports `Filename too long`.** The merge and local worktree removal are separate operations. Confirm the pull request's `state` and `mergeCommit` with `gh pr view` before retrying anything. Inspect the remaining worktree and preserve it if cleanup cannot safely finish; a cleanup error is not proof that the merge failed.
- **`gh pr merge --delete-branch` also removes the worktree that holds the merged branch** (seen twice on 2026-10-06 with gh 2.101.0). Afterwards the folder is gone and `git worktree list` does not name it. A later `cd` into that folder fails, and the next command then runs in the shell's own checkout. Copy out anything you need first, and do not chain a `cd` into that worktree after the merge. Run from a folder that is not a git checkout, with `--repo owner/name`, the same command merged and deleted the remote branch and left the worktree and its local branch in place (seen twice on 2026-10-05 with gh 2.101.0). Use that form when a worktree must outlive its merge, such as one an app session works in.

## The moving base

- Compare fixed commit ids. Shared worktrees can update `origin/main` between commands.
- Review `git diff --name-only <base>...HEAD` before publishing; a clean checkout does not prove the branch contains only your changes.
- Resolve conflicts from both changes' intent. Do not take `--ours` or `--theirs` for every file without checking what it discards.
- A documentation branch based on a feature branch can retain its old code after that feature is squash-merged. Merge current main, keep its tested code and verify that the final diff changes only the intended documents.

## Local Git fixtures

- Address a generated bare repository with `git --git-dir <path>`, not by
  changing into it and relying on discovery. `safe.bareRepository=explicit`
  refuses implicit discovery even when the test created the repository.
  Exercise both `explicit` and `all` with subprocess-scoped settings; do not
  change the machine's Git policy to make a test pass. Apply the explicit
  address to tree comparisons as well as history inspection.

## The `gh` CLI

- Confirm the repository and authenticated account before a write. Never print or export tokens to check an account.
- **A push still uses the wrong account after `GH_TOKEN` is removed.** The tell
  is a 403 naming a different account from `gh auth status`. The app can inject
  URL-specific credential helpers through `GIT_CONFIG_PARAMETERS`; a generic
  helper does not replace them. After confirming the keyring account has access,
  use a fresh shell for this push only; leave global credentials unchanged.
  A push refused for a missing `workflow` scope (seen 2026-10-04), not a 403, is the same credential fault; the reset below fixes it.
  ```powershell
  if (Test-Path Env:GH_TOKEN) { Remove-Item Env:GH_TOKEN }
  if (Test-Path Env:GIT_CONFIG_PARAMETERS) { Remove-Item Env:GIT_CONFIG_PARAMETERS }
  git -c credential.helper= -c credential.helper='!gh auth git-credential' push
  ```
- After an interrupted push or merge, verify remote state before retrying: `git ls-remote` for a branch; `gh pr view <number> --repo <owner/repo> --json state,mergeCommit` for a pull request.
- Treat `UNKNOWN` and missing checks as unresolved, not success. Check mergeability and workflow triggers before waiting.
- When the user changes a merge precondition, update the pending command before executing it. Record the authorized exception without extending it, retain the other checks, and use `--match-head-commit` to bind the merge to the verified head.

**A push returns 403 after adding the correct helper, but Git used an earlier helper.**
`git -c credential.helper=...` appends to the existing helper list.
The tell is that `gh api user --jq '.login'` names the intended account while
the push error names another, and `git config --get-all credential.helper`
lists an earlier helper. Clear the list for this command before adding `gh`:
```powershell
if (Test-Path Env:GH_TOKEN) { Remove-Item Env:GH_TOKEN }
if (Test-Path Env:GITHUB_TOKEN) { Remove-Item Env:GITHUB_TOKEN }
git -c credential.helper= -c credential.helper='!gh auth git-credential' push
```
Confirm the keyring account first; do not change shared global authentication.

## Reading a run

- Match checks to the candidate commit and inspect individual jobs. Skipped jobs are not passes, even when the run summary is green.
- Check job status, log availability and verbosity before treating missing output as proof that something did not run.
- A GitHub Actions re-run keeps the original commit and ref. Start a new run on the target branch to verify a merged fix, then check its `headSha`. Passing PR checks alone do not verify the next production run.
- **One CI run of the browser step reads as a speed change; it is noise.** On
  2026-10-03, three `ubuntu-latest` runs of nearly the same suite (1,425 to
  1,445 tests) took 5.0, 6.4 and 7.5 minutes. So one reading cannot show a
  change smaller than about 2.5 minutes. Judge a cut by what it removed - tests,
  page loads, fixed waits - or by paired runs on one commit.
- An active writer can publish removed files from its old checkout after a merge. Check the retired paths after that run completes. Permission to merge during a run does not authorize cancelling it.

## See also

- [../../how-to/run-the-gates.md](../../how-to/run-the-gates.md) - required checks.
- [../documentation-structure.md](../documentation-structure.md) - keep current rules and reasons, not incident records or developer-machine configuration.
- [../agent-notes.md](../agent-notes.md) - related command checks.
