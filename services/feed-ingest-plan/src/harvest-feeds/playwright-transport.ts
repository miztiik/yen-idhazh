/** Download source documents through checked Chromium requests and retain their original completion evidence. */
import { errors } from "playwright";
import type { Page } from "playwright";
import type { FeedIngestConfig } from "@idhazh/common-contracts";
import { createBrowserRuntime } from "./browser-runtime";
import type { BrowserRuntime } from "./browser-runtime";
import type { BrowserRequestPolicy } from "./browser-request-gate";
import {
  BodyLimitError, BrowserNetworkError, BrowserRequestInterruptedError, ChallengeUnresolvedError, HTTP_REDIRECT_STATUSES, ResponseReadError,
} from "./transport";
import type { HarvestTransport, TransportResponse } from "./transport";
import { admitParserInput, completedBrowserResponse, inlineDocumentHeaders } from "./browser-document-response";
import { responseEvidence } from "./source-response-evidence";
import { UnsafeTargetError } from "./safe-target";
import { isBrowserIconRequest } from "./browser-icon-request";

type PendingResponse = {
  url: string; role: "document" | "resource"; status: number | null; headers: Headers;
  body?: Buffer; documentOrder?: number;
  redirected?: boolean;
  resolve(value: TransportResponse): void; reject(error: unknown): void;
};
function responseHeaders(value: unknown): { name: string; value: string }[] {
  if (!Array.isArray(value)) return [];
  return value.map(header => {
    if (header === null || typeof header !== "object"
      || typeof header.name !== "string" || typeof header.value !== "string") {
      throw new Error("Invalid Chromium response header");
    }
    return { name: header.name, value: header.value };
  });
}

export function createPlaywrightTransport(
  config: FeedIngestConfig["harvest"], supplied?: BrowserRuntime,
): HarvestTransport {
  const runtime = supplied ?? createBrowserRuntime(config.browser);
  const active = new Map<AbortController, Promise<void>>();
  const fatalContext: BrowserRequestPolicy = {
    async attach() { throw new Error("Source page needs a document request owner"); },
    fail(error) { for (const controller of active.keys()) controller.abort(error); },
  };
  let context: ReturnType<BrowserRuntime["context"]> | undefined;
  let closed = false;
  return {
    browser_managed: true,
    async request(input) {
      if (closed) throw new Error("Source browser transport is closed");
      if (!input.gate) throw new Error("Source browser request has no pre-dispatch policy");
      input.signal.throwIfAborted();
      const controller = new AbortController();
      let finish!: () => void;
      active.set(controller, new Promise<void>(resolve => { finish = resolve; }));
      const signal = AbortSignal.any([controller.signal, input.signal]);
      context ??= runtime.context(fatalContext, Object.fromEntries(Object.entries(config.request_headers)
        .flatMap(([name, value]) => typeof value === "string" ? [[name, value]] : [])));
      let page: Page | undefined;
      let closing: Promise<void> | undefined;
      let deadline: ReturnType<typeof setTimeout> | undefined;
      let finishReadiness: (() => void) | undefined;
      let terminal: TransportResponse | undefined;
      let challenged = false;
      let selectorChallenge = false;
      let fatal: unknown;
      let primaryFailure: unknown;
      let documentOrder = 0;
      let terminalOrder = -1;
      let pageClosing = false;
      const requests = new Map<string, PendingResponse>();
      const tasks = new Set<Promise<void>>();
      const documentReads: Promise<TransportResponse>[] = [];
      const closePage = () => {
        pageClosing = true;
        if (page) closing ??= page.close();
        return closing;
      };
      const fail = (error: unknown) => {
        fatal ??= error;
        controller.abort(error);
      };
      const settleFailure = (request: PendingResponse, error: unknown) => {
        request.reject(request.status === null ? error : new ResponseReadError(
          request.status, responseEvidence(request.headers, input, null), error,
        ));
      };
      const settleCompleted = (request: PendingResponse) => {
        try {
          if (request.status === null) throw new BrowserNetworkError("Response completed without original headers");
          if (request.role === "document") {
            if (!request.body || request.documentOrder === undefined) {
              throw new BrowserNetworkError("Document completed without its original body and order");
            }
            const completed = completedBrowserResponse(input, request.status, request.headers, request.body, request.url);
            if (request.documentOrder >= terminalOrder) {
              terminal = completed;
              terminalOrder = request.documentOrder;
            }
            request.resolve(completed);
          } else request.resolve({ status: request.status, body: "", location: request.headers.get("location"),
            evidence: responseEvidence(request.headers, input, null), final_url: request.url });
        } catch (error) {
          if (error instanceof BodyLimitError) request.reject(error);
          else settleFailure(request, error);
        }
      };
      const policy: BrowserRequestPolicy = {
        fail,
        async attach(session, target) {
          let mainFrame: string | null = null;
          if (target.type === "page") {
            const tree = await session.send("Page.getFrameTree");
            const frameTree = tree.frameTree;
            if (frameTree && typeof frameTree === "object" && "frame" in frameTree
              && frameTree.frame && typeof frameTree.frame === "object" && "id" in frameTree.frame
              && typeof frameTree.frame.id === "string") mainFrame = frameTree.frame.id;
            if (!mainFrame) throw new Error("Source page has no main frame identity");
          }
          session.on("Network.responseReceived", event => {
            if (typeof event.requestId !== "string") return;
            const pending = requests.get(event.requestId);
            const response = event.response;
            if (!pending || !response || typeof response !== "object"
              || !("status" in response) || typeof response.status !== "number"
              || !("headers" in response) || !response.headers || typeof response.headers !== "object") return;
            pending.status ??= response.status;
            if ([...pending.headers].length === 0) {
              pending.headers = new Headers(Object.entries(response.headers)
                .filter((entry): entry is [string, string] => typeof entry[1] === "string")
                .flatMap(([name, value]) => value.split("\n").map((part): [string, string] => [name, part.trim()])));
            }
          });
          session.on("Network.loadingFailed", event => {
            if (typeof event.requestId !== "string") return;
            const request = requests.get(event.requestId);
            if (!request) return;
            requests.delete(event.requestId);
            const code = typeof event.errorText === "string"
              ? /^net::(ERR_[A-Z0-9_]+)$/.exec(event.errorText)?.[1] ?? null : null;
            if (request.redirected) {
              if (request.role === "document" && !pageClosing && request.status !== null) {
                fail(new ResponseReadError(request.status, responseEvidence(request.headers, input, null),
                  new BrowserNetworkError("Chromium redirect navigation did not complete", code)));
              }
              return;
            }
            // These statuses have no HTTP body; Chromium can abort both navigation and resource delivery.
            if (!signal.aborted && code === "ERR_ABORTED"
              && (request.role === "resource" || request.body?.length === 0)
              && (request.status === 204 || request.status === 205)) {
              settleCompleted(request);
              return;
            }
            settleFailure(request, pageClosing
              ? new BrowserRequestInterruptedError("Source page closed before resource completion")
              : new BrowserNetworkError("Chromium response did not complete", code));
          });
          session.on("Network.loadingFinished", event => {
            if (typeof event.requestId !== "string") return;
            const request = requests.get(event.requestId);
            if (!request) return;
            requests.delete(event.requestId);
            if (request.redirected) return;
            settleCompleted(request);
          });
          session.on("Fetch.requestPaused", event => {
            if (typeof event.requestId !== "string") { fail(new Error("Chromium supplied no intercepted request identity")); return; }
            const fetchId = event.requestId;
            const request = event.request;
            const networkId = event.networkId;
            if (!request || typeof request !== "object" || !("url" in request) || typeof request.url !== "string"
              || typeof networkId !== "string") {
              fail(new Error("Chromium request cannot be checked and accounted before dispatch"));
              return;
            }
            const url = request.url;
            const role = event.resourceType === "Document" && event.frameId === mainFrame ? "document" : "resource";
            const job = (async () => {
              if (event.responseStatusCode === undefined && event.responseErrorReason === undefined
                && await isBrowserIconRequest(session, url, event.resourceType)) {
                await session.send("Fetch.failRequest", { requestId: fetchId, errorReason: "BlockedByClient" });
                return;
              }
              if (typeof event.responseErrorReason === "string") {
                const pending = requests.get(networkId);
                if (!pending) throw new Error("Chromium response failure has no admitted request");
                requests.delete(networkId);
                settleFailure(pending, new BrowserNetworkError("Chromium response failed before completion"));
                await session.send("Fetch.failRequest", { requestId: fetchId, errorReason: event.responseErrorReason });
                return;
              }
              if (typeof event.responseStatusCode === "number") {
                const pending = requests.get(networkId);
                if (!pending) throw new Error("Chromium response has no admitted request");
                const headers = responseHeaders(event.responseHeaders);
                pending.headers = new Headers(headers.map((header): [string, string] => [header.name, header.value]));
                pending.status = event.responseStatusCode;
                if (role === "document") challenged = pending.headers.get("cf-mitigated") === "challenge";
                const inline = inlineDocumentHeaders(headers, input.kind, role);
                const redirect = HTTP_REDIRECT_STATUSES.has(event.responseStatusCode) && pending.headers.has("location");
                if (role === "document" && !redirect) {
                  try {
                    const body = await session.send("Fetch.getResponseBody", { requestId: fetchId });
                    if (typeof body.body !== "string" || typeof body.base64Encoded !== "boolean") {
                      throw new Error("Chromium supplied no completed document body");
                    }
                    pending.body = Buffer.from(body.body, body.base64Encoded ? "base64" : "utf8");
                  } catch (error) {
                    requests.delete(networkId);
                    if (error instanceof BodyLimitError) pending.reject(error);
                    else settleFailure(pending, error);
                    return;
                  }
                }
                await session.send("Fetch.continueResponse", {
                  requestId: fetchId,
                  ...(inline ? { responseCode: event.responseStatusCode, responseHeaders: inline } : {}),
                });
                if (redirect) {
                  pending.redirected = true;
                  pending.resolve({
                    status: event.responseStatusCode, body: "", location: pending.headers.get("location"),
                    evidence: responseEvidence(pending.headers, input, null), final_url: pending.url,
                  });
                }
                return;
              }
              let dispatched = false;
              const completed = input.gate!(url, role, async requestSignal => {
                requestSignal.throwIfAborted();
                if (role === "document" && !deadline) {
                  deadline = setTimeout(() => {
                    if (finishReadiness && terminal && ![...requests.values()].some(value => value.role === "document")) {
                      finishReadiness();
                    } else controller.abort(new errors.TimeoutError("Source document deadline exceeded"));
                  }, config.browser.document_timeout_ms);
                }
                let resolve!: (value: TransportResponse) => void;
                let reject!: (error: unknown) => void;
                const settlement = new Promise<TransportResponse>((done, failed) => { resolve = done; reject = failed; });
                const pending: PendingResponse = { url, role, status: null, headers: new Headers(), resolve, reject,
                  ...(role === "document" ? { documentOrder: documentOrder++ } : {}) };
                requests.set(networkId, pending);
                const abort = () => settleFailure(pending, requestSignal.reason);
                const timer = setTimeout(() => settleFailure(pending,
                  new errors.TimeoutError("Source HTTP request deadline exceeded")), input.timeout_ms);
                requestSignal.addEventListener("abort", abort, { once: true });
                try {
                  dispatched = true;
                  const continued = session.send("Fetch.continueRequest", { requestId: fetchId });
                  return (await Promise.all([continued, settlement]))[1];
                } finally {
                  clearTimeout(timer);
                  requestSignal.removeEventListener("abort", abort);
                }
              });
              if (role === "document") documentReads.push(completed);
              try { await completed; }
              catch (error) {
                if (!dispatched) {
                  await session.send("Fetch.failRequest", { requestId: fetchId, errorReason: "BlockedByClient" });
                }
                if (role === "document" || error instanceof UnsafeTargetError) fail(error);
              }
            })().catch(fail);
            tasks.add(job);
            void job.then(() => tasks.delete(job), () => tasks.delete(job));
          });
          await session.send("Network.enable");
          await session.send("Network.setCacheDisabled", { cacheDisabled: true });
          await session.send("Fetch.enable", {
            patterns: [{ urlPattern: "*", requestStage: "Request" }, { urlPattern: "*", requestStage: "Response" }],
          });
        },
      };
      const abort = () => {
        for (const request of requests.values()) settleFailure(request, signal.reason);
        void closePage()?.catch(error => { fatal ??= error; });
      };
      signal.addEventListener("abort", abort, { once: true });
      try {
        const owned = await context;
        signal.throwIfAborted();
        page = await owned.page(policy);
        signal.throwIfAborted();
        try { await page.goto(input.url.href, { waitUntil: "domcontentloaded", timeout: 0 }); }
        catch (error) {
          await Promise.all(documentReads);
          // HTTP 204 and 205 complete without creating a browser document.
          if (!fatal && !signal.aborted && !challenged && terminal
            && (terminal.status === 204 || terminal.status === 205)) {
            await Promise.all(documentReads);
            return admitParserInput(input, terminal, terminal.body);
          }
          throw error;
        }
        if (challenged) {
          await page.waitForEvent("response", {
            predicate: response => response.request().isNavigationRequest()
              && response.frame() === page!.mainFrame() && response.headers()["cf-mitigated"] !== "challenge",
            timeout: 0,
          });
        }
        if (config.browser.challenge_selectors.length > 0) {
          selectorChallenge = await page.locator(config.browser.challenge_selectors.join(",")).count() > 0;
          await page.waitForFunction(selectors => !selectors.some(selector => document.querySelector(selector)),
            config.browser.challenge_selectors, { timeout: 0 });
          selectorChallenge = false;
        }
        if (input.kind === "article") {
          const expired = new Promise<void>(resolve => { finishReadiness = resolve; });
          await Promise.race([expired, page.waitForFunction(({ roots, challenges }) => {
            if (challenges.some(selector => document.querySelector(selector))) return false;
            return roots.some(selector => (document.querySelector(selector)?.textContent?.trim().length ?? 0) > 0)
              || (document.readyState === "complete" && !roots.some(selector => document.querySelector(selector))
                && (document.body?.innerText?.trim().length ?? 0) > 0);
          }, { roots: config.semantic_fallback.content_roots, challenges: config.browser.challenge_selectors }, { timeout: 0 })]);
          finishReadiness = undefined;
        }
        await Promise.all(documentReads);
        if (fatal) throw fatal;
        if (!terminal) throw new BrowserNetworkError("Browser navigation has no completed document");
        const unresolved = challenged || (config.browser.challenge_selectors.length > 0
          && (await page.locator(config.browser.challenge_selectors.join(",")).count()) > 0);
        if (unresolved) throw new ChallengeUnresolvedError(terminal.status, terminal.evidence,
          new Error("Browser challenge did not resolve"));
        return admitParserInput(input, terminal, input.kind === "article" ? await page.content() : terminal.body);
      } catch (error) {
        const cause = fatal ?? (signal.aborted ? signal.reason : error);
        primaryFailure = !fatal && terminal && (challenged || selectorChallenge)
          ? new ChallengeUnresolvedError(terminal.status, terminal.evidence, cause)
          : !fatal && terminal && !(cause instanceof ResponseReadError || cause instanceof BodyLimitError)
            ? new ResponseReadError(terminal.status, terminal.evidence, cause) : cause;
        throw primaryFailure;
      } finally {
        clearTimeout(deadline);
        signal.removeEventListener("abort", abort);
        try {
          const cleanup = await Promise.allSettled([closePage()]);
          for (const request of requests.values()) settleFailure(request,
            new BrowserRequestInterruptedError("Source page closed before request completion"));
          await Promise.all(tasks);
          const failed = cleanup.find(result => result.status === "rejected");
          if (failed?.status === "rejected") {
            if (primaryFailure instanceof ResponseReadError || primaryFailure instanceof BodyLimitError) {
              const original = primaryFailure instanceof ResponseReadError ? primaryFailure.cause : primaryFailure;
              const combined = new AggregateError([original, failed.reason],
                "Source response and page cleanup failed", { cause: original });
              throw primaryFailure instanceof ChallengeUnresolvedError
                ? new ChallengeUnresolvedError(primaryFailure.http_status, primaryFailure.response_evidence, combined)
                : new ResponseReadError(primaryFailure.http_status, primaryFailure.response_evidence, combined);
            }
            throw new AggregateError([...(primaryFailure === undefined ? [] : [primaryFailure]), failed.reason],
              "Source page cleanup failed", { cause: primaryFailure ?? failed.reason });
          }
          if (primaryFailure === undefined && fatal) throw fatal;
        } finally { active.delete(controller); finish(); }
      }
    },
    async close() {
      closed = true;
      for (const controller of active.keys()) controller.abort(new DOMException("Source transport is closing", "AbortError"));
      await Promise.all(active.values());
      const failures: unknown[] = [];
      if (context) {
        try { await (await context).close(); }
        catch (error) { failures.push(error); }
      }
      if (!supplied) {
        try { await runtime.close(); }
        catch (error) { failures.push(error); }
      }
      if (failures.length) throw new AggregateError(failures, "Source transport cleanup failed");
    },
  };
}
