/** What runner label did the platform give this process? */
export function runnerName(environment: NodeJS.ProcessEnv): string | null {
  return environment.RUNNER_NAME?.trim() || null;
}
