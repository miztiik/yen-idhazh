/** Pause Chromium child targets and their requests before website traffic can leave. */
import type { CDPSession, BrowserContext, Page } from "playwright";
import { BrowserNetworkError } from "./transport";

type Message = {
  id?: number; method?: string; params?: Record<string, unknown>;
  result?: Record<string, unknown>; error?: { message: string };
};
type ChildTarget = {
  sessionId: string; waitingForDebugger: boolean;
  targetInfo: { targetId: string; type: string; browserContextId?: string; openerId?: string };
};
export type BrowserRequestPolicy = {
  attach(session: RequestSession, target: ChildTarget["targetInfo"]): Promise<void>;
  fail(error: unknown): void;
};
export interface RequestSession {
  send(method: string, params?: Record<string, unknown>): Promise<Record<string, unknown>>;
  on(method: string, listener: (params: Record<string, unknown>) => void): void;
}

// Non-flattened child messages let the public Playwright CDP session pause nested targets.
class ChildSession implements RequestSession {
  private nextId = 0;
  private pending = new Map<number, { resolve(value: Record<string, unknown>): void; reject(error: Error): void }>();
  private listeners = new Map<string, ((params: Record<string, unknown>) => void)[]>();
  constructor(private parent: RequestSession, readonly id: string) {}
  send(method: string, params: Record<string, unknown> = {}) {
    const id = ++this.nextId;
    return new Promise<Record<string, unknown>>((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.parent.send("Target.sendMessageToTarget", {
        sessionId: this.id, message: JSON.stringify({ id, method, params }),
      }).catch(error => { this.pending.delete(id); reject(error); });
    });
  }
  on(method: string, listener: (params: Record<string, unknown>) => void) {
    this.listeners.set(method, [...(this.listeners.get(method) ?? []), listener]);
  }
  receive(message: string) {
    const event = JSON.parse(message) as Message;
    if (event.id !== undefined) {
      const request = this.pending.get(event.id);
      this.pending.delete(event.id);
      if (event.error) request?.reject(new Error(event.error.message));
      else request?.resolve(event.result ?? {});
    } else if (event.method) {
      for (const listener of this.listeners.get(event.method) ?? []) listener(event.params ?? {});
    }
  }
  close() {
    for (const request of this.pending.values()) request.reject(new Error("Chromium target closed"));
    this.pending.clear();
  }
}

export async function installBrowserRequestGate(root: CDPSession) {
  const policies = new Map<string, BrowserRequestPolicy>();
  const pausedPages = new Map<string, string>();
  const allChildren = new Set<ChildSession>();
  const adapter: RequestSession = {
    send: (method, params) => root.send(method as Parameters<CDPSession["send"]>[0], params),
    on: (method, listener) => root.on("event", event => {
      if (event.method === method) listener((event.params ?? {}) as Record<string, unknown>);
    }),
  };
  async function watch(parent: RequestSession, inherited: BrowserRequestPolicy) {
    const children = new Map<string, ChildSession>();
    parent.on("Target.receivedMessageFromTarget", event => {
      if (typeof event.sessionId === "string" && typeof event.message === "string") {
        children.get(event.sessionId)?.receive(event.message);
      }
    });
    parent.on("Target.detachedFromTarget", event => {
      if (typeof event.sessionId !== "string") return;
      const child = children.get(event.sessionId);
      child?.close();
      if (child) allChildren.delete(child);
      children.delete(event.sessionId);
    });
    parent.on("Target.attachedToTarget", event => {
      const attached = event as unknown as ChildTarget;
      const policy = inherited;
      void (async () => {
        if (!policy) throw new Error("No request policy owns this Chromium target");
        if (!attached.waitingForDebugger) throw new Error("Chromium target was not paused before execution");
        if (attached.targetInfo.openerId || attached.targetInfo.type === "service_worker") {
          await adapter.send("Target.closeTarget", { targetId: attached.targetInfo.targetId });
          return;
        }
        const sessionId = attached.sessionId;
        if (typeof sessionId !== "string") throw new Error("Chromium target session is missing");
        const child = new ChildSession(parent, sessionId);
        children.set(sessionId, child);
        allChildren.add(child);
        // Dedicated-worker requests are intercepted by their owning page's Fetch agent.
        if (attached.targetInfo.type !== "worker") await policy.attach(child, attached.targetInfo);
        await watch(child, policy);
        await child.send("Runtime.runIfWaitingForDebugger");
      })().catch(error => {
        policy?.fail(error);
        void adapter.send("Target.closeTarget", { targetId: attached.targetInfo.targetId })
          .catch(cleanup => policy?.fail(new AggregateError([error, cleanup], "Ungated target cleanup failed")));
      });
    });
    await parent.send("Target.setAutoAttach", {
      autoAttach: true, waitForDebuggerOnStart: true, flatten: false,
    });
  }
  root.on("Target.attachedToTarget", (event: ChildTarget) => {
    const policy = policies.get(event.targetInfo.browserContextId ?? "");
    if (!policy || event.targetInfo.openerId || event.targetInfo.type !== "page") {
      if (policy && !event.targetInfo.openerId && event.targetInfo.type !== "service_worker") {
        policy.fail(new BrowserNetworkError("Unsupported Chromium target refused before execution",
          "ERR_UNSUPPORTED_BROWSER_TARGET"));
      }
      void adapter.send("Target.closeTarget", { targetId: event.targetInfo.targetId })
        .catch(error => policy?.fail(error));
    } else pausedPages.set(event.targetInfo.targetId, event.sessionId);
  });
  await root.send("Target.setAutoAttach", { autoAttach: true, waitForDebuggerOnStart: true, flatten: true });
  return {
    register(contextId: string, policy: BrowserRequestPolicy) { policies.set(contextId, policy); },
    unregister(contextId: string) { policies.delete(contextId); },
    async preparePage(context: BrowserContext, page: Page, policy: BrowserRequestPolicy) {
      const session = await context.newCDPSession(page);
      const pageSession: RequestSession = {
        send: (method, params) => session.send(method as Parameters<CDPSession["send"]>[0], params),
        on: (method, listener) => session.on("event", event => {
          if (event.method === method) listener((event.params ?? {}) as Record<string, unknown>);
        }),
      };
      await policy.attach(pageSession, { targetId: "", type: "page" });
      await watch(pageSession, policy);
      await session.send("Runtime.runIfWaitingForDebugger");
      const { targetInfo } = await session.send("Target.getTargetInfo");
      const paused = pausedPages.get(targetInfo.targetId);
      if (!paused) throw new Error("Source page was not paused before request admission");
      await root.send("Target.detachFromTarget", { sessionId: paused });
      pausedPages.delete(targetInfo.targetId);
    },
    close() { for (const child of allChildren) child.close(); allChildren.clear(); policies.clear(); },
  };
}
