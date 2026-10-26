/** Bound real HTML worker ownership and keep the listener free while extraction runs. */
import { randomUUID } from "node:crypto";
import { PositiveCountSchema } from "@idhazh/common-contracts";
import { ArticleExtractionError } from "./dom-extractor";
import type {
  ArticleParserRequest, ArticleParserResponse, ArticleParserResult,
} from "./article-parser-worker";
import type { ExtractionControls } from "./extraction-controls";

type Job = {
  request: ArticleParserRequest;
  resolve: (result: ArticleParserResult) => void;
  reject: (error: Error) => void;
};
type Slot = { worker: Worker; job: Job | null };

export class ArticleParserPool {
  private readonly slots: Slot[] = [];
  private readonly waiting: Job[] = [];
  private closed = false;

  constructor(private readonly concurrency: number, private readonly activity?: (phase: "started" | "completed" | "failed") => void) {
    PositiveCountSchema.parse(concurrency);
  }

  parse(body: string, url: string, config: ExtractionControls, form: "article" | "abstract") {
    if (this.closed) return Promise.reject(new Error("Article parser pool is closed"));
    return new Promise<ArticleParserResult>((resolve, reject) => {
      this.waiting.push({ request: { id: randomUUID(), body, url, config, form }, resolve, reject });
      this.dispatch();
    });
  }

  private dispatch() {
    while (this.waiting.length) {
      let slot = this.slots.find(slot => slot.job === null);
      if (slot === undefined) {
        if (this.slots.length >= this.concurrency) return;
        const worker = new Worker(new URL("./article-parser-worker.ts", import.meta.url).href);
        slot = { worker, job: null };
        const held = slot;
        worker.onmessage = (event: MessageEvent<ArticleParserResponse>) => {
          const job = held.job;
          if (job === null || event.data.id !== job.request.id) {
            this.close(new Error("Article parser response identity differs from its assigned job"));
            return;
          }
          if (event.data.phase === "started") {
            this.activity?.("started");
            return;
          }
          held.job = null;
          this.activity?.(event.data.ok ? "completed" : "failed");
          if (event.data.ok) job.resolve(event.data.result);
          else job.reject(event.data.reason === "parser-failed"
            ? new Error("Article parser worker failed")
            : new ArticleExtractionError(event.data.reason));
          this.dispatch();
        };
        worker.onerror = () => this.close(new Error("Article parser worker failed"));
        this.slots.push(slot);
      }
      const job = this.waiting.shift()!;
      slot.job = job;
      slot.worker.postMessage(job.request);
    }
  }

  close(error = new Error("Article parser pool closed before work completed")) {
    if (this.closed) return;
    this.closed = true;
    for (const slot of this.slots) {
      slot.job?.reject(error);
      slot.job = null;
      slot.worker.terminate();
    }
    for (const job of this.waiting.splice(0)) job.reject(error);
  }
}
