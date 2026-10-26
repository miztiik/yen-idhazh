/** Bound real HTML worker ownership and keep the listener free while extraction runs. */
import { randomUUID } from "node:crypto";
import { PositiveCountSchema } from "@idhazh/common-contracts";
import { ArticleExtractionError } from "./dom-extractor";
import type {
  ArticleParserRequest, ArticleParserResponse, ArticleParserResult,
} from "./article-parser-worker";
import type { ExtractionControls } from "./extraction-controls";
import { ArticleParserResponseSchema } from "./article-parser-worker";

type Job = {
  request: ArticleParserRequest;
  resolve: (result: ArticleParserResult) => void;
  reject: (error: Error) => void;
  activity: ((phase: "started" | "completed" | "failed") => void) | undefined;
  signal: AbortSignal | undefined; cancel: (() => void) | undefined; started: boolean;
};
type Slot = { worker: Worker; job: Job | null };

export class ArticleParserPool {
  private readonly slots: Slot[] = [];
  private readonly waiting: Job[] = [];
  private closed = false;

  constructor(private readonly concurrency: number, private readonly activity?: (phase: "started" | "completed" | "failed") => void) {
    PositiveCountSchema.parse(concurrency);
  }

  parse(body: string, url: string, config: ExtractionControls, form: "article" | "abstract", options: {
    activity?: (phase: "started" | "completed" | "failed") => void; signal?: AbortSignal;
  } = {}) {
    if (this.closed) return Promise.reject(new Error("Article parser pool is closed"));
    options.signal?.throwIfAborted();
    return new Promise<ArticleParserResult>((resolve, reject) => {
      const job: Job = {
        request: { id: randomUUID(), body, url, config, form }, resolve, reject,
        activity: options.activity ?? this.activity, signal: options.signal, cancel: undefined, started: false,
      };
      job.cancel = () => {
        const slot = this.slots.find(slot => slot.job === job);
        if (slot !== undefined) this.failSlot(slot, new Error("Article parsing was cancelled"));
        else {
          const position = this.waiting.indexOf(job);
          if (position >= 0) this.waiting.splice(position, 1);
          job.signal?.removeEventListener("abort", job.cancel!);
          job.reject(new Error("Article parsing was cancelled"));
        }
      };
      job.signal?.addEventListener("abort", job.cancel, { once: true });
      this.waiting.push(job);
      this.dispatch();
    });
  }

  private dispatch() {
    if (this.closed) return;
    while (this.waiting.length) {
      let slot = this.slots.find(slot => slot.job === null);
      if (slot === undefined) {
        if (this.slots.length >= this.concurrency) return;
        const worker = new Worker(new URL("./article-parser-worker.ts", import.meta.url).href);
        slot = { worker, job: null };
        const held = slot;
        worker.onmessage = (event: MessageEvent<unknown>) => {
          const checked = ArticleParserResponseSchema.safeParse(event.data);
          if (!checked.success) {
            this.failSlot(held, new Error("Article parser response failed its declared contract"));
            return;
          }
          const response: ArticleParserResponse = checked.data;
          const job = held.job;
          if (job === null || response.id !== job.request.id) {
            this.failSlot(held, new Error("Article parser response identity differs from its assigned job"));
            return;
          }
          if (response.phase === "started") {
            job.started = true;
            job.activity?.("started");
            return;
          }
          held.job = null;
          job.signal?.removeEventListener("abort", job.cancel!);
          job.activity?.(response.ok ? "completed" : "failed");
          if (response.ok) job.resolve(response.result);
          else job.reject(response.reason === "parser-failed"
            ? new Error("Article parser worker failed")
            : new ArticleExtractionError(response.reason));
          this.dispatch();
        };
        worker.onerror = event => { event.preventDefault(); this.failSlot(held, new Error("Article parser worker failed")); };
        this.slots.push(slot);
      }

      const job = this.waiting.shift()!;
      slot.job = job;
      slot.worker.postMessage(job.request);
    }
  }

  private failSlot(slot: Slot, error: Error) {
    const index = this.slots.indexOf(slot);
    if (index < 0) return;
    this.slots.splice(index, 1);
    const job = slot.job;
    slot.job = null;
    slot.worker.terminate();
    if (job !== null) {
      job.signal?.removeEventListener("abort", job.cancel!);
      if (job.started) job.activity?.("failed");
      job.reject(error);
    }
    this.dispatch();
  }

  close(error = new Error("Article parser pool closed before work completed")) {
    if (this.closed) return;
    this.closed = true;
    const slots = this.slots.splice(0);
    for (const job of this.waiting.splice(0)) {
      job.signal?.removeEventListener("abort", job.cancel!);
      job.reject(error);
    }
    for (const slot of slots) {
      slot.job?.signal?.removeEventListener("abort", slot.job.cancel!);
      if (slot.job?.started) slot.job.activity?.("failed");
      slot.job?.reject(error);
      slot.job = null;
      slot.worker.onmessage = null;
      slot.worker.onerror = null;
      slot.worker.terminate();
    }
  }
}
