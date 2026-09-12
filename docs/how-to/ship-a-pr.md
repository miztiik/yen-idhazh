# How to ship a PR

**Last Updated**: 2026-09-11

The end-to-end runbook for taking a worker branch from "ready to commit" to "merged + cleaned up". Procedural counterpart to [CLAUDE.md](../../CLAUDE.md) section 8 (Git Hygiene) + section 9 (Definition of Done) + section 12 (published-surface verification).

This runbook is written to be **domain-neutral and stack-agnostic**, so it can be copied between projects unchanged (CLAUDE.md section 5). It cites the contract by section number rather than restating a project-specific rule, and it names gate *categories* rather than gate commands. Fill the commands in per project.

## When to run

For any change that goes through a pull request. Not every change does - one that cannot break a reader, a contract or a published page can go to the trunk directly, and the same gates still apply to it there. Scale the steps to the change: a one-line typo fix needs a commit, a push, and the checks its own paths select.

## Inputs

- A correction-level assessment per [CLAUDE.md](../../CLAUDE.md) section 6 (Level 0 / 1 / 2 / 3 / 4 / 5). Level 5 stops here for design consultation.
- Branch name in the form `<type>/<scope>-<slug>` (e.g. `feat/<scope>-<slug>`, `chore/<scope>-<slug>`, `docs/<scope>-<slug>`).

## Pre-flight

### Status check

```powershell
git status --porcelain; git branch --show-current
```

Confirm a clean working tree (or that the dirty paths are yours). Confirm the branch you intend to commit on.

### Branching

Start every code change in a dedicated worktree and named branch from the
fetched `origin/main`. Keep the shared main checkout free of implementation
edits. Check `git worktree list` before choosing the new directory:

```powershell
git fetch origin main
git worktree list
git worktree add -b <type>/<scope>-<slug> ../<worktree-name> origin/main
Set-Location -LiteralPath ../<worktree-name>
```

If work already exists in the shared checkout, preserve and verify its exact
files before transferring it. Do not overwrite another agent's changes while
making the transfer. Commit and validate in the dedicated worktree, merge via
the PR, then fast-forward the clean main checkout and remove only your worktree.

## Commit

One commit where the work is one change. Stage explicit paths only:

```powershell
git add <named paths>
git status --short # Verify EVERY named path shows M / A / D / R in column 1.
 # Any ' M' (space-M) entry means the path is NOT staged.
git commit -F .tmp_commit_msg.txt # or: git commit -m "<single-line message>"
```

The `git status --short` verification protects against the staged-then-silently-unstaged bug (a path can show `MM` if it was staged and then edited again; if you commit without re-`git add`, the second edit ships invisibly missing).

If you author the commit message in a scratch file with PowerShell, prefer `[System.IO.File]::WriteAllText($path, $content, [System.Text.UTF8Encoding]::new($false))` over `Set-Content -Encoding utf8` - the latter inserts a UTF-8 BOM that `git commit -F` treats as content.

### Push + create PR

```powershell
git push -u origin <branch>
gh pr create --base main --head <branch> --title "<title>" --body-file .tmp_pr_body.md
```

Capture the PR number from the URL it prints; the merge command below needs it.

**A change does not cite its own pull request number.** A number allocated after the branch is written costs a second commit and a second round of checks for about five lines of churn. Name the change by what it did - the behaviour, the file, the date - which is what somebody searching the history has to go on anyway. Where a record genuinely needs the number, read it from the merge rather than writing it into the diff.

Do not record an architecture decision as a routine stamp either. Update the living doc that owns the current shape, in this same change. When the change actively explored and rejected a real architecture alternative with non-trivial reversal cost, add a `## Design rationale` / `## Rejected alternatives` section to that same living doc - there is no `docs/architecture/decisions/` directory.

## The Definition-of-Done gates

Run the gates appropriate to the surface before merge. Reference: [CLAUDE.md](../../CLAUDE.md) section 9 (DoD) + section 12 (published-surface verification) + section 13 (Test Coverage Policy).

The gate *commands* are project-specific (build tool, test runner, type-checker, linter). The gate *categories* are stable across projects:

1. **Schema / contract validation** - every persisted shape validates against its schema, and any generated artifact regenerates byte-identical to what is committed (the drift gate).
2. **Unit + contract tests** - per CLAUDE.md section 13. Real fixtures, no mocks.
3. **Integration + end-to-end tests** - when the change composes two or more units, or touches a surface a user sees.
4. **Lint + type-check** - zero-warning policy.
5. **Published-surface smoke** - per CLAUDE.md section 12, when the change touches anything a user renders.

Record the project's actual commands under each category the first time you run them.

## Merge

Merge is serialized even when work dispatch is parallel. Before each merge, confirm the required gates are green. Update the branch only when something asks for it - a conflict, or a gate that went red because of a change on the target branch rather than yours. Never merge a red branch.

**When the target branch moves under an open PR, bring it in with a merge.** A merge adds those commits to your branch and rewrites nothing you already pushed, so the update is an ordinary push with nothing to force over:

```powershell
git fetch origin main
git merge origin/main
git push
```

**Do not rebase a branch you have already pushed and force the result.** A rebase gives every commit on the branch a new identity, so the push has to overwrite what the remote already holds - which [CLAUDE.md](../../CLAUDE.md) section 8 rules out. The merge above ends in the same place and needs no exception to get there.

**Update the branch when something asks for it, not because it is behind.** A conflict, a gate that went red because of a change on the target branch rather than yours, or a reviewer asking are each a reason to merge. A branch that is merely behind, conflict-free and green is not - a squash merge resolves against the target branch as it stands at merge time, so being behind costs nothing on its own.

The cost, named rather than hidden: one extra merge commit on the branch. The squash collapses it with everything else, so it never reaches the target branch's history.

```powershell
gh pr merge NNN --squash --delete-branch
```

The branch squashes to one entry on `main`.

**`--auto` queues the merge behind the gates instead of behind a person, and it needs more than the repo setting.** Auto-merge queues behind something that *blocks* the merge, so with no required status check there is nothing to queue behind: `gh pr merge <n> --squash --delete-branch --auto` exits 0 and does nothing. Check `autoMergeRequest` rather than the exit code before believing it worked.

```powershell
gh pr merge NNN --squash --delete-branch --auto
gh api graphql -f query='{repository(owner:"OWNER",name:"REPO"){pullRequest(number:NNN){autoMergeRequest{enabledAt}}}}'
```

A `null` there means the plain form above is still the merge.

## Post-merge cleanup

This is the loop that is otherwise implicit. Run every step in order.

### Step 1 - verify the merge actually happened

```powershell
gh pr view NNN --json state,mergedAt,mergeCommit
```

`state` MUST be `MERGED`. If `gh pr merge` printed a cosmetic error during merge, the server-side merge usually succeeded anyway - this command confirms.

### Step 2 - delete the remote branch if gh skipped it

If `gh pr merge` cosmetic-errored, its post-merge git steps were skipped, including the remote-branch delete:

```powershell
git push origin --delete <branch>
```

Expected output: `[deleted]`. If `gh`'s `--delete-branch` ran successfully, this returns `error: unable to delete '<branch>': remote ref does not exist` - which is the GOOD outcome (already deleted).

### Step 3 - fetch + sync your view of origin/main

```powershell
git fetch origin main
git log --oneline origin/main -1
```

Confirms the new `main` HEAD matches the merge commit you just landed.

### Step 4 - prune stale local branches

After several merges the local repo accumulates branches whose remote-tracking ref is `: gone`. Prune in bulk, skipping the current branch (which `git branch -vv` prefixes with `* `):

```powershell
git fetch --prune
git branch -vv | Select-String ': gone\]' | ForEach-Object {
 $tokens = ($_.Line.TrimStart('*',' ').Trim() -split '\s+')
 $branchName = $tokens[0]
 if ($branchName -and -not ($branchName -match '^(main|HEAD)$')) {
 git branch -D $branchName
 }
}
```

Use `git branch -D` (force), not `-d` (merged-only), because squash-merged branches do not look "merged" to git even though they are. The `: gone` marker is the safe signal - it means the upstream was deleted (only happens after the PR merges).

Do NOT prune branches without a `: gone` marker; those have live upstreams and may be parallel work-in-progress.

### Step 5 - clean up tmp files

```powershell
Remove-Item .tmp_*.txt, .tmp_*.md, .tmp_*.log -ErrorAction SilentlyContinue
```

The `.tmp_*` pattern is the convention for ephemeral PR-authoring files. Add `.tmp_*` to `.gitignore` once it exists.

### Step 6 - a finding with no home

Normally there is nothing to do here, because the change already updated the page that owns what it changed. If it taught you something durable that no page owns, [distill-a-plan.md](distill-a-plan.md) says where it goes.

## See also

- [CLAUDE.md](../../CLAUDE.md) section 8 (Git Hygiene), section 9 (Definition of Done), section 12 (UI Verification), section 13 (Test Coverage Policy)
- [distill-a-plan.md](distill-a-plan.md) - where a finding goes when no page owns it yet
- [../reference/documentation-structure.md](../reference/documentation-structure.md) - which doc tier the distilled content belongs in
