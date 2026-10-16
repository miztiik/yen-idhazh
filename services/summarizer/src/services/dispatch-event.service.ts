import fs from "node:fs";
import crypto from "node:crypto";
import { EventEmitter } from "node:events";
import type { PipelineEvent, PipelineEventType } from "../schemas/export-all-schemas.js";

const RFC_4122_NAMESPACE = "6ba7b810-9dad-11d1-80b4-00c04fd430c8";

function uuidToBytes(uuid: string): Buffer {
  return Buffer.from(uuid.replace(/-/g, ""), "hex");
}

export function generateUuidV5(name: string, namespace: string = RFC_4122_NAMESPACE): string {
  const nsBytes = uuidToBytes(namespace);
  const hash = crypto.createHash("sha1");
  hash.update(nsBytes);
  hash.update(Buffer.from(name, "utf8"));
  const digest = hash.digest();

  digest[6] = (digest[6] & 0x0f) | 0x50; // Version 5
  digest[8] = (digest[8] & 0x3f) | 0x80; // Variant RFC 4122

  const hex = digest.subarray(0, 16).toString("hex");
  return [
    hex.substring(0, 8),
    hex.substring(8, 12),
    hex.substring(12, 16),
    hex.substring(16, 20),
    hex.substring(20, 32),
  ].join("-");
}

export class PipelineEventBus extends EventEmitter {
  private auditLog: PipelineEvent[] = [];
  private readonly correlationId: string;
  private readonly runnerName: string;
  private readonly shardId: string;
  private readonly jsonlFilePath: string;

  constructor(runnerName: string, shardId: string, jsonlFilePath = "pipeline-events.jsonl") {
    super();
    this.runnerName = runnerName;
    this.shardId = shardId;
    this.correlationId = `corr-${Date.now()}`;
    this.jsonlFilePath = jsonlFilePath;
  }

  private createEventId(eventType: string, epochMs: number): string {
    const seed = `runner:${this.runnerName}:shard:${this.shardId}:epoch:${epochMs}:event:${eventType}`;
    return `evt-${generateUuidV5(seed)}`;
  }

  public emitEvent<T = unknown>(eventType: PipelineEventType, payload: T): PipelineEvent<T> {
    const epochMs = Date.now();
    const event: PipelineEvent<T> = {
      eventId: this.createEventId(eventType, epochMs),
      eventType,
      timestamp: new Date(epochMs).toISOString(),
      correlationId: this.correlationId,
      payload,
    };

    this.auditLog.push(event);

    const jsonlLine = JSON.stringify(event);
    fs.appendFileSync(this.jsonlFilePath, jsonlLine + "\n", "utf8");
    console.log(`[JSONL_EVENT] ${jsonlLine}`);

    this.emit(eventType, event);
    return event;
  }

  public getEventHistory(): PipelineEvent[] {
    return this.auditLog;
  }
}