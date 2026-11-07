/** How are one request's validated events delivered and saved privately? */
import fs from "node:fs";
import { EventEmitter } from "node:events";
import type { Writable } from "node:stream";
import {
  GeneratorLoggingSchema, type GeneratorConfig,
} from "../../services/summary-generator/src/config/load-generator-config.js";
import { createCloudEvent } from "@idhazh/common-contracts/create-cloud-event";
import type { OperationMetadata } from "@idhazh/common-contracts/schemas/operation-metadata";
import {
  parsePipelineEventData,
  readPipelineEvent,
  type PipelineEvent,
  type PipelineEventData,
  type PipelineEventType,
  type RecordedPipelineEvent,
} from "./contracts/pipeline-event.schema.js";

export function readPipelineEvents(jsonlFilePath: string): RecordedPipelineEvent[] {
  const lines = fs.readFileSync(jsonlFilePath, "utf8").split(/\r?\n/);
  if (lines.at(-1) === "") lines.pop();
  return lines.map((line, index) => {
    try {
      return readPipelineEvent(JSON.parse(line));
    } catch (cause) {
      throw new Error(`Invalid summarizer event at line ${index + 1}.`, { cause });
    }
  });
}

export class PipelineEventBus extends EventEmitter {
  private readonly auditLog: PipelineEvent[] = [];

  constructor(
    private readonly source: string,
    private readonly jsonlFilePath = "pipeline-events.jsonl",
    private readonly logging?: GeneratorConfig["logging"],
    private readonly diagnostic: Pick<Writable, "write"> = process.stderr,
  ) {
    super();
  }

  public emitEvent<T extends PipelineEventType>(
    type: T,
    data: PipelineEventData<T>,
    context: OperationMetadata,
  ): PipelineEvent<T> {
    const event: PipelineEvent<T> = {
      ...createCloudEvent({
        source: this.source,
        type,
        context,
        data,
        parseData: value => parsePipelineEventData(type, value),
      }),
      type,
    };
    fs.appendFileSync(this.jsonlFilePath, JSON.stringify(event) + "\n", "utf8");
    this.auditLog.push(event);
    this.recordDiagnostic({
      code: "SUMMARIZER_EVENT",
      id: event.id,
      type: event.type,
      time: event.time,
      traceId: context.traceId,
      spanId: context.spanId,
    });
    this.emit(type, event);
    return event;
  }

  public getEventHistory(): PipelineEvent[] {
    return structuredClone(this.auditLog);
  }

  public recordDiagnostic(record: Record<string, string | number | boolean | null>): void {
    if (this.logging) {
      const levels = GeneratorLoggingSchema.shape.level.options;
      if (levels.indexOf(this.logging.level) > levels.indexOf("INFO")) return;
    }
    const line = JSON.stringify(record);
    if (this.logging && Buffer.byteLength(line, "utf8") > this.logging.max_event_bytes) {
      throw new Error("The caller diagnostic exceeds its configured allowance.");
    }
    this.diagnostic.write(line + "\n");
  }
}
