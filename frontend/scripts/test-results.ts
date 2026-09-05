import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';

export type TestCounts = { passed: number; failed: number; skipped: number };

export function requireExecuted(counts: TestCounts): TestCounts {
	if (![counts?.passed, counts?.failed, counts?.skipped].every((count) => Number.isInteger(count) && count >= 0)) {
		throw new Error('The test report contains invalid counts.');
	}
	if (counts.passed + counts.failed === 0) throw new Error('No tests executed; collection or all-skipped output is not a pass.');
	if (counts.failed !== 0) throw new Error(`${counts.failed} tests failed in the test report.`);
	return counts;
}

export function playwrightCounts(file: string): TestCounts {
	const report = JSON.parse(readFileSync(file, 'utf8')) as {
		stats?: { expected: number; unexpected: number; flaky: number; skipped: number };
		errors?: unknown[];
	};
	if (!report.stats || report.errors?.length) throw new Error('Playwright did not produce a complete successful report.');
	return requireExecuted({ passed: report.stats.expected, failed: report.stats.unexpected + report.stats.flaky,
		skipped: report.stats.skipped });
}

export function pytestCounts(python: string, file: string, env: NodeJS.ProcessEnv): TestCounts {
	const source = [
		'import json, sys, xml.etree.ElementTree as ET',
		'cases = list(ET.parse(sys.argv[1]).iter("testcase"))',
		'counts = {"passed": 0, "failed": 0, "skipped": 0}',
		'for case in cases:',
		'    status = "skipped" if case.find("skipped") is not None else "failed" if case.find("failure") is not None or case.find("error") is not None else "passed"',
		'    counts[status] += 1',
		'print(json.dumps(counts))'
	].join('\n');
	const output = execFileSync(python, ['-c', source, file], { env, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] });
	return requireExecuted(JSON.parse(output) as TestCounts);
}
