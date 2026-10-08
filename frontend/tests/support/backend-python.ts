/**
 * Which Python runs the backend when a spec needs a file only the backend writes.
 *
 * A runner installs the backend onto the interpreter on `PATH`, and the
 * documented local setup is a `.venv` at the repository root. `IDHAZH_PYTHON`
 * is the escape for a worktree borrowing another checkout's environment, which
 * is how several agents share one machine
 * ([docs/reference/agent-notes.md](../../../docs/reference/agent-notes.md)).
 */

import { existsSync } from 'node:fs';
import path from 'node:path';

/** The Python that runs the backend for a repository rooted at `repo`. */
export function backendPython(repo: string): string {
	const named = process.env.IDHAZH_PYTHON;
	if (named) return named;
	for (const candidate of [
		path.join(repo, '.venv', 'Scripts', 'python.exe'),
		path.join(repo, '.venv', 'bin', 'python')
	]) {
		if (existsSync(candidate)) return candidate;
	}
	return 'python';
}
