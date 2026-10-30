/** Resolve local source-catalog targets and ad-hoc URLs before feed transport starts. */
import { join } from "node:path";
import { z } from "zod";
import {
  LifecycleStatusSchema,
  NonEmptySchema,
  PositiveCountSchema,
  SlugSchema,
  SourceSnapshotSchema,
  UrlSchema,
} from "@idhazh/common-contracts";
import type { FeedProbeCliOptions } from "./cli-options";

const CatalogSourceSchema = z.object({
  added_on: z.string().regex(/^\d{4}-\d{2}-\d{2}$/).nullable().optional().default(null),
  form: z.string().optional().default("article"),
  id: SlugSchema,
  kind: z.string().optional().default("reporting"),
  publisher_id: SlugSchema.nullable().optional().default(null),
  retired_on: z.string().regex(/^\d{4}-\d{2}-\d{2}$/).nullable().optional().default(null),
  retirement_reason: z.string().nullable().optional().default(null),
  status: LifecycleStatusSchema,
  tier: PositiveCountSchema.optional().default(1),
  title: NonEmptySchema.optional().default("Configured feed"),
  url: UrlSchema.refine(value => {
    try {
      const url = new URL(value);
      return !url.username && !url.password;
    } catch {
      return false;
    }
  }),
  vertical: SlugSchema.optional(),
  weight: z.number().finite().min(0).max(1).optional().default(1),
}).passthrough();

const CatalogSchema = z.object({
  version: z.string().optional(),
  feeds: z.array(CatalogSourceSchema).default([]),
  retired: z.array(CatalogSourceSchema).default([]),
}).passthrough();

export type CatalogSource = z.infer<typeof CatalogSourceSchema>;

export type FeedProbeTarget = {
  feed_id: string;
  url: string;
  status: z.infer<typeof LifecycleStatusSchema>;
  vertical: string | null;
};

export class FeedProbeInputError extends Error {}

export function normalizeFeedUrl(raw: string): string {
  const parsedUrl = UrlSchema.safeParse(raw.trim());
  if (!parsedUrl.success) throw new FeedProbeInputError(`Invalid feed URL: ${raw}`);
  let url: URL;
  try {
    url = new URL(parsedUrl.data);
  } catch {
    throw new FeedProbeInputError(`Invalid feed URL: ${raw}`);
  }
  if (url.username || url.password) throw new FeedProbeInputError(`Feed URL must not contain credentials`);
  if (url.protocol !== "http:" && url.protocol !== "https:") {
    throw new FeedProbeInputError(`Feed URL must use HTTP or HTTPS: ${raw}`);
  }

  url.protocol = url.protocol.toLowerCase();
  url.hostname = url.hostname.toLowerCase().replace(/^www\./, "");
  if ((url.protocol === "http:" && url.port === "80") || (url.protocol === "https:" && url.port === "443")) {
    url.port = "";
  }
  url.hash = "";
  url.searchParams.sort();
  const path = url.pathname.replace(/\/+$/, "");
  const query = url.searchParams.toString();
  return `${url.protocol}//${url.host}${path}${query ? `?${query}` : ""}`;
}

function slug(value: string): string {
  const result = value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .replace(/-{2,}/g, "-");
  return result || "feed";
}

export function deriveSourceIdCandidates(raw: string): string[] {
  const normalized = normalizeFeedUrl(raw);
  const url = new URL(normalized);
  const hostLabels = url.hostname.replace(/\.$/, "").split(".").filter(Boolean);
  const commonLabels = new Set(["com", "org", "net", "co", "uk", "au", "in", "io", "ai", "gov", "edu", "me", "info", "biz", "app", "dev"]);
  const rootLabels = hostLabels.filter(label => !commonLabels.has(label));
  const hostBase = rootLabels.length ? slug(rootLabels.join("-")) : slug(hostLabels.join("-"));
  const hostFull = slug(hostLabels.join("-"));
  const firstLabel = hostLabels[0] ? slug(hostLabels[0]) : "feed";
  const candidates = new Set<string>();
  candidates.add(hostBase);
  candidates.add(hostFull);
  candidates.add(firstLabel);
  if (hostLabels.length >= 3) {
    candidates.add(slug(hostLabels.slice(0, -2).join("-")));
    candidates.add(slug(hostLabels.slice(0, -2).concat(hostLabels.slice(-2, -1)).join("-")));
  }

  const pathLabels = url.pathname
    .split("/")
    .map(segment => segment.replace(/\.[^.]+$/, ""))
    .filter(segment => segment && !["rss", "feed", "xml", "index"].includes(segment.toLowerCase()))
    .map(slug);
  for (const segment of pathLabels.slice(-2)) {
    if (segment) {
      candidates.add(`${hostBase}-${segment}`);
      candidates.add(`${firstLabel}-${segment}`);
    }
  }
  return [...candidates].filter(candidate => /^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(candidate));
}

export function deriveSourceId(raw: string): string {
  return deriveSourceIdCandidates(raw)[0] ?? `ad-hoc-${slug(raw).slice(0, 12)}`;
}

export const deriveAdHocSourceId = deriveSourceId;
export const normalizeFeedAddress = normalizeFeedUrl;

function validateCatalog(raw: unknown): { sources: CatalogSource[] } {
  const parsed = CatalogSchema.parse(raw);
  const sources = [...parsed.feeds, ...parsed.retired];
  const ids = new Set<string>();
  const urls = new Map<string, string>();

  for (const source of parsed.feeds) {
    if (source.status === "retired") {
      throw new FeedProbeInputError(`Catalog feed ${source.id} must not use retired status`);
    }
    SourceSnapshotSchema.parse({
      source_id: source.id,
      feed_url: source.url,
      title: source.title ?? source.id,
      publisher_id: source.publisher_id ?? null,
      tier: source.tier ?? 1,
      status: source.status,
      weight: source.weight ?? 1,
      applied_tier_weight: source.weight ?? 1,
    });
  }
  for (const source of parsed.retired) {
    if (source.status !== "retired") {
      throw new FeedProbeInputError(`Catalog retired source ${source.id} must use retired status`);
    }
    SourceSnapshotSchema.parse({
      source_id: source.id,
      feed_url: source.url,
      title: source.title ?? source.id,
      publisher_id: source.publisher_id ?? null,
      tier: source.tier ?? 1,
      status: source.status,
      weight: source.weight ?? 1,
      applied_tier_weight: source.weight ?? 1,
    });
  }
  for (const source of sources) {
    if (ids.has(source.id)) throw new FeedProbeInputError(`Duplicate catalog source ID: ${source.id}`);
    ids.add(source.id);
    const normalized = normalizeFeedUrl(source.url);
    const existing = urls.get(normalized);
    if (existing !== undefined) {
      throw new FeedProbeInputError(`Duplicate catalog feed URL: ${source.id} and ${existing}`);
    }
    urls.set(normalized, source.id);
  }
  return { sources };
}

export async function loadSourceCatalog(repoRoot: string): Promise<{ sources: CatalogSource[] }> {
  const raw = await Bun.file(join(repoRoot, "config", "sources.json")).json();
  return validateCatalog(raw);
}

export function parseSourceCatalog(raw: unknown): { sources: CatalogSource[] } {
  return validateCatalog(raw);
}

function catalogDuplicate(
  adHocUrl: string,
  catalog: { sources: CatalogSource[] },
): CatalogSource | null {
  const normalized = normalizeFeedUrl(adHocUrl);
  const adHocCandidates = new Set(deriveSourceIdCandidates(normalized));
  for (const source of catalog.sources) {
    if (normalizeFeedUrl(source.url) === normalized) return source;
    if (adHocCandidates.has(source.id)) return source;
    const sourceCandidates = new Set(deriveSourceIdCandidates(source.url));
    sourceCandidates.add(source.id);
    for (const candidate of sourceCandidates) {
      if (adHocCandidates.has(candidate)) return source;
    }
  }
  return null;
}

export async function resolveFeedProbeTargets(
  options: FeedProbeCliOptions,
  loadCatalog: () => Promise<unknown>,
): Promise<FeedProbeTarget[]> {
  const catalogRaw = await loadCatalog();
  const catalog = parseSourceCatalog(catalogRaw);

  if (options.urls.length > 0) {
    if (options.fromConfig !== null || options.vertical !== null || options.ids.length > 0) {
      throw new FeedProbeInputError("URL mode cannot be combined with source catalog selectors");
    }
    const targets: FeedProbeTarget[] = [];
    const urls = new Set<string>();
    const ids = new Set<string>();
    for (const rawUrl of options.urls) {
      const normalized = normalizeFeedUrl(rawUrl);
      const duplicate = catalogDuplicate(normalized, catalog);
      if (duplicate !== null) {
        throw new FeedProbeInputError(
          `Duplicate catalog target: ${duplicate.id} (${normalizeFeedUrl(duplicate.url)})`,
        );
      }
      if (urls.has(normalized)) throw new FeedProbeInputError(`Duplicate feed URL target: ${normalized}`);
      urls.add(normalized);
      const feedId = deriveSourceId(normalized);
      if (ids.has(feedId)) throw new FeedProbeInputError(`Duplicate derived source ID target: ${feedId}`);
      ids.add(feedId);
      targets.push({ feed_id: feedId, url: rawUrl, status: "draft", vertical: null });
    }
    return targets;
  }
  if (
    options.fromConfig === null
    && options.vertical === null
    && options.ids.length === 0
  ) {
    throw new FeedProbeInputError("No feed targets were provided");
  }

  const mode = options.fromConfig ?? "feeds";
  const catalogByMode = mode === "feeds"
    ? catalogRawFeeds(catalog)
    : mode === "retired"
      ? catalogRawRetired(catalog)
      : catalog.sources;

  let selected = catalogByMode;
  if (options.vertical !== null) {
    selected = selected.filter(source => source.vertical === options.vertical);
  }
  if (options.ids.length > 0) {
    const ids = new Set(options.ids);
    selected = selected.filter(source => ids.has(source.id));
  }
  if (selected.length === 0) throw new FeedProbeInputError("No targets matched the source catalog selection");

  const targets: FeedProbeTarget[] = [];
  const urls = new Set<string>();
  const ids = new Set<string>();
  for (const source of selected) {
    const normalized = normalizeFeedUrl(source.url);
    if (ids.has(source.id) || urls.has(normalized)) {
      throw new FeedProbeInputError(`Duplicate catalog target: ${source.id}`);
    }
    ids.add(source.id);
    urls.add(normalized);
    targets.push({
      feed_id: source.id,
      url: source.url,
      status: source.status,
      vertical: source.vertical ?? null,
    });
  }
  return targets;
}

function catalogRawFeeds(catalog: { sources: CatalogSource[] }): CatalogSource[] {
  return catalog.sources.filter(source => source.status !== "retired");
}

function catalogRawRetired(catalog: { sources: CatalogSource[] }): CatalogSource[] {
  return catalog.sources.filter(source => source.status === "retired");
}
