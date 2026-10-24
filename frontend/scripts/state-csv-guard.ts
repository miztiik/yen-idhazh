/** Does one supplied commit range add or change a CSV file under state/? */
import { spawnSync } from 'node:child_process';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

function git(root: string, args: string[], failure: string): string {
	const result = spawnSync('git', ['-C', root, ...args], {
		encoding: 'utf8', maxBuffer: 16 * 1024 * 1024, stdio: ['ignore', 'pipe', 'pipe']
	});
	if (result.error) throw new Error('State CSV check could not run Git.', { cause: result.error });
	if (result.status !== 0) throw new Error(failure);
	return result.stdout;
}

export function checkStateCsvRange(root: string, base: string, head: string, event = ''): string {
	// Git's push-event sentinel is not a commit; it means the branch had no old tip.
	const branchCreation = event === 'push' && /^0{40}$/.test(base);
	const baseCommit = base && !branchCreation
		? git(root, ['rev-parse', '--verify', '--end-of-options', `${base}^{commit}`],
			'State CSV check cannot resolve BASE as a commit.').trim()
		: '';
	const headCommit = head
		? git(root, ['rev-parse', '--verify', '--end-of-options', `${head}^{commit}`],
			'State CSV check cannot resolve HEAD as a commit.').trim()
		: '';
	if ((!base && !head) || (!base && event === 'workflow_dispatch') || branchCreation) {
		if (base && !head) throw new Error('State CSV check requires HEAD when BASE is supplied.');
		return 'State CSV check not run: no commit range was supplied. No whole-tree integrity certification.';
	}
	if (!baseCommit || !headCommit) {
		throw new Error('State CSV check requires both BASE and HEAD for a commit range.');
	}
	const ancestor = git(root, ['merge-base', baseCommit, headCommit],
		'State CSV check cannot find a merge base for BASE and HEAD.').trim();
	const paths = git(root, [
		'diff', '--name-only', '--no-renames', '--diff-filter=d', '-z', `${ancestor}...${headCommit}`
	], 'State CSV check cannot read the supplied commit range.').split('\0').filter(Boolean);
	// These case-sensitive names are the existing repository policy, not tunable file patterns.
	const forbidden = paths.filter((path) => path.startsWith('state/') && path.endsWith('.csv'));
	if (forbidden.length > 0) {
		throw new Error(`State CSV check rejected added or changed CSV files: ${forbidden.map((path) => JSON.stringify(path)).join(', ')}`);
	}
	return 'State CSV check passed for the supplied commit range; unchanged files were not checked.';
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
	try {
		console.log(checkStateCsvRange(process.cwd(), process.env.BASE ?? '', process.env.HEAD ?? '',
			process.env.EVENT ?? ''));
	} catch (error) {
		console.error(error instanceof Error ? error.message : String(error));
		process.exitCode = 1;
	}
}
