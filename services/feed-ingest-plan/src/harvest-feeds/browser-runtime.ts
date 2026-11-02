/** Own a lazy sandboxed Chromium process and disposable execution contexts. */
import { chromium } from "playwright";
import type { Browser, BrowserContext } from "playwright";
import type { FeedIngestConfig } from "@idhazh/common-contracts";
import { installBrowserRequestGate } from "./browser-request-gate";
import type { BrowserRequestPolicy } from "./browser-request-gate";

// Mandatory Chromium control: target pausing does not stop a SharedWorker's initial script download.
const DISABLE_UNGATED_SHARED_WORKERS = "--disable-shared-workers";

function browserEnvironment(): Record<string, string> {
  const environment: Record<string, string> = {};
  for (const name of ["PATH", "HOME", "USERPROFILE", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "TMPDIR", "LANG", "LC_ALL"]) {
    if (process.env[name] !== undefined) environment[name] = process.env[name];
  }
  return environment;
}

export function createBrowserRuntime(config: FeedIngestConfig["harvest"]["browser"]) {
  let starting: Promise<{ browser: Browser; session: Awaited<ReturnType<Browser["newBrowserCDPSession"]>>;
    gate: Awaited<ReturnType<typeof installBrowserRequestGate>> }> | undefined;
  let closed = false;
  let creation = Promise.resolve();
  const contexts = new Set<BrowserContext>();
  async function start() {
    if (closed) throw new Error("Source browser runtime is closed");
    starting ??= (async () => {
      const browser = await chromium.launch({
        headless: config.headless, chromiumSandbox: true, env: browserEnvironment(),
        args: [DISABLE_UNGATED_SHARED_WORKERS],
        timeout: config.document_timeout_ms,
      });
      try {
        const session = await browser.newBrowserCDPSession();
        const gate = await installBrowserRequestGate(session);
        return { browser, session, gate };
      } catch (error) {
        await browser.close();
        throw error;
      }
    })();
    return starting;
  }
  return {
    async context(policy: BrowserRequestPolicy, headers: Record<string, string>) {
      const runtime = await start();
      let release!: () => void;
      const previous = creation;
      creation = new Promise<void>(resolve => { release = resolve; });
      await previous;
      try {
        if (closed) throw new Error("Source browser runtime is closed");
        const before = await runtime.session.send("Target.getBrowserContexts");
        const context = await runtime.browser.newContext({
          acceptDownloads: false, serviceWorkers: "block", extraHTTPHeaders: headers,
        });
        contexts.add(context);
        try {
          const after = await runtime.session.send("Target.getBrowserContexts");
          const ids = after.browserContextIds.filter(id => !before.browserContextIds.includes(id));
          if (ids.length !== 1) throw new Error("Could not establish exclusive source browser context ownership");
          const id = ids[0]!;
          runtime.gate.register(id, policy);
          await context.routeWebSocket("**/*", socket => socket.close());
          return {
            context,
            async page(pagePolicy: BrowserRequestPolicy = policy) {
              const page = await context.newPage();
              await runtime.gate.preparePage(context, page, pagePolicy);
              return page;
            },
            async close() {
              try { await context.close(); }
              finally { contexts.delete(context); runtime.gate.unregister(id); }
            },
          };
        } catch (error) {
          await context.close();
          contexts.delete(context);
          throw error;
        }
      } finally { release(); }
    },
    async close() {
      closed = true;
      await creation;
      const failures = await Promise.allSettled([...contexts].map(context => context.close()));
      contexts.clear();
      if (starting) {
        const runtime = await starting;
        try { await runtime.browser.close(); }
        finally { runtime.gate.close(); }
      }
      const errors = failures.flatMap(result => result.status === "rejected" ? [result.reason] : []);
      if (errors.length) throw new AggregateError(errors, "Source browser context cleanup failed");
    },
  };
}
export type BrowserRuntime = ReturnType<typeof createBrowserRuntime>;
