# Agent Notes - Shell and Tools

**Last Updated**: 2026-10-04

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
- In a shared terminal, start each command with a unique tag and an explicit working directory. A returned transcript can include older commands; match the tag, exit status and output file before using it as evidence.
- If a long pasted command has no confirmed result, inspect its effects first. Put a still-needed sequence in a script and invoke it with a short command; do not paste the same writes again on the assumption that none ran.
- For a non-interactive `gh` watch, redirect output to a unique file. An alternate-screen display alone gives no usable job result; verify the final job states before reporting success.
- Keep printed output short: write a long result to a file and read the file. A terminal that replays its old scrollback can return thousands of lines and stall the session.
- For cross-plan dependencies, pass each needed document as `--plan TODO/<file>.md` to `python backend/utilities/plan_status.py --no-gh`. The named set supplies both the dependency index and the report. A dependency in an unnamed plan appears missing. Omit `--no-gh` when remote pull-request checks are needed.

## The editor's own file and search tools

- Verify which checkout a search or edit tool targets. For a worktree outside the open workspace, use explicit paths or a search rooted in that worktree.
- Confirm a claimed absence with a direct search or file read before deleting or redoing work. When tool results disagree, check the current file bytes and Git diff.
- Edit one file sequentially. Create an input before starting its reader, inspect structural diffs, and check for unintended files after a move.
- In a worktree outside the open workspace, the file reader can return a copy from before the last edit. Read such a file through the terminal before an edit depends on its text.
- **A new file reads as LF text and is CRLF on disk.** On 2026-10-04, on a Windows machine, the agent's file-creation tools wrote Windows line endings into new files. Git normalises only at `git add`, too late for a test that reads the working file. Check the bytes and convert before the first test:
  ```powershell
  python -c "import sys;p=sys.argv[1];b=open(p,'rb').read();print(b.count(b'\r\n'));open(p,'wb').write(b.replace(b'\r\n',b'\n'))" <path>
  ```

## Nested subagents

- Check the [host's delegation requirements](https://code.visualstudio.com/docs/agents/run/subagents#_nested-subagents) before relying on nested calls. Verify required tools are available; report a blocked consultation to the coordinating agent.
- Give a long review subagent a tool-call budget and a findings file it rewrites as it works. Its report exists only in its final message, so an interrupted turn loses everything it found.

## The Python environment

- Use an interpreter supported by the project's declared version range. Verify imports and package paths in the intended checkout before running checks.
- Isolate environment changes to the task. Do not rebuild or change a shared environment while another task uses it.

## Downloads

- Pin the source revision and verify downloaded bytes against the published file checksum. Do not treat an HTTP ETag as a SHA-256 checksum.

## See also

- [../../how-to/run-the-gates.md](../../how-to/run-the-gates.md) - supported setup and commands.
- [git-and-github.md](git-and-github.md) - repository operations.
- [../agent-notes.md](../agent-notes.md) - related command checks.
