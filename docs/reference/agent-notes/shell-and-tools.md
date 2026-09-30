# Agent Notes - Shell and Tools

**Last Updated**: 2026-09-30

Checks before trusting command output or an editor operation. Keep instructions portable; omit machine configuration and session transcripts.

## PowerShell

- Confirm the working directory before running a command. Stop if changing directories fails; do not continue in the previous checkout.
- Quote paths and use `-LiteralPath` when a path can contain wildcard characters. Pass absolute paths to .NET file APIs, which do not follow PowerShell's location.
- Verify that a native command exists, then capture its exit code immediately. For `Start-Process`, read the returned process's `ExitCode`; `$LASTEXITCODE` belongs to the last directly invoked native command.
- Keep diagnostic output out of a function's returned value. Wrap pipeline results in `@(...)` when they must remain a collection with zero or one member.
- Quote shell-sensitive arguments as complete values. Do not assume native programs receive PowerShell arrays, globs or revision expressions unchanged.

## The terminal tool itself

- Use the command's completion status. An empty log proves neither success nor failure; before retrying, check whether the first command is still active.
- Keep output paths unique per run. Wait for commands you started and read their results; do not leave an unattended check running after reporting completion.
- Never queue a destructive command against files another task uses. An interrupted command may have completed some work; inspect its result before repeating it.
- For cross-plan dependencies, run `python backend/utilities/plan_status.py --no-gh` without `--plan`. The filter narrows the dependency index as well as the report, so an external dependency can appear missing. Omit `--no-gh` when remote pull-request checks are needed.

## The editor's own file and search tools

- Verify which checkout a search or edit tool targets. For a worktree outside the open workspace, use explicit paths or a search rooted in that worktree.
- Confirm a claimed absence with a direct search or file read before deleting or redoing work. When tool results disagree, check the current file bytes and Git diff.
- Edit one file sequentially. Create an input before starting its reader, inspect structural diffs, and check for unintended files after a move.

## Nested subagents

- Check the [host's delegation requirements](https://code.visualstudio.com/docs/agents/run/subagents#_nested-subagents) before relying on nested calls. Verify required tools are available; report a blocked consultation to the coordinating agent.

## The Python environment

- Use an interpreter supported by the project's declared version range. Verify imports and package paths in the intended checkout before running checks.
- Isolate environment changes to the task. Do not rebuild or change a shared environment while another task uses it.

## Downloads

- Pin the source revision and verify downloaded bytes against the published file checksum. Do not treat an HTTP ETag as a SHA-256 checksum.

## See also

- [../../how-to/run-the-gates.md](../../how-to/run-the-gates.md) - supported setup and commands.
- [git-and-github.md](git-and-github.md) - repository operations.
- [../agent-notes.md](../agent-notes.md) - related command checks.
