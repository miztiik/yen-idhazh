/** Which host probe operation did the operator request? */
import { loadConfig } from "./config";
import { serveSamples } from "./api/server";
import { sampleHost } from "./probe/sample-host";

async function main(): Promise<void> {
  const args = Bun.argv.slice(2);
  if (args.length !== 1 || (args[0] !== "--sample" && args[0] !== "--serve")) {
    throw new Error("Usage: bun run src/index.ts --sample|--serve");
  }
  const config = await loadConfig();
  if (args[0] === "--sample") {
    console.log(JSON.stringify(await sampleHost(config)));
  } else {
    const server = serveSamples(config);
    console.error(JSON.stringify({ listening: server.url.toString() }));
  }
}

if (import.meta.main) {
  main().catch((error: unknown) => {
    console.error(JSON.stringify({ error: error instanceof Error ? error.message : String(error) }));
    process.exitCode = 1;
  });
}
