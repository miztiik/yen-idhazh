/** Bound native feed and article parsing, including time waiting for a worker. */
import { randomUUID } from "node:crypto";
import { FeedHarvestConfigSchema, PositiveCountSchema } from "@idhazh/common-contracts";
import { ArticleExtractionError } from "./dom-extractor";
import { FeedParseError } from "./parse-feed";
import { ParserError } from "./parser-error";
import type {
  ArticleParserRequest, ArticleParserResponse, ArticleParserResult, FeedParserResult,
} from "./article-parser-worker";
import type { ExtractionControls } from "./extraction-controls";
import { ArticleParserResponseSchema } from "./article-parser-worker";

type ArticleParserActivity = (
  phase: "started" | "completed" | "failed",
  duration_ms: number | null,
  feed_id?: string | null,
  publisher_id?: string | null,
) => void;

export type ParserOptions = {
  activity?: ArticleParserActivity; signal?: AbortSignal; timeout_ms?: number;
};
type ParserResult = ArticleParserResult | FeedParserResult;
type Job = {
  request: ArticleParserRequest;
  resolve: (result: ParserResult) => void;
  reject: (error: Error) => void;
  activity: ArticleParserActivity | undefined;
  signal: AbortSignal | undefined; cancel: (() => void) | undefined; started: boolean;
  startedAt: number | null;
  deadline: number; timer: ReturnType<typeof setTimeout>; settled: boolean;
};
type Slot = { worker: Worker; job: Job | null };

export class ArticleParserPool {
  private readonly slots: Slot[] = [];
  private readonly waiting: Job[] = [];
  private closed = false;

  constructor(private readonly concurrency: number,
    private readonly activity?: ArticleParserActivity) {
    PositiveCountSchema.parse(concurrency);
  }

  parse(body: string, url: string, config: ExtractionControls, options: ParserOptions = {}): Promise<ArticleParserResult> {
    return this.enqueue({ id: randomUUID(), kind: "article", body, url, config }, options) as Promise<ArticleParserResult>;
  }

  parseFeed(body: string, options: ParserOptions = {}): Promise<FeedParserResult> {
    return this.enqueue({ id: randomUUID(), kind: "feed", body }, options) as Promise<FeedParserResult>;
  }

  private enqueue(request: ArticleParserRequest, options: ParserOptions) {
    if (this.closed) return Promise.reject(new ParserError("parser-cancelled"));
    if (options.signal?.aborted) return Promise.reject(new ParserError("parser-cancelled"));
    const timeout = FeedHarvestConfigSchema.shape.parse_timeout_ms.parse(options.timeout_ms);
    const deadline = performance.now() + timeout;
    return new Promise<ParserResult>((resolve, reject) => {
      const job: Job = {
        request, resolve, reject,
        activity: options.activity ?? this.activity, signal: options.signal, cancel: undefined, started: false, startedAt: null,
        deadline, timer: setTimeout(() => this.cancel(job, new ParserError("parser-timeout")), timeout), settled: false,
      };
      job.cancel = () => this.cancel(job, new ParserError("parser-cancelled"));
      job.signal?.addEventListener("abort", job.cancel, { once: true });
      this.waiting.push(job);
      this.dispatch();
    });
  }

  private cleanup(job: Job) {
    job.settled = true;
    clearTimeout(job.timer);
    job.signal?.removeEventListener("abort", job.cancel!);
  }

  private cancel(job: Job, error: Error) {
    if (job.settled) return;
    const slot = this.slots.find(slot => slot.job === job);
    if (slot !== undefined) this.failSlot(slot, error);
    else {
      const position = this.waiting.indexOf(job);
      if (position >= 0) this.waiting.splice(position, 1);
      this.cleanup(job);
      job.reject(error);
    }
  }

  private dispatch() {
    if (this.closed) return;
    while (this.waiting.length) {
      let slot = this.slots.find(slot => slot.job === null);
      if (slot === undefined) {
        if (this.slots.length >= this.concurrency) return;
        let worker: Worker;
        try { worker = new Worker(new URL("./article-parser-worker.ts", import.meta.url).href); }
        catch {
          const job = this.waiting.shift()!;
          this.cleanup(job);
          job.reject(new ParserError("parser-failed"));
          continue;
        }
        slot = { worker, job: null };
        const held = slot;
        worker.onmessage = (event: MessageEvent<unknown>) => {
          const checked = ArticleParserResponseSchema.safeParse(event.data);
          if (!checked.success) {
            this.failSlot(held, new ParserError("parser-failed"));
            return;
          }
          const response: ArticleParserResponse = checked.data;
          const job = held.job;
          if (job === null || response.id !== job.request.id) {
            this.failSlot(held, new ParserError("parser-failed"));
            return;
          }
          if (performance.now() >= job.deadline) {
            this.failSlot(held, new ParserError("parser-timeout"));
            return;
          }
          if (response.phase === "started") {
            job.started = true;
            job.startedAt = performance.now();
            job.activity?.("started", null);
            return;
          }
          if (response.ok && response.kind !== job.request.kind) {
            this.failSlot(held, new ParserError("parser-failed"));
            return;
          }
          held.job = null;
          this.cleanup(job);
          job.activity?.(response.ok ? "completed" : "failed", this.elapsed(job));
          if (response.ok) job.resolve(response.result);
          else job.reject(response.reason === "parser-failed"
            ? new ParserError("parser-failed")
            : response.reason === "malformed-feed" ? new FeedParseError(null) : new ArticleExtractionError(response.reason));
          this.dispatch();
        };
        worker.onerror = event => { event.preventDefault(); this.failSlot(held, new ParserError("parser-failed")); };
        this.slots.push(slot);
      }

      const job = this.waiting.shift()!;
      if (performance.now() >= job.deadline) {
        this.cleanup(job);
        job.reject(new ParserError("parser-timeout"));
        continue;
      }
      slot.job = job;
      try { slot.worker.postMessage(job.request); }
      catch { this.failSlot(slot, new ParserError("parser-failed")); }
    }
  }

  private elapsed(job: Job): number | null {
    if (job.startedAt === null) return null;
    return Math.max(0, Math.round(performance.now() - job.startedAt));
  }

  private failSlot(slot: Slot, error: Error) {
    const index = this.slots.indexOf(slot);
    if (index < 0) return;
    this.slots.splice(index, 1);
    const job = slot.job;
    slot.job = null;
    slot.worker.terminate();
    if (job !== null) {
      this.cleanup(job);
      if (job.started) job.activity?.("failed", this.elapsed(job));
      job.reject(error);
    }
    this.dispatch();
  }

  close(error: Error = new ParserError("parser-cancelled")) {
    if (this.closed) return;
    this.closed = true;
    const slots = this.slots.splice(0);
    for (const job of this.waiting.splice(0)) {
      this.cleanup(job);
      job.reject(error);
    }
    for (const slot of slots) {
      if (slot.job !== null) this.cleanup(slot.job);
      if (slot.job?.started) slot.job.activity?.("failed", this.elapsed(slot.job));
      slot.job?.reject(error);
      slot.job = null;
      slot.worker.onmessage = null;
      slot.worker.onerror = null;
      slot.worker.terminate();
    }
  }
}
