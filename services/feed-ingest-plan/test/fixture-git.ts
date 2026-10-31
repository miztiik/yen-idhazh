/** Run Git only inside a test's generated repository. */
export async function fixtureGit(directory: string, args: string[], environment: Record<string, string> = {}) {
  const env: Record<string, string | undefined> = { ...Bun.env, ...environment };
  delete env.GIT_INDEX_FILE;
  delete env.GIT_DIR;
  delete env.GIT_WORK_TREE;
  Object.assign(env, {
    GIT_AUTHOR_NAME: "Fixture", GIT_AUTHOR_EMAIL: "fixture@example.test",
    GIT_COMMITTER_NAME: "Fixture", GIT_COMMITTER_EMAIL: "fixture@example.test",
  });
  const child = Bun.spawn(["git", ...args], { cwd: directory, env, stdout: "pipe", stderr: "pipe" });
  const [output, errors, code] = await Promise.all([
    new Response(child.stdout).text(), new Response(child.stderr).text(), child.exited,
  ]);
  if (code !== 0) throw new Error(`Generated fixture Git ${args[0]} failed: ${errors}`);
  return output.trim();
}
