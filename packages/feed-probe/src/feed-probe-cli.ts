/** Execute the standalone package CLI when invoked directly. */
import { runFeedProbeCli } from "./cli";

if (import.meta.main) {
  const exitCode = await runFeedProbeCli(process.argv.slice(2));
  process.exitCode = exitCode;
}
