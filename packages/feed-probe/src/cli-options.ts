/** Parse bounded standalone feed-probe command options without adding a CLI framework. */
import {
  FEED_PROBE_SAMPLE_DEFAULT,
  FeedProbeSampleCountSchema,
  SlugSchema,
  UrlSchema,
} from "@idhazh/common-contracts";

export type SourceSelectionMode = "feeds" | "retired" | "all";
export type FeedProbeLogLevel = "INFO" | "DEBUG" | "WARN" | "ERROR";

export type FeedProbeCliOptions = {
  urls: string[];
  articles: number;
  report: string | null;
  trace: string | null;
  logLevel: FeedProbeLogLevel;
  fromConfig: SourceSelectionMode | null;
  vertical: string | null;
  ids: string[];
  json: boolean;
  jsonLines: boolean;
};

export type FeedProbeCliParseResult =
  | { kind: "options"; options: FeedProbeCliOptions }
  | { kind: "help" }
  | { kind: "error"; message: string };

export function feedProbeCliUsage(): string {
  return [
    "Usage: bun src/feed-probe-cli.ts [options] <url...>",
    "",
    "Options:",
    "  --articles <integer>       Articles per feed (default 3)",
    "  --report <relative.jsonl>  Write one strict JSON object per feed",
    "  --trace <relative.jsonl>   Trace path (default backend/var/probes/<UTC-stamp>.jsonl)",
    "  --log-level <level>        INFO, DEBUG, WARN, or ERROR",
    "  --from-config <mode>       Select feeds, retired, or all",
    "  --vertical <slug>          Filter configured feeds by vertical",
    "  --id <slug>                Select a configured feed; repeatable",
    "  --json                     Print a strict JSON summary",
    "  --json-lines               Print one strict JSON report per feed",
    "  -h, --help                 Show this help",
  ].join("\n");
}

function validUrl(raw: string): boolean {
  if (!UrlSchema.safeParse(raw).success) return false;
  try {
    const url = new URL(raw);
    return !url.username && !url.password && (url.protocol === "http:" || url.protocol === "https:");
  } catch {
    return false;
  }
}

function readValue(
  args: readonly string[],
  index: number,
  option: string,
): { value: string; next: number } | { error: string } {
  const current = args[index]!;
  const equals = current.indexOf("=");
  if (equals >= 0) {
    const value = current.slice(equals + 1);
    if (!value) return { error: `${option} requires a value` };
    return { value, next: index };
  }
  if (index + 1 >= args.length || args[index + 1]!.startsWith("--")) {
    return { error: `${option} requires a value` };
  }
  return { value: args[index + 1]!, next: index + 1 };
}

export function parseFeedProbeCliArguments(args: readonly string[]): FeedProbeCliParseResult {
  if (args.includes("--help") || args.includes("-h")) return { kind: "help" };

  const options: FeedProbeCliOptions = {
    urls: [],
    articles: FEED_PROBE_SAMPLE_DEFAULT,
    report: null,
    trace: null,
    logLevel: "INFO",
    fromConfig: null,
    vertical: null,
    ids: [],
    json: false,
    jsonLines: false,
  };

  for (let index = 0; index < args.length; index += 1) {
    const current = args[index]!;

    if (current === "--articles" || current.startsWith("--articles=")) {
      const valueResult = readValue(args, index, "--articles");
      if ("error" in valueResult) return { kind: "error", message: valueResult.error };
      index = valueResult.next;
      if (!/^\d+$/.test(valueResult.value)) {
        return { kind: "error", message: "--articles must be an integer" };
      }
      const articles = Number(valueResult.value);
      const parsed = FeedProbeSampleCountSchema.safeParse(articles);
      if (!parsed.success) {
        return { kind: "error", message: `--articles must be between 1 and 10` };
      }
      options.articles = parsed.data;
      continue;
    }

    if (current === "--report" || current.startsWith("--report=")) {
      const valueResult = readValue(args, index, "--report");
      if ("error" in valueResult) return { kind: "error", message: valueResult.error };
      index = valueResult.next;
      options.report = valueResult.value;
      continue;
    }

    if (current === "--trace" || current.startsWith("--trace=")) {
      const valueResult = readValue(args, index, "--trace");
      if ("error" in valueResult) return { kind: "error", message: valueResult.error };
      index = valueResult.next;
      options.trace = valueResult.value;
      continue;
    }

    if (current === "--log-level" || current.startsWith("--log-level=")) {
      const valueResult = readValue(args, index, "--log-level");
      if ("error" in valueResult) return { kind: "error", message: valueResult.error };
      index = valueResult.next;
      const level = valueResult.value.toUpperCase();
      if (!["INFO", "DEBUG", "WARN", "ERROR"].includes(level)) {
        return { kind: "error", message: "--log-level must be INFO, DEBUG, WARN, or ERROR" };
      }
      options.logLevel = level as FeedProbeLogLevel;
      continue;
    }

    if (current === "--from-config" || current.startsWith("--from-config=")) {
      const valueResult = readValue(args, index, "--from-config");
      if ("error" in valueResult) return { kind: "error", message: valueResult.error };
      index = valueResult.next;
      if (!["feeds", "retired", "all"].includes(valueResult.value)) {
        return { kind: "error", message: "--from-config must be feeds, retired, or all" };
      }
      options.fromConfig = valueResult.value as SourceSelectionMode;
      continue;
    }

    if (current === "--vertical" || current.startsWith("--vertical=")) {
      const valueResult = readValue(args, index, "--vertical");
      if ("error" in valueResult) return { kind: "error", message: valueResult.error };
      index = valueResult.next;
      const parsed = SlugSchema.safeParse(valueResult.value);
      if (!parsed.success) return { kind: "error", message: "--vertical must be a valid slug" };
      options.vertical = parsed.data;
      continue;
    }

    if (current === "--id" || current.startsWith("--id=")) {
      const valueResult = readValue(args, index, "--id");
      if ("error" in valueResult) return { kind: "error", message: valueResult.error };
      index = valueResult.next;
      const parsed = SlugSchema.safeParse(valueResult.value);
      if (!parsed.success) return { kind: "error", message: "--id must be a valid source slug" };
      options.ids.push(parsed.data);
      continue;
    }

    if (current === "--json" || current === "--json-summary") {
      options.json = true;
      continue;
    }
    if (current === "--json-lines") {
      options.jsonLines = true;
      continue;
    }
    if (current.startsWith("-")) {
      return { kind: "error", message: `Unknown option: ${current}` };
    }
    if (!validUrl(current)) {
      return { kind: "error", message: `Invalid feed URL: ${current}` };
    }
    options.urls.push(current);
  }

  if (options.json && options.jsonLines) {
    return { kind: "error", message: "--json and --json-lines cannot be used together" };
  }
  if (new Set(options.ids).size !== options.ids.length) {
    return { kind: "error", message: "Duplicate --id target" };
  }
  return { kind: "options", options };
}

export const parseCliArguments = parseFeedProbeCliArguments;
